from __future__ import annotations

from typing import Any

from backend.repositories import device_repository
from backend.schemas.device import DeviceCreate, DeviceStatusUpdate


def list_devices(
    online: bool | None = None,
    device_type: str | None = None,
) -> list[dict[str, Any]]:
    return device_repository.get_devices(online=online, device_type=device_type)


def get_device(device_id: str) -> dict[str, Any] | None:
    return device_repository.get_device_by_device_id(device_id)


def create_device(device: DeviceCreate) -> dict[str, Any]:
    return device_repository.create_device(device)


def delete_device(device_id: str) -> dict[str, Any] | None:
    return device_repository.delete_device(device_id)


def update_status(
    device_id: str,
    status_update: DeviceStatusUpdate,
) -> dict[str, Any] | None:
    return device_repository.update_device_status(device_id, status_update)
