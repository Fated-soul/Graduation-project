from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.api.errors import raise_database_http_exception
from backend.schemas.animal import (
    AnimalCreate,
    AnimalDeviceBindingUpdate,
    AnimalStageUpdate,
    AnimalStatus,
    AnimalStatusUpdate,
)
from backend.schemas.common import APIResponse
from backend.services import animal_service

router = APIRouter(prefix="/api/animals", tags=["animals"])


@router.get("", response_model=APIResponse)
def list_animals(status: AnimalStatus | None = Query(default=None)) -> APIResponse:
    try:
        animals = animal_service.list_animals(status=status)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=animals)


@router.get("/{mouse_id}", response_model=APIResponse)
def get_animal(mouse_id: str) -> APIResponse:
    try:
        animal = animal_service.get_animal(mouse_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if animal is None:
        raise HTTPException(status_code=404, detail="animal not found")
    return APIResponse(data=animal)


@router.post("", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
def create_animal(animal: AnimalCreate) -> APIResponse:
    try:
        created = animal_service.create_animal(animal)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="animal created", data=created)


@router.patch("/{mouse_id}/status", response_model=APIResponse)
def update_animal_status(
    mouse_id: str,
    status_update: AnimalStatusUpdate,
) -> APIResponse:
    try:
        updated = animal_service.update_status(mouse_id, status_update)
    except Exception as exc:
        raise_database_http_exception(exc)
    if updated is None:
        raise HTTPException(status_code=404, detail="animal not found")
    return APIResponse(message="animal status updated", data=updated)


@router.patch("/{mouse_id}/stage", response_model=APIResponse)
def update_animal_stage(
    mouse_id: str,
    stage_update: AnimalStageUpdate,
) -> APIResponse:
    try:
        updated = animal_service.update_stage(mouse_id, stage_update)
    except Exception as exc:
        raise_database_http_exception(exc)
    if updated is None:
        raise HTTPException(status_code=404, detail="animal not found")
    return APIResponse(message="animal stage updated", data=updated)


@router.patch("/{mouse_id}/device", response_model=APIResponse)
def update_animal_device_binding(
    mouse_id: str,
    binding_update: AnimalDeviceBindingUpdate,
) -> APIResponse:
    try:
        updated = animal_service.update_device_binding(mouse_id, binding_update)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise_database_http_exception(exc)
    if updated is None:
        raise HTTPException(status_code=404, detail="animal not found")
    return APIResponse(message="animal device binding updated", data=updated)


@router.delete("/{mouse_id}", response_model=APIResponse)
def delete_animal(mouse_id: str) -> APIResponse:
    try:
        deleted = animal_service.delete_animal(mouse_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if deleted is None:
        raise HTTPException(status_code=404, detail="animal not found")
    return APIResponse(message="animal deleted", data=deleted)


@router.get("/{mouse_id}/status-history", response_model=APIResponse)
def get_status_history(
    mouse_id: str,
    limit: int = Query(default=50, ge=1, le=500),
) -> APIResponse:
    try:
        animal = animal_service.get_animal(mouse_id)
        if animal is None:
            raise HTTPException(status_code=404, detail="animal not found")
        history = animal_service.get_status_history(mouse_id, limit)
    except HTTPException:
        raise
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=history)
