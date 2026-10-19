from __future__ import annotations

from pathlib import Path
import sys


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from pages import sessions


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
