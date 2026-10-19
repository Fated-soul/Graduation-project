from __future__ import annotations

from fastapi import APIRouter, Query, status

from backend.api.errors import raise_database_http_exception
from backend.schemas.common import APIResponse
from backend.schemas.stimulation import StimulationEventCreate, StimulationEventType, StimulationSettingUpdate
from backend.services import stimulation_service
from backend.services.device_connection_manager import device_connection_manager

router = APIRouter(prefix="/api/stimulation", tags=["stimulation"])


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_stimulation_event(event: StimulationEventCreate) -> APIResponse:
    try:
        stored = stimulation_service.create_event(event)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="stimulation event stored", data=stored)


@router.patch("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def patch_stimulation_event(event: StimulationEventCreate) -> APIResponse:
    try:
        stored = stimulation_service.create_event(event)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="stimulation event stored", data=stored)


@router.get("/settings/{device_id}", response_model=APIResponse)
def get_stimulation_settings(device_id: str) -> APIResponse:
    try:
        settings = stimulation_service.get_settings(device_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=settings)


@router.put("/settings", response_model=APIResponse)
async def update_stimulation_setting(setting: StimulationSettingUpdate) -> APIResponse:
    try:
        stored = stimulation_service.save_setting(setting)
        delivered = await device_connection_manager.send_json(
            setting.device_id,
            {
                "type": "stimulation_settings",
                "mouse_id": setting.mouse_id,
                "device_id": setting.device_id,
                "event_type": setting.event_type,
                "enabled": setting.enabled,
                "min_interval_ms": setting.min_interval_ms,
                "max_interval_ms": setting.max_interval_ms,
                "min_duration_ms": setting.min_duration_ms,
                "max_duration_ms": setting.max_duration_ms,
            },
        )
    except Exception as exc:
        raise_database_http_exception(exc)

    response_data = dict(stored)
    response_data["delivered"] = delivered
    return APIResponse(message="stimulation setting stored", data=response_data)


@router.get("/{mouse_id}", response_model=APIResponse)
def get_stimulation_history(
    mouse_id: str,
    event_type: StimulationEventType | None = Query(default=None),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=100, ge=1, le=1000),
) -> APIResponse:
    try:
        history = stimulation_service.get_history(
            mouse_id=mouse_id,
            event_type=event_type,
            hours=hours,
            limit=limit,
        )
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=history)
