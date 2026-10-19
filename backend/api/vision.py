from __future__ import annotations

from fastapi import APIRouter, Query

from backend.api.errors import raise_database_http_exception
from backend.schemas.common import APIResponse
from backend.services import vision_service

router = APIRouter(prefix="/api/vision", tags=["vision"])


@router.get("/keypoints/{mouse_id}", response_model=APIResponse)
def get_keypoints(
    mouse_id: str,
    limit: int = Query(default=1000, ge=1, le=100000),
    frame_start: int | None = Query(default=None, ge=0),
    frame_end: int | None = Query(default=None, ge=0),
    keypoint_name: str | None = Query(default=None, min_length=1, max_length=100),
) -> APIResponse:
    try:
        rows = vision_service.get_keypoints(
            mouse_id=mouse_id,
            limit=limit,
            frame_start=frame_start,
            frame_end=frame_end,
            keypoint_name=keypoint_name,
        )
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=rows)


@router.get("/features/{mouse_id}", response_model=APIResponse)
def get_frame_features(
    mouse_id: str,
    limit: int = Query(default=1000, ge=1, le=100000),
    frame_start: int | None = Query(default=None, ge=0),
    frame_end: int | None = Query(default=None, ge=0),
) -> APIResponse:
    try:
        rows = vision_service.get_frame_features(
            mouse_id=mouse_id,
            limit=limit,
            frame_start=frame_start,
            frame_end=frame_end,
        )
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=rows)


@router.get("/summary/{mouse_id}", response_model=APIResponse)
def get_summary(mouse_id: str) -> APIResponse:
    try:
        summary = vision_service.get_summary(mouse_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=summary)
