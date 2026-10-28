from __future__ import annotations

from pathlib import Path
import sys

from streamlit.testing.v1 import AppTest


FRONTEND_DIR = Path(__file__).resolve().parents[1]
PLAYER_COMPONENT_APP = Path(__file__).resolve().parent / "player_component_app.py"
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from data import public_dataset
from pages import dataset_agent, evidence_review, sessions


class _SessionState(dict):
    def __getattr__(self, name: str):
        return self[name]

    def __setattr__(self, name: str, value) -> None:
        self[name] = value


class _StreamlitStub:
    def __init__(self) -> None:
        self.session_state = _SessionState()
        self.rerun_called = False

    def rerun(self) -> None:
        self.rerun_called = True


def test_open_review_carries_the_selected_subject_and_session(monkeypatch) -> None:
    stub = _StreamlitStub()
    monkeypatch.setattr(sessions, "st", stub)

    sessions._open_review({"id": 63, "subject_code": "Ca-EEG3-4"})

    assert stub.session_state["review_subject_id"] == "Ca-EEG3-4"
    assert stub.session_state["review_primary_session"] == 63
    assert stub.session_state["current_page"] == "多模态复核"
    assert stub.rerun_called is True


def test_legacy_agent_questions_are_presented_in_readable_chinese() -> None:
    english = (
        "Assess whether this FC session supports fear-memory formation by jointly "
        "considering foot shocks, freezing behavior, and calcium activity. State "
        "the limits of the conclusion."
    )

    assert "足底电击" in dataset_agent._display_question(english)
    assert "多模态证据" in dataset_agent._display_question("????????????????????")


def test_agent_followups_stay_with_their_original_conversation() -> None:
    analyses = [
        {"id": 4, "parent_analysis_id": 2, "created_at": "2026-10-19T10:04:00"},
        {"id": 3, "parent_analysis_id": None, "created_at": "2026-10-19T10:03:00"},
        {"id": 2, "parent_analysis_id": 1, "created_at": "2026-10-19T10:02:00"},
        {"id": 1, "parent_analysis_id": None, "created_at": "2026-10-19T10:01:00"},
    ]

    threads = dataset_agent._group_analysis_threads(analyses)

    assert [[item["id"] for item in thread] for thread in threads] == [[1, 2, 4], [3]]


def test_review_records_are_ordered_by_session_position() -> None:
    records = [
        {"id": 3, "timestamp_seconds": 125.5, "created_at": "2026-10-23T10:00:00"},
        {"id": 1, "timestamp_seconds": None, "created_at": "2026-10-23T09:00:00"},
        {"id": 2, "timestamp_seconds": 8.0, "created_at": "2026-10-23T11:00:00"},
    ]

    ordered = evidence_review._sorted_annotations(records)

    assert [item["id"] for item in ordered] == [2, 3, 1]
    assert evidence_review._format_session_offset(125.5) == "02:05.5"
    assert evidence_review._format_session_offset(None) == "未定位"


def test_video_time_is_normalized_before_updating_the_review_form() -> None:
    assert evidence_review._normalize_video_time(12.36, 30.0) == 12.4
    assert evidence_review._normalize_video_time(35.0, 30.0) == 30.0
    assert evidence_review._normalize_video_time(-2.0, 30.0) == 0.0
    assert evidence_review._normalize_video_time(None, 30.0) is None


def test_signal_axis_labels_preserve_physical_units() -> None:
    label, unit = evidence_review._signal_axis_label(
        "eeg",
        [{"signal_name": "脑电均方根幅值", "unit": "volts"}],
    )

    assert label == "脑电均方根幅值（V）"
    assert unit == "V"


def test_signal_axis_labels_mark_unspecified_relative_values_as_arbitrary_units() -> None:
    label, unit = evidence_review._signal_axis_label(
        "calcium",
        [{"signal_name": "群体钙活动", "unit": "n.a."}],
    )

    assert label == "群体钙活动（a.u.）"
    assert unit == "a.u."


def test_synchronized_player_reports_user_selected_video_time() -> None:
    component = (
        FRONTEND_DIR
        / "components"
        / "synchronized_player_frontend"
        / "index.html"
    ).read_text(encoding="utf-8")

    assert "streamlit:setComponentValue" in component
    assert 'video.addEventListener("pause", emitCurrentTime)' in component
    assert 'video.addEventListener("seeked", scheduleEmit)' in component
    assert "now - lastPlaybackEmitAt >= 800" in component
    assert "采用当前画面时间" in component


def test_synchronized_player_component_loads_in_streamlit() -> None:
    app = AppTest.from_file(str(PLAYER_COMPONENT_APP), default_timeout=20).run()

    assert not app.exception


def test_delete_review_record_uses_the_session_scoped_endpoint(monkeypatch) -> None:
    request: dict[str, object] = {}

    def fake_request(path: str, **kwargs):
        request["path"] = path
        request.update(kwargs)
        return {"success": True}

    monkeypatch.setattr(public_dataset, "api_request", fake_request)

    response = public_dataset.delete_annotation(12, 34)

    assert response["success"] is True
    assert request["path"] == "/api/public-data/sessions/12/annotations/34"
    assert request["method"] == "DELETE"
