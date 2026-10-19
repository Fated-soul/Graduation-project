from __future__ import annotations

from typing import Any

from backend.database.connection import get_dict_cursor
from backend.schemas.animal import (
    AnimalCreate,
    AnimalDeviceBindingUpdate,
    AnimalStageUpdate,
    AnimalStatusUpdate,
)

ANIMAL_FIELDS = """
    id, mouse_id, current_status, experiment_name, experiment_stage,
    created_at, updated_at
"""

DEVICE_FIELDS = """
    id, device_id, device_type, device_name, mouse_id, online,
    voltage, current, last_seen, created_at, updated_at
"""


def _to_dict(row: Any | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def get_all_animals(status: str | None = None) -> list[dict[str, Any]]:
    sql = f"SELECT {ANIMAL_FIELDS} FROM animals"
    params: list[Any] = []
    if status is not None:
        sql += " WHERE current_status = %s"
        params.append(status)
    sql += " ORDER BY mouse_id ASC"

    with get_dict_cursor() as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def get_animal_by_mouse_id(mouse_id: str) -> dict[str, Any] | None:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {ANIMAL_FIELDS}
            FROM animals
            WHERE mouse_id = %s
            """,
            (mouse_id,),
        )
        return _to_dict(cursor.fetchone())


def create_animal(animal: AnimalCreate) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            INSERT INTO animals (
                mouse_id, current_status, experiment_name, experiment_stage
            )
            VALUES (%s, %s, %s, %s)
            RETURNING {ANIMAL_FIELDS}
            """,
            (
                animal.mouse_id,
                animal.current_status,
                animal.experiment_name,
                animal.experiment_stage,
            ),
        )
        return dict(cursor.fetchone())


def update_animal_status(
    mouse_id: str,
    status_update: AnimalStatusUpdate,
) -> dict[str, Any] | None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            "SELECT id FROM animals WHERE mouse_id = %s FOR UPDATE",
            (mouse_id,),
        )
        if cursor.fetchone() is None:
            return None

        cursor.execute(
            f"""
            UPDATE animals
            SET current_status = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE mouse_id = %s
            RETURNING {ANIMAL_FIELDS}
            """,
            (status_update.status, mouse_id),
        )
        animal = dict(cursor.fetchone())

        cursor.execute(
            """
            INSERT INTO animal_status_history (mouse_id, status, reason)
            VALUES (%s, %s, %s)
            """,
            (mouse_id, status_update.status, status_update.reason),
        )
        return animal


def update_animal_stage(
    mouse_id: str,
    stage_update: AnimalStageUpdate,
) -> dict[str, Any] | None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            UPDATE animals
            SET experiment_stage = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE mouse_id = %s
            RETURNING {ANIMAL_FIELDS}
            """,
            (stage_update.experiment_stage, mouse_id),
        )
        return _to_dict(cursor.fetchone())


def update_animal_device_binding(
    mouse_id: str,
    binding_update: AnimalDeviceBindingUpdate,
) -> dict[str, Any] | None:
    device_id = binding_update.device_id.strip() if binding_update.device_id else None

    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            SELECT {ANIMAL_FIELDS}
            FROM animals
            WHERE mouse_id = %s
            FOR UPDATE
            """,
            (mouse_id,),
        )
        if cursor.fetchone() is None:
            return None

        if device_id is not None:
            cursor.execute(
                f"""
                SELECT {DEVICE_FIELDS}
                FROM devices
                WHERE device_id = %s
                FOR UPDATE
                """,
                (device_id,),
            )
            if cursor.fetchone() is None:
                raise LookupError("device not found")

        if device_id is None:
            cursor.execute(
                """
                UPDATE devices
                SET mouse_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE mouse_id = %s
                RETURNING device_id
                """,
                (mouse_id,),
            )
        else:
            cursor.execute(
                """
                UPDATE devices
                SET mouse_id = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE mouse_id = %s
                  AND device_id <> %s
                RETURNING device_id
                """,
                (mouse_id, device_id),
            )
        unbound_device_ids = [row["device_id"] for row in cursor.fetchall()]

        selected_device = None
        if device_id is not None:
            cursor.execute(
                f"""
                UPDATE devices
                SET mouse_id = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE device_id = %s
                RETURNING {DEVICE_FIELDS}
                """,
                (mouse_id, device_id),
            )
            selected_device = _to_dict(cursor.fetchone())

        cursor.execute(
            f"""
            UPDATE animals
            SET updated_at = CURRENT_TIMESTAMP
            WHERE mouse_id = %s
            RETURNING {ANIMAL_FIELDS}
            """,
            (mouse_id,),
        )
        animal = _to_dict(cursor.fetchone())

        return {
            "animal": animal,
            "device": selected_device,
            "unbound_device_ids": unbound_device_ids,
        }


def delete_animal(mouse_id: str) -> dict[str, Any] | None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            DELETE FROM animals
            WHERE mouse_id = %s
            RETURNING {ANIMAL_FIELDS}
            """,
            (mouse_id,),
        )
        return _to_dict(cursor.fetchone())


def get_animal_status_history(mouse_id: str, limit: int = 50) -> list[dict[str, Any]]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, mouse_id, status, reason, recorded_at, created_at
            FROM animal_status_history
            WHERE mouse_id = %s
            ORDER BY recorded_at DESC
            LIMIT %s
            """,
            (mouse_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]
