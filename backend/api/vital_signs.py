from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.errors import raise_database_http_exception
from backend.schemas.common import APIResponse
from backend.schemas.vital_signs import VitalSignsCreate
from backend.services import vital_signs_service

router = APIRouter(prefix="/api/vital-signs", tags=["vital-signs"])


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_vital_signs(vital_signs: VitalSignsCreate) -> APIResponse:
    try:
        stored = vital_signs_service.store_vital_signs(vital_signs)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="vital signs stored", data=stored)


@router.get("/latest/{mouse_id}", response_model=APIResponse)
def get_latest_vital_signs(mouse_id: str) -> APIResponse:
    try:
        latest = vital_signs_service.get_latest(mouse_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if latest is None:
        raise HTTPException(status_code=404, detail="vital signs not found")
    return APIResponse(data=latest)


@router.get("/history/{mouse_id}", response_model=APIResponse)
def get_vital_signs_history(
    mouse_id: str,
    hours: int = Query(default=1, ge=1, le=168),
    limit: int = Query(default=500, ge=1, le=10000),
) -> APIResponse:
    try:
        history = vital_signs_service.get_history(mouse_id, hours, limit)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=history)


@router.get("/device/{device_id}", response_model=APIResponse)
def get_device_vital_signs(
    device_id: str,
    hours: int = Query(default=1, ge=1, le=168),
    limit: int = Query(default=500, ge=1, le=10000),
) -> APIResponse:
    try:
        history = vital_signs_service.get_device_history(device_id, hours, limit)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=history)
