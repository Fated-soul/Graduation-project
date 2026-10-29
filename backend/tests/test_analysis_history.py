from __future__ import annotations

from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from backend.api import public_data
from backend.services import agent_service, dandi_service


@pytest.mark.parametrize("cursor", [None, 240, 1])
def test_analysis_list_passes_valid_cursor_to_repository(monkeypatch, cursor):
    get_records = Mock(return_value=[])
    monkeypatch.setattr(public_data.public_data_repository, "get_analyses", get_records)
    app = FastAPI()
    app.include_router(public_data.router)
    query = "?limit=200" + (f"&before_id={cursor}" if cursor is not None else "")
    with TestClient(app) as client:
        response = client.get("/api/public-data/sessions/3/analyses" + query)
    assert response.status_code == 200
    get_records.assert_called_once_with(3, 200, cursor)


@pytest.mark.parametrize("cursor", ["0", "-1", "not-a-number"])
def test_analysis_list_rejects_invalid_cursor(monkeypatch, cursor):
    get_records = Mock()
    monkeypatch.setattr(public_data.public_data_repository, "get_analyses", get_records)
    app = FastAPI()
    app.include_router(public_data.router)
    with TestClient(app) as client:
        response = client.get(f"/api/public-data/sessions/3/analyses?before_id={cursor}")
    assert response.status_code == 422
    get_records.assert_not_called()


def test_follow_up_transmits_the_entire_ancestor_chain_without_changing_the_question(monkeypatch):
    repository = dandi_service.public_data_repository
    history = [{
        "id": index, "parent_analysis_id": index - 1 if index > 1 else None,
        "question": "原始研究问题" if index == 1 else f"第 {index - 1} 次追问",
        "summary": "完整结论" * 250,
        "evidence": [f"依据 {index}"], "recommendation": "继续复核",
        "analysis_source": "bailian_multimodal_agent",
    } for index in range(1, 26)]
    monkeypatch.setattr(repository, "get_session", lambda _: {"subject_code": "test-mouse"})
    monkeypatch.setattr(repository, "get_analysis", lambda session, ident: history[-1] if (session, ident) == (1, 25) else None)
    load_chain = Mock(return_value=history)
    monkeypatch.setattr(repository, "get_analysis_chain", load_chain)
    monkeypatch.setattr(repository, "get_timeline", lambda _: {
        "modeling_events": [], "signal_windows": [], "annotations": [], "roi_metrics": [],
    })
    monkeypatch.setattr(repository, "create_analysis", lambda _, data: data)
    generate = Mock(return_value={"data": {"summary": "本轮答复", "analysis_source": "bailian_multimodal_agent"}})
    monkeypatch.setattr(agent_service, "analyze_dataset_session", generate)

    result = dandi_service.build_session_analysis(1, "现在还缺什么证据？", parent_analysis_id=25)

    load_chain.assert_called_once_with(1, 25)
    payload = generate.call_args.kwargs
    assert payload["question"] == result["question"] == "现在还缺什么证据？"
    assert len(payload["history"]) == 25
    assert payload["history"][0]["question"] == "原始研究问题"
    assert payload["history"][0]["summary"] == history[0]["summary"]
    assert result["parent_analysis_id"] == 25


def test_follow_up_rejects_a_parent_from_another_session(monkeypatch):
    repository = dandi_service.public_data_repository
    monkeypatch.setattr(repository, "get_session", lambda _: {"subject_code": "test-mouse"})
    monkeypatch.setattr(repository, "get_analysis", lambda *_: None)
    load_chain = Mock()
    monkeypatch.setattr(repository, "get_analysis_chain", load_chain)
    with pytest.raises(LookupError, match="analysis record not found"):
        dandi_service.build_session_analysis(1, "继续", parent_analysis_id=99)
    load_chain.assert_not_called()


def test_agent_proxy_keeps_history_separate_from_the_question(monkeypatch):
    request = Mock(return_value={"success": True})
    monkeypatch.setattr(agent_service, "_request", request)
    history = [{"question": "原始问题", "summary": "原始答复"}]
    agent_service.analyze_dataset_session(1, question="追问", history=history)
    assert request.call_args.args[2] == {"question": "追问", "history": history}
