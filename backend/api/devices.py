from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.errors import raise_database_http_exception
from backend.schemas.common import APIResponse
from backend.schemas.device import DeviceCreate, DeviceStatusUpdate
from backend.services import device_service

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("", response_model=APIResponse)
def list_devices(
    online: bool | None = Query(default=None),
    device_type: str | None = Query(default=None, min_length=1, max_length=50),
) -> APIResponse:
    try:
        devices = device_service.list_devices(online=online, device_type=device_type)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=devices)


@router.get("/{device_id}", response_model=APIResponse)
def get_device(device_id: str) -> APIResponse:
    try:
        device = device_service.get_device(device_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if device is None:
        raise HTTPException(status_code=404, detail="device not found")
    return APIResponse(data=device)


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_device(device: DeviceCreate) -> APIResponse:
    try:
        created = device_service.create_device(device)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="device created", data=created)


@router.delete("/{device_id}", response_model=APIResponse)
def delete_device(device_id: str) -> APIResponse:
    try:
        deleted = device_service.delete_device(device_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if deleted is None:
        raise HTTPException(status_code=404, detail="device not found")
    return APIResponse(message="device deleted", data=deleted)


@router.patch("/{device_id}/status", response_model=APIResponse)
def update_device_status(
    device_id: str,
    status_update: DeviceStatusUpdate,
) -> APIResponse:
    try:
        updated = device_service.update_status(device_id, status_update)
    except Exception as exc:
        raise_database_http_exception(exc)
    if updated is None:
        raise HTTPException(status_code=404, detail="device not found")
    return APIResponse(message="device status updated", data=updated)
