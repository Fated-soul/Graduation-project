from __future__ import annotations

from pathlib import Path
import sys


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from pages import dataset_agent, sessions


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
