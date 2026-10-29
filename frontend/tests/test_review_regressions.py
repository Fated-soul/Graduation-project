from __future__ import annotations

from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

import pytest
from streamlit.testing.v1 import AppTest


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from data import public_dataset
from pages import dataset_agent, evidence_review
from utils.analysis_source import analysis_source_label


@pytest.mark.parametrize("duration", [273.953, 599.866, 0.001, 0.0])
def test_video_end_time_remains_inside_the_session_after_rounding(duration):
    assert evidence_review._normalize_video_time(duration, duration) == duration
    assert evidence_review._normalize_video_time(duration + 10, duration) == duration


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_player_times_are_ignored(value):
    assert evidence_review._normalize_video_time(value, 273.953) is None


def test_review_input_accepts_the_exact_fractional_session_end():
    app = AppTest.from_string("""
import streamlit as st
from pages.evidence_review import _normalize_video_time
duration = 273.953
st.session_state.review_time = _normalize_video_time(274.0, duration)
st.number_input('复核时间点（秒）', min_value=0.0, max_value=duration, format='%.3f', key='review_time')
""").run()
    assert not app.exception
    assert app.number_input[0].value == 273.953


def test_analysis_pagination_recovers_a_long_thread_and_ignores_newer_insertions(monkeypatch):
    rows = [{
        "id": index, "parent_analysis_id": index - 1 if index > 1 else None,
        "question": f"问题 {index}", "created_at": "2026-10-29T10:00:00+08:00",
    } for index in range(1, 451)]
    calls = []

    def fetch(path, **_):
        query = parse_qs(urlsplit(path).query)
        before = int(query.get("before_id", [1000])[0])
        calls.append(before)
        result = list(reversed([row for row in rows if row["id"] < before]))[:200]
        if len(calls) == 1:
            rows.append({"id": 999, "parent_analysis_id": None})
        return result

    monkeypatch.setattr(public_dataset, "api_data", fetch)
    result = public_dataset.get_session_analyses(1)
    threads = dataset_agent._group_analysis_threads(result)
    assert calls == [1000, 251, 51]
    assert len(result) == 450
    assert len(threads) == 1
    assert [row["id"] for row in threads[0]] == list(range(1, 451))


def test_a_failed_history_page_is_not_exported_as_a_complete_thread(monkeypatch):
    pages = iter([[{"id": index} for index in range(250, 50, -1)], None])
    monkeypatch.setattr(public_dataset, "api_data", lambda *_args, **_kwargs: next(pages))
    with pytest.raises(RuntimeError, match="完整读取"):
        public_dataset.get_session_analyses(1)


def test_nonadvancing_history_cursor_does_not_loop_forever(monkeypatch):
    monkeypatch.setattr(public_dataset, "api_data", lambda *_args, **_kwargs: [{"id": index} for index in range(250, 50, -1)])
    with pytest.raises(RuntimeError, match="读取中断"):
        public_dataset.get_session_analyses(1)


@pytest.mark.parametrize("analysis,title,description", [
    ({"analysis_source": "multimodal_modeling_evidence", "model_name": None}, "本地证据评估", "未使用云端模型或知识库"),
    ({"analysis_source": "bailian_rag_multimodal_agent", "knowledge_sources": [{"title": "资料"}]}, "Agent 辅助结论", "检索到的研究资料"),
    ({"analysis_source": "bailian_multimodal_agent", "knowledge_sources": []}, "Agent 辅助结论", "未引用外部研究资料"),
    ({}, "历史评估结论", "未记录完整的生成来源"),
])
def test_analysis_labels_match_the_actual_generation_source(analysis, title, description):
    label, detail = analysis_source_label(analysis)
    assert label == title
    assert description in detail
