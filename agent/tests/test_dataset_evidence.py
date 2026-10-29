from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock

from agent import llm_client
from agent.dataset_evidence import compact_dataset_context
from agent.schemas import DatasetSessionAnalysisRequest


def signal_rows():
    return [{
        "modality": modality, "signal_name": modality, "unit": "V" if modality in {"eeg", "emg"} else "a.u.",
        "window_start_seconds": index * 3.0, "window_end_seconds": (index + 1) * 3.0,
        "mean_value": float(index), "min_value": float(index),
        "max_value": 9999.0 if index == 175 else float(index),
    } for index in range(180) for modality in ("calcium", "motion", "eeg", "emg")]


def test_compact_signals_cover_each_modality_from_start_to_end():
    rows = signal_rows()
    context = {"signal_windows": rows}
    compact = compact_dataset_context(context)
    assert len(compact["signal_windows"]) == 360
    for modality in ("calcium", "motion", "eeg", "emg"):
        selected = [row for row in compact["signal_windows"] if row["modality"] == modality]
        assert len(selected) == 90
        assert selected[0]["window_start_seconds"] == 0.0
        assert selected[-1]["window_end_seconds"] == 540.0
        summary = next(row for row in compact["signal_summary"] if row["modality"] == modality)
        assert summary["window_count"] == 180
        assert summary["supplied_window_count"] == 90
        assert summary["maximum_recorded_sample_value"] == 9999.0
        assert summary["maximum_window_mean"] == 179.0
        assert summary["mean_of_window_means"] == 89.5
    assert compact["evidence_coverage"]["signal_windows"] == {
        "available_count": 720, "supplied_count": 360, "is_reduced": True,
        "selection": "stratified_full_time_sample",
    }
    assert len(rows) == 720


def test_small_context_keeps_all_records_and_does_not_claim_reduction():
    rows = signal_rows()[:20]
    compact = compact_dataset_context({"signal_windows": rows})
    assert compact["signal_windows"] == rows
    assert compact["evidence_coverage"]["signal_windows"]["selection"] == "all"
    assert compact["evidence_coverage"]["signal_windows"]["is_reduced"] is False


def test_event_reduction_retains_shocks_and_late_freezing_with_full_totals():
    events = [{"event_type": "electric_shock", "start_time_seconds": index * 60.0,
               "stop_time_seconds": index * 60.0 + 2} for index in range(3)]
    events += [{"event_type": "freezing", "start_time_seconds": float(index),
                "stop_time_seconds": float(index) + 0.5} for index in range(500)]
    compact = compact_dataset_context({"modeling_events": events})
    assert len(compact["modeling_events"]) == 180
    assert sum(row["event_type"] == "electric_shock" for row in compact["modeling_events"]) == 3
    assert max(row["start_time_seconds"] for row in compact["modeling_events"]) == 499.0
    freezing = next(row for row in compact["modeling_event_summary"] if row["event_type"] == "freezing")
    assert freezing == {"event_type": "freezing", "event_count": 500, "sum_interval_seconds": 250.0}


def test_summaries_handle_missing_and_nonfinite_values():
    compact = compact_dataset_context({"signal_windows": [{
        "modality": "eeg", "mean_value": float("nan"), "max_value": float("inf"),
    }]})
    assert compact["signal_summary"][0]["mean_of_window_means"] is None
    assert compact["signal_summary"][0]["maximum_recorded_sample_value"] is None


def test_limited_detail_reports_channels_that_have_no_budget():
    rows = [{"modality": "calcium", "channel_name": str(index), "mean_value": 1} for index in range(400)]
    compact = compact_dataset_context({"signal_windows": rows})
    assert len(compact["signal_windows"]) == 360
    assert len(compact["signal_summary"]) == 400
    assert sum(row["supplied_window_count"] == 0 for row in compact["signal_summary"]) == 40


def test_generation_receives_full_dialogue_and_explicit_evidence_coverage(monkeypatch):
    client = Mock()
    client.chat.completions.create.return_value = SimpleNamespace(choices=[
        SimpleNamespace(message=SimpleNamespace(content='{"summary":"受控测试答复"}')),
    ])
    monkeypatch.setattr(llm_client.config, "DASHSCOPE_API_KEY", "test-placeholder")
    monkeypatch.setattr(llm_client, "OpenAI", Mock(return_value=client))
    monkeypatch.setattr(llm_client, "retrieve_knowledge", lambda _: {"mode": "disabled", "sources": []})
    history = [{"question": f"历史问题 {index}", "summary": f"历史答复 {index}"} for index in range(25)]

    llm_client.analyze_dataset_session(
        context={"signal_windows": signal_rows()}, question="当前追问", history=history,
    )

    messages = client.chat.completions.create.call_args.kwargs["messages"]
    assert len(messages) == 52
    assert messages[1]["content"] == "历史问题 0"
    assert "历史答复 24" in messages[-2]["content"]
    assert "当前追问" in messages[-1]["content"]
    compact = json.loads(messages[-1]["content"].split("会话证据：\n", 1)[1].split("\n\n可引用的研究资料：", 1)[0])
    assert compact["evidence_coverage"]["signal_windows"]["is_reduced"] is True
    assert max(row["window_end_seconds"] for row in compact["signal_windows"]) == 540.0


def test_structured_history_is_not_limited_by_the_current_question_length():
    request = DatasetSessionAnalysisRequest.model_validate({
        "question": "当前问题",
        "history": [{"question": "历史问题" * 300, "summary": "历史答复" * 1000} for _ in range(25)],
    })
    assert len(request.history) == 25
