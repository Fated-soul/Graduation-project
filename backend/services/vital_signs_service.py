from __future__ import annotations

from typing import Any

from backend.repositories import device_repository, vital_signs_repository
from backend.schemas.vital_signs import VitalSignsCreate


def store_vital_signs(vital_signs: VitalSignsCreate) -> dict[str, Any]:
    stored = vital_signs_repository.create_vital_signs(vital_signs)
    device_repository.update_device_from_telemetry(vital_signs.device_id)
    return stored


def get_latest(mouse_id: str) -> dict[str, Any] | None:
    return vital_signs_repository.get_latest_vital_signs(mouse_id)


def get_history(mouse_id: str, hours: int = 1, limit: int = 500) -> list[dict[str, Any]]:
    return vital_signs_repository.get_vital_signs_history(mouse_id, hours, limit)


def get_device_history(
    device_id: str,
    hours: int = 1,
    limit: int = 500,
) -> list[dict[str, Any]]:
    return vital_signs_repository.get_device_vital_signs(device_id, hours, limit)
