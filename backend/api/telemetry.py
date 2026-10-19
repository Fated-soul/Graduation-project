from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.errors import raise_database_http_exception
from backend.schemas.common import APIResponse
from backend.schemas.telemetry import TelemetryCreate
from backend.services import telemetry_service

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_telemetry(telemetry: TelemetryCreate) -> APIResponse:
    try:
        stored = telemetry_service.store_telemetry(telemetry)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="telemetry stored", data=stored)


@router.get("/latest/{mouse_id}", response_model=APIResponse)
def get_latest_telemetry(mouse_id: str) -> APIResponse:
    try:
        latest = telemetry_service.get_latest(mouse_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if latest is None:
        raise HTTPException(status_code=404, detail="telemetry not found")
    return APIResponse(data=latest)


@router.get("/history/{mouse_id}", response_model=APIResponse)
def get_telemetry_history(
    mouse_id: str,
    hours: int = Query(default=1, ge=1, le=168),
    limit: int = Query(default=500, ge=1, le=5000),
) -> APIResponse:
    try:
        history = telemetry_service.get_history(mouse_id, hours, limit)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=history)


@router.get("/device/{device_id}", response_model=APIResponse)
def get_device_telemetry(
    device_id: str,
    hours: int = Query(default=1, ge=1, le=168),
    limit: int = Query(default=500, ge=1, le=5000),
) -> APIResponse:
    try:
        history = telemetry_service.get_device_history(device_id, hours, limit)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=history)
