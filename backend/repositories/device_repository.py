from __future__ import annotations

from typing import Any

from backend.database.connection import get_dict_cursor
from backend.schemas.device import DeviceCreate, DeviceStatusUpdate

DEVICE_FIELDS = """
    id, device_id, device_type, device_name, mouse_id, online,
    voltage, current, last_seen, created_at, updated_at
"""


def _with_online_status(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    data = dict(row)
    data["online_status"] = "在线" if data.get("online") else "离线"
    return data


def get_devices(
    online: bool | None = None,
    device_type: str | None = None,
) -> list[dict[str, Any]]:
    sql = f"SELECT {DEVICE_FIELDS} FROM devices"
    conditions: list[str] = []
    params: list[Any] = []

    if online is not None:
        conditions.append("online = %s")
        params.append(online)
    if device_type is not None:
        conditions.append("device_type = %s")
        params.append(device_type)

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY device_id ASC"

    with get_dict_cursor() as cursor:
        cursor.execute(sql, params)
        return [_with_online_status(row) for row in cursor.fetchall()]


def get_device_by_device_id(device_id: str) -> dict[str, Any] | None:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {DEVICE_FIELDS}
            FROM devices
            WHERE device_id = %s
            """,
            (device_id,),
        )
        return _with_online_status(cursor.fetchone())


def create_device(device: DeviceCreate) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            INSERT INTO devices (
                device_id, device_type, device_name, mouse_id,
                online, voltage, current, last_seen
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING {DEVICE_FIELDS}
            """,
            (
                device.device_id,
                device.device_type,
                device.device_name,
                device.mouse_id,
                device.online,
                device.voltage,
                device.current,
                device.last_seen,
            ),
        )
        return _with_online_status(cursor.fetchone())


def delete_device(device_id: str) -> dict[str, Any] | None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            SELECT {DEVICE_FIELDS}
            FROM devices
            WHERE device_id = %s
            FOR UPDATE
            """,
            (device_id,),
        )
        device = _with_online_status(cursor.fetchone())
        if device is None:
            return None

        # 设备历史数据使用外键保护；删除设备前先清理该设备产生的数据。
        for table in (
            "stimulation_settings",
            "control_commands",
            "stimulation_events",
            "vital_signs",
            "telemetry",
        ):
            cursor.execute(
                f"DELETE FROM {table} WHERE device_id = %s",
                (device_id,),
            )

        cursor.execute(
            """
            DELETE FROM devices
            WHERE device_id = %s
            """,
            (device_id,),
        )
        return device


def update_device_status(
    device_id: str,
    status_update: DeviceStatusUpdate,
) -> dict[str, Any] | None:
    assignments: list[str] = []
    params: list[Any] = []

    if status_update.online is not None:
        assignments.append("online = %s")
        params.append(status_update.online)
    if status_update.voltage is not None:
        assignments.append("voltage = %s")
        params.append(status_update.voltage)
    if status_update.current is not None:
        assignments.append("current = %s")
        params.append(status_update.current)
    if status_update.last_seen is not None:
        assignments.append("last_seen = %s")
        params.append(status_update.last_seen)
    elif status_update.online is not None:
        assignments.append("last_seen = CURRENT_TIMESTAMP")

    assignments.append("updated_at = CURRENT_TIMESTAMP")
    params.append(device_id)

    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            UPDATE devices
            SET {", ".join(assignments)}
            WHERE device_id = %s
            RETURNING {DEVICE_FIELDS}
            """,
            params,
        )
        return _with_online_status(cursor.fetchone())


def update_device_from_telemetry(
    device_id: str,
    voltage: float | None = None,
    current: float | None = None,
) -> dict[str, Any] | None:
    assignments = [
        "online = TRUE",
        "last_seen = CURRENT_TIMESTAMP",
        "updated_at = CURRENT_TIMESTAMP",
    ]
    params: list[Any] = []

    if voltage is not None:
        assignments.append("voltage = %s")
        params.append(voltage)
    if current is not None:
        assignments.append("current = %s")
        params.append(current)

    params.append(device_id)

    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            UPDATE devices
            SET {", ".join(assignments)}
            WHERE device_id = %s
            RETURNING {DEVICE_FIELDS}
            """,
            params,
        )
        return _with_online_status(cursor.fetchone())
