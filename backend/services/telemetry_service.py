from __future__ import annotations

from typing import Any

from backend.repositories import device_repository, telemetry_repository
from backend.schemas.telemetry import TelemetryCreate


def store_telemetry(telemetry: TelemetryCreate) -> dict[str, Any]:
    stored = telemetry_repository.create_telemetry(telemetry)
    device_repository.update_device_from_telemetry(
        telemetry.device_id,
        voltage=telemetry.voltage,
        current=telemetry.current,
    )
    return stored


def get_latest(mouse_id: str) -> dict[str, Any] | None:
    return telemetry_repository.get_latest_telemetry(mouse_id)


def get_history(mouse_id: str, hours: int = 1, limit: int = 500) -> list[dict[str, Any]]:
    return telemetry_repository.get_telemetry_history(mouse_id, hours, limit)


def get_device_history(
    device_id: str,
    hours: int = 1,
    limit: int = 500,
) -> list[dict[str, Any]]:
    return telemetry_repository.get_device_telemetry(device_id, hours, limit)
