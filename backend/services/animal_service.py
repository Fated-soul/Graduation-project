from __future__ import annotations

from typing import Any

from backend.repositories import animal_repository
from backend.schemas.animal import (
    AnimalCreate,
    AnimalDeviceBindingUpdate,
    AnimalStageUpdate,
    AnimalStatusUpdate,
)


def list_animals(status: str | None = None) -> list[dict[str, Any]]:
    return animal_repository.get_all_animals(status=status)


def get_animal(mouse_id: str) -> dict[str, Any] | None:
    return animal_repository.get_animal_by_mouse_id(mouse_id)


def create_animal(animal: AnimalCreate) -> dict[str, Any]:
    return animal_repository.create_animal(animal)


def update_status(
    mouse_id: str,
    status_update: AnimalStatusUpdate,
) -> dict[str, Any] | None:
    return animal_repository.update_animal_status(mouse_id, status_update)


def update_stage(
    mouse_id: str,
    stage_update: AnimalStageUpdate,
) -> dict[str, Any] | None:
    return animal_repository.update_animal_stage(mouse_id, stage_update)


def update_device_binding(
    mouse_id: str,
    binding_update: AnimalDeviceBindingUpdate,
) -> dict[str, Any] | None:
    return animal_repository.update_animal_device_binding(mouse_id, binding_update)


def delete_animal(mouse_id: str) -> dict[str, Any] | None:
    return animal_repository.delete_animal(mouse_id)


def get_status_history(mouse_id: str, limit: int = 50) -> list[dict[str, Any]]:
    return animal_repository.get_animal_status_history(mouse_id, limit)
