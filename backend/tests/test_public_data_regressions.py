from __future__ import annotations

from unittest.mock import Mock

import h5py
import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api import public_data
from backend.services import agent_service, dandi_service
from backend.services.nwb_import_service import _read_modeling_events


@pytest.mark.parametrize("shock_path", [
    "stimulus/presentation/ShockStimuli",
    "stimulus/ShockStimuli",
    "intervals/ShockStimuli",
    "processing/custom/RecordedShockIntervals",
])
def test_fc_shocks_are_not_hidden_by_a_known_freezing_group(tmp_path, shock_path):
    path = tmp_path / "fc.nwb"
    with h5py.File(path, "w") as nwb:
        shock = nwb.create_group(shock_path)
        shock.create_dataset("start_time", data=[120.0, 180.0, 240.0])
        shock.create_dataset("stop_time", data=[122.0, 182.0, 242.0])
        shock.create_dataset("shock_amplitude", data=[1.5, 1.5, 1.5])
        freezing = nwb.create_group("processing/behavior/FreezingIntervals")
        freezing.create_dataset("start_time", data=[130.0])
        freezing.create_dataset("stop_time", data=[135.0])
        events = _read_modeling_events(nwb, 100, session_type="fear_conditioning")
    shocks = [x for x in events if x["event_type"] == "electric_shock"]
    assert [x["start_time_seconds"] for x in shocks] == [120.0, 180.0, 240.0]
    assert [x["numeric_value"] for x in shocks] == [1.5, 1.5, 1.5]
    assert all(x["source_path"] == "/" + shock_path for x in shocks)
    assert len([x for x in events if x["event_type"] == "freezing"]) == 1


def test_fc_stimulus_alias_is_not_counted_twice(tmp_path):
    with h5py.File(tmp_path / "aliases.nwb", "w") as nwb:
        shock = nwb.create_group("stimulus/presentation/ShockStimuli")
        shock.create_dataset("start_time", data=np.array([120.0]))
        shock.create_dataset("stop_time", data=np.array([122.0]))
        nwb["stimulus/ShockStimuli"] = shock
        events = _read_modeling_events(nwb, 100, session_type="fear_conditioning")
    assert len(events) == 1
    assert events[0]["source_path"] == "/stimulus/presentation/ShockStimuli"


@pytest.fixture
def annotation_api(monkeypatch):
    session = {"id": 1, "duration_seconds": 273.966}
    save = Mock(side_effect=lambda session_id, data: {"id": 10, "session_id": session_id, **data})
    monkeypatch.setattr(public_data.public_data_repository, "get_session", lambda _: session)
    monkeypatch.setattr(public_data.public_data_repository, "create_annotation", save)
    app = FastAPI()
    app.include_router(public_data.router)
    with TestClient(app) as client:
        yield client, session, save


@pytest.mark.parametrize("timestamp,status", [
    (0, 201), (12.3, 201), (273.966, 201), (273.966001, 422),
    (999999, 422), (-1, 422), ("NaN", 422), ("Infinity", 422), ("-Infinity", 422),
    (None, 201),
])
def test_annotation_time_is_bounded_before_writing(annotation_api, timestamp, status):
    client, _, save = annotation_api
    response = client.post("/api/public-data/sessions/1/annotations", json={
        "timestamp_seconds": timestamp, "category": "冻结行为", "note": "复核测试",
    })
    assert response.status_code == status
    assert save.call_count == (1 if status == 201 else 0)


@pytest.mark.parametrize("duration", [None, float("nan"), float("inf"), -1])
def test_annotation_with_unknown_duration_requires_an_unlocated_note(annotation_api, duration):
    client, session, save = annotation_api
    session["duration_seconds"] = duration
    timed = client.post("/api/public-data/sessions/1/annotations", json={
        "timestamp_seconds": 1.0, "category": "其他", "note": "复核测试",
    })
    assert timed.status_code == 422
    save.assert_not_called()
    unlocated = client.post("/api/public-data/sessions/1/annotations", json={
        "timestamp_seconds": None, "category": "其他", "note": "整体观察",
    })
    assert unlocated.status_code == 201


def test_zero_duration_only_accepts_zero_or_unlocated_time(annotation_api):
    client, session, save = annotation_api
    session["duration_seconds"] = 0
    for timestamp, expected in ((0, 201), (0.01, 422), (None, 201)):
        response = client.post("/api/public-data/sessions/1/annotations", json={
            "timestamp_seconds": timestamp, "category": "其他", "note": "复核测试",
        })
        assert response.status_code == expected
    assert save.call_count == 2


def test_annotation_missing_session_is_not_written(annotation_api, monkeypatch):
    client, _, save = annotation_api
    monkeypatch.setattr(public_data.public_data_repository, "get_session", lambda _: None)
    response = client.post("/api/public-data/sessions/999/annotations", json={
        "timestamp_seconds": 0, "category": "其他", "note": "复核测试",
    })
    assert response.status_code == 404
    save.assert_not_called()


@pytest.fixture
def fallback_context(monkeypatch):
    session = {"id": 1, "subject_code": "test-mouse", "session_type": "neutral_exposure"}
    timeline = {
        "modeling_events": [{"event_type": "freezing", "start_time_seconds": 2, "stop_time_seconds": 3}],
        "signal_windows": [{"modality": "calcium"}], "roi_metrics": [], "annotations": [],
    }
    monkeypatch.setattr(dandi_service.public_data_repository, "get_session", lambda _: session)
    monkeypatch.setattr(dandi_service.public_data_repository, "get_timeline", lambda _: timeline)
    monkeypatch.setattr(dandi_service.public_data_repository, "create_analysis", lambda _, data: {"id": 2, **data})
    upstream = Mock(side_effect=RuntimeError("controlled provider outage"))
    monkeypatch.setattr(agent_service, "analyze_dataset_session", upstream)
    return session, timeline, upstream


@pytest.mark.parametrize("stage,prefix", [
    ("neutral_exposure", "本次为基线适应会话。"),
    ("fear_conditioning", "本次为恐惧条件化（FC）会话。"),
    ("recall_assessment", "本次为记忆回忆评估会话。"),
    ("offline_consolidation", "本次为离线巩固会话。"),
    ("longitudinal_followup", "本次为跨周随访会话。"),
    ("unknown", "本次为其他研究阶段会话。"),
])
def test_provider_outage_preserves_the_actual_research_stage(fallback_context, stage, prefix):
    session, _, upstream = fallback_context
    session["session_type"] = stage
    result = dandi_service.build_session_analysis(1, "应如何复核本阶段？", use_llm=True)
    assert result["summary"].startswith(prefix)
    assert result["analysis_source"] == "multimodal_modeling_evidence"
    assert result["model_name"] is None
    assert result["knowledge_sources"] == []
    upstream.assert_called_once()


def test_fc_fallback_does_not_claim_missing_shocks_or_video(fallback_context):
    session, _, _ = fallback_context
    session["session_type"] = "fear_conditioning"
    result = dandi_service.build_session_analysis(1, "有什么证据？", use_llm=False)
    assert "尚未记录足底电击" in result["summary"]
    assert "行为视频" not in result["summary"]


def test_offline_fallback_does_not_claim_missing_ephys(fallback_context):
    session, _, _ = fallback_context
    session["session_type"] = "offline_consolidation"
    result = dandi_service.build_session_analysis(1, "有哪些模态？", use_llm=False)
    assert "尚未记录" in result["summary"]
    assert all(label in result["summary"] for label in ("EEG", "EMG", "睡眠状态"))
    assert "均按该会话" not in result["summary"]


def test_empty_baseline_fallback_does_not_invent_evidence(fallback_context):
    _, timeline, _ = fallback_context
    timeline["modeling_events"] = []
    timeline["signal_windows"] = []
    result = dandi_service.build_session_analysis(1, "分析基线", use_llm=False)
    assert result["summary"].startswith("本次为基线适应会话。")
    assert "当前尚无已载入的事件或信号" in result["summary"]
