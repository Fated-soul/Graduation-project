from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.database.connection import get_dict_cursor
from backend.schemas.vital_signs import VitalSignsCreate

VITAL_SIGNS_FIELDS = """
    id, mouse_id, device_id, body_temperature,
    heart_rate, blood_oxygen, recorded_at, created_at
"""


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_dict(row: Any | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def create_vital_signs(vital_signs: VitalSignsCreate) -> dict[str, Any]:
    recorded_at = _normalize_datetime(vital_signs.recorded_at)
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            INSERT INTO vital_signs (
                mouse_id, device_id, body_temperature,
                heart_rate, blood_oxygen, recorded_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING {VITAL_SIGNS_FIELDS}
            """,
            (
                vital_signs.mouse_id,
                vital_signs.device_id,
                vital_signs.body_temperature,
                vital_signs.heart_rate,
                vital_signs.blood_oxygen,
                recorded_at,
            ),
        )
        return dict(cursor.fetchone())


def get_latest_vital_signs(mouse_id: str) -> dict[str, Any] | None:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {VITAL_SIGNS_FIELDS}
            FROM vital_signs
            WHERE mouse_id = %s
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (mouse_id,),
        )
        return _to_dict(cursor.fetchone())


def get_vital_signs_history(
    mouse_id: str,
    hours: int = 1,
    limit: int = 500,
) -> list[dict[str, Any]]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {VITAL_SIGNS_FIELDS}
            FROM vital_signs
            WHERE mouse_id = %s
              AND recorded_at >= CURRENT_TIMESTAMP - (%s::integer * INTERVAL '1 hour')
            ORDER BY recorded_at ASC
            LIMIT %s
            """,
            (mouse_id, hours, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_device_vital_signs(
    device_id: str,
    hours: int = 1,
    limit: int = 500,
) -> list[dict[str, Any]]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {VITAL_SIGNS_FIELDS}
            FROM vital_signs
            WHERE device_id = %s
              AND recorded_at >= CURRENT_TIMESTAMP - (%s::integer * INTERVAL '1 hour')
            ORDER BY recorded_at ASC
            LIMIT %s
            """,
            (device_id, hours, limit),
        )
        return [dict(row) for row in cursor.fetchall()]
