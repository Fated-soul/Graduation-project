from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.database.connection import get_dict_cursor
from backend.schemas.telemetry import TelemetryCreate

TELEMETRY_FIELDS = """
    id, mouse_id, device_id, temperature, humidity, is_dark,
    voltage, current, recorded_at, created_at
"""


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_dict(row: Any | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def create_telemetry(telemetry: TelemetryCreate) -> dict[str, Any]:
    recorded_at = _normalize_datetime(telemetry.recorded_at)
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            INSERT INTO telemetry (
                mouse_id, device_id, temperature,
                humidity, is_dark, voltage, current, recorded_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {TELEMETRY_FIELDS}
            """,
            (
                telemetry.mouse_id,
                telemetry.device_id,
                telemetry.temperature,
                telemetry.humidity,
                telemetry.is_dark,
                telemetry.voltage,
                telemetry.current,
                recorded_at,
            ),
        )
        return dict(cursor.fetchone())


def get_latest_telemetry(mouse_id: str) -> dict[str, Any] | None:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {TELEMETRY_FIELDS}
            FROM telemetry
            WHERE mouse_id = %s
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (mouse_id,),
        )
        return _to_dict(cursor.fetchone())


def get_telemetry_history(
    mouse_id: str,
    hours: int = 1,
    limit: int = 500,
) -> list[dict[str, Any]]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {TELEMETRY_FIELDS}
            FROM telemetry
            WHERE mouse_id = %s
              AND recorded_at >= CURRENT_TIMESTAMP - (%s::integer * INTERVAL '1 hour')
            ORDER BY recorded_at ASC
            LIMIT %s
            """,
            (mouse_id, hours, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_device_telemetry(
    device_id: str,
    hours: int = 1,
    limit: int = 500,
) -> list[dict[str, Any]]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {TELEMETRY_FIELDS}
            FROM telemetry
            WHERE device_id = %s
              AND recorded_at >= CURRENT_TIMESTAMP - (%s::integer * INTERVAL '1 hour')
            ORDER BY recorded_at ASC
            LIMIT %s
            """,
            (device_id, hours, limit),
        )
        return [dict(row) for row in cursor.fetchall()]
