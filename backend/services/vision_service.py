from __future__ import annotations

from typing import Any

from backend.repositories import vision_repository


def get_keypoints(
    mouse_id: str,
    limit: int = 1000,
    frame_start: int | None = None,
    frame_end: int | None = None,
    keypoint_name: str | None = None,
) -> list[dict[str, Any]]:
    return vision_repository.get_keypoints(
        mouse_id=mouse_id,
        limit=limit,
        frame_start=frame_start,
        frame_end=frame_end,
        keypoint_name=keypoint_name,
    )


def get_frame_features(
    mouse_id: str,
    limit: int = 1000,
    frame_start: int | None = None,
    frame_end: int | None = None,
) -> list[dict[str, Any]]:
    return vision_repository.get_frame_features(
        mouse_id=mouse_id,
        limit=limit,
        frame_start=frame_start,
        frame_end=frame_end,
    )


def get_summary(mouse_id: str) -> dict[str, Any]:
    return vision_repository.get_summary(mouse_id)
