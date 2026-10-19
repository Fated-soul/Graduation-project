from __future__ import annotations

from typing import Any

from backend.repositories import agent_analysis_repository


def get_latest(mouse_id: str) -> dict[str, Any] | None:
    return agent_analysis_repository.get_latest_analysis(mouse_id)


def get_history(mouse_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return agent_analysis_repository.get_analysis_history(mouse_id, limit)


def create(data: dict[str, Any]) -> dict[str, Any]:
    return agent_analysis_repository.create_analysis_result(data)


def confirm(analysis_id: int) -> dict[str, Any] | None:
    return agent_analysis_repository.confirm_analysis_result(analysis_id)
