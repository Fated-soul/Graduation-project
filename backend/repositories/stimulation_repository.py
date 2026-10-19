from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.database.connection import get_dict_cursor
from backend.schemas.stimulation import StimulationEventCreate

STIMULATION_FIELDS = """
    id, mouse_id, device_id, event_type, duration_ms,
    intensity, is_active, next_interval_ms, next_trigger_at,
    started_at, ended_at, created_at
"""

STIMULATION_SETTING_FIELDS = """
    id, mouse_id, device_id, event_type, enabled,
    min_interval_ms, max_interval_ms, min_duration_ms, max_duration_ms,
    created_at, updated_at
"""


def _normalize_datetime(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def create_stimulation_event(event: StimulationEventCreate) -> dict[str, Any]:
    received_at = datetime.now(timezone.utc)
    started_at = _normalize_datetime(event.started_at) if event.started_at is not None else received_at
    ended_at = started_at + timedelta(milliseconds=event.duration_ms)
    next_trigger_at = (
        received_at + timedelta(milliseconds=event.next_interval_ms)
        if event.next_interval_ms is not None
        else None
    )

    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            INSERT INTO stimulation_events (
                mouse_id, device_id, event_type, duration_ms,
                intensity, is_active, next_interval_ms, next_trigger_at,
                started_at, ended_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {STIMULATION_FIELDS}
            """,
            (
                event.mouse_id,
                event.device_id,
                event.event_type,
                event.duration_ms,
                event.intensity,
                event.is_active,
                event.next_interval_ms,
                next_trigger_at,
                started_at,
                ended_at,
            ),
        )
        return dict(cursor.fetchone())


def get_stimulation_history(
    mouse_id: str,
    event_type: str | None = None,
    hours: int = 24,
    limit: int = 100,
) -> list[dict[str, Any]]:
    conditions = [
        "mouse_id = %s",
        "started_at >= CURRENT_TIMESTAMP - (%s::integer * INTERVAL '1 hour')",
    ]
    params: list[Any] = [mouse_id, hours]

    if event_type is not None:
        conditions.append("event_type = %s")
        params.append(event_type)

    params.append(limit)

    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {STIMULATION_FIELDS}
            FROM stimulation_events
            WHERE {" AND ".join(conditions)}
            ORDER BY started_at DESC
            LIMIT %s
            """,
            params,
        )
        return [dict(row) for row in cursor.fetchall()]


def upsert_stimulation_setting(
    *,
    mouse_id: str | None,
    device_id: str,
    event_type: str,
    enabled: bool,
    min_interval_ms: int,
    max_interval_ms: int,
    min_duration_ms: int,
    max_duration_ms: int,
) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            INSERT INTO stimulation_settings (
                mouse_id, device_id, event_type, enabled,
                min_interval_ms, max_interval_ms, min_duration_ms, max_duration_ms
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (device_id, event_type)
            DO UPDATE SET
                mouse_id = EXCLUDED.mouse_id,
                enabled = EXCLUDED.enabled,
                min_interval_ms = EXCLUDED.min_interval_ms,
                max_interval_ms = EXCLUDED.max_interval_ms,
                min_duration_ms = EXCLUDED.min_duration_ms,
                max_duration_ms = EXCLUDED.max_duration_ms,
                updated_at = CURRENT_TIMESTAMP
            RETURNING {STIMULATION_SETTING_FIELDS}
            """,
            (
                mouse_id,
                device_id,
                event_type,
                enabled,
                min_interval_ms,
                max_interval_ms,
                min_duration_ms,
                max_duration_ms,
            ),
        )
        return dict(cursor.fetchone())


def get_stimulation_settings(device_id: str) -> list[dict[str, Any]]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {STIMULATION_SETTING_FIELDS}
            FROM stimulation_settings
            WHERE device_id = %s
            ORDER BY event_type ASC
            """,
            (device_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
