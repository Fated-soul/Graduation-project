from __future__ import annotations

from typing import Any

from backend.database.connection import get_dict_cursor
from backend.schemas.control_command import ControlCommandCreate

CONTROL_COMMAND_FIELDS = """
    id, command_id, mouse_id, device_id, command_type, duration_ms,
    intensity, status, requested_at, dispatched_at, acknowledged_at,
    error_message, created_at, updated_at
"""


def create_control_command(command: ControlCommandCreate, command_id: str) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            INSERT INTO control_commands (
                command_id, mouse_id, device_id, command_type,
                duration_ms, intensity
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING {CONTROL_COMMAND_FIELDS}
            """,
            (
                command_id,
                command.mouse_id,
                command.device_id,
                command.command_type,
                command.duration_ms,
                command.intensity,
            ),
        )
        return dict(cursor.fetchone())


def get_control_command(command_id: str) -> dict[str, Any] | None:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {CONTROL_COMMAND_FIELDS}
            FROM control_commands
            WHERE command_id = %s
            """,
            (command_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def list_control_commands(
    device_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if device_id is not None:
        conditions.append("device_id = %s")
        params.append(device_id)
    if status is not None:
        conditions.append("status = %s")
        params.append(status)

    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {CONTROL_COMMAND_FIELDS}
            FROM control_commands
            {where_sql}
            ORDER BY requested_at DESC
            LIMIT %s
            """,
            params,
        )
        return [dict(row) for row in cursor.fetchall()]


def mark_command_sent(command_id: str) -> dict[str, Any] | None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            UPDATE control_commands
            SET status = 'sent',
                dispatched_at = CURRENT_TIMESTAMP,
                error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE command_id = %s
            RETURNING {CONTROL_COMMAND_FIELDS}
            """,
            (command_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def mark_command_failed(command_id: str, error_message: str) -> dict[str, Any] | None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            UPDATE control_commands
            SET status = 'failed',
                acknowledged_at = CURRENT_TIMESTAMP,
                error_message = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE command_id = %s
            RETURNING {CONTROL_COMMAND_FIELDS}
            """,
            (error_message, command_id),
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def acknowledge_command(
    command_id: str,
    status: str,
    message: str | None = None,
) -> dict[str, Any] | None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            UPDATE control_commands
            SET status = %s,
                acknowledged_at = CURRENT_TIMESTAMP,
                error_message = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE command_id = %s
            RETURNING {CONTROL_COMMAND_FIELDS}
            """,
            (status, message, command_id),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
