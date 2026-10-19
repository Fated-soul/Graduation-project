from __future__ import annotations

from typing import Any

from backend.repositories import stimulation_repository
from backend.schemas.stimulation import StimulationEventCreate, StimulationSettingUpdate


def create_event(event: StimulationEventCreate) -> dict[str, Any]:
    return stimulation_repository.create_stimulation_event(event)


def get_history(
    mouse_id: str,
    event_type: str | None = None,
    hours: int = 24,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return stimulation_repository.get_stimulation_history(
        mouse_id=mouse_id,
        event_type=event_type,
        hours=hours,
        limit=limit,
    )


def save_setting(setting: StimulationSettingUpdate) -> dict[str, Any]:
    return stimulation_repository.upsert_stimulation_setting(
        mouse_id=setting.mouse_id,
        device_id=setting.device_id,
        event_type=setting.event_type,
        enabled=setting.enabled,
        min_interval_ms=setting.min_interval_ms,
        max_interval_ms=setting.max_interval_ms,
        min_duration_ms=setting.min_duration_ms,
        max_duration_ms=setting.max_duration_ms,
    )


def get_settings(device_id: str) -> list[dict[str, Any]]:
    return stimulation_repository.get_stimulation_settings(device_id)
