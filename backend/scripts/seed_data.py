from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta, timezone

from backend.database.connection import DatabaseConnectionError, get_connection
from backend.database.init_db import init_database

ANIMALS = [
    ("MOUSE-001", "行为无助造模", "适应阶段", "normal"),
    ("MOUSE-002", "行为无助造模", "应激阶段", "high_risk"),
    ("MOUSE-003", "行为无助造模", "行为测试阶段", "attention"),
    ("MOUSE-004", "行为无助造模", "观察阶段", "normal"),
    ("MOUSE-005", "行为无助造模", "应激阶段", "normal"),
    ("MOUSE-006", "行为无助造模", "观察阶段", "offline"),
]

DEVICES = [
    ("ESP32-001", "esp32_s3", "1号实验箱 ESP32-S3", "MOUSE-001", True, 5.05, 0.38),
    ("ESP32-002", "esp32_s3", "2号实验箱 ESP32-S3", "MOUSE-002", True, 5.02, 0.43),
    ("ESP32-003", "esp32_s3", "3号实验箱 ESP32-S3", "MOUSE-003", True, 4.96, 0.41),
    ("ESP32-004", "esp32_s3", "4号实验箱 ESP32-S3", "MOUSE-004", True, 5.11, 0.35),
    ("ESP32-005", "esp32_s3", "5号实验箱 ESP32-S3", "MOUSE-005", True, 4.89, 0.52),
    ("ESP32-006", "esp32_s3", "6号实验箱 ESP32-S3", "MOUSE-006", False, 4.81, 0.31),
]


def _seed_anchor() -> datetime:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    return now.replace(minute=now.minute - now.minute % 5)


def _insert_animals(cursor) -> None:
    for mouse_id, experiment_name, experiment_stage, current_status in ANIMALS:
        cursor.execute(
            """
            INSERT INTO animals (
                mouse_id, experiment_name, experiment_stage, current_status
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (mouse_id) DO NOTHING
            """,
            (mouse_id, experiment_name, experiment_stage, current_status),
        )
        cursor.execute(
            """
            INSERT INTO animal_status_history (mouse_id, status, reason)
            SELECT %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1
                FROM animal_status_history
                WHERE mouse_id = %s
                  AND status = %s
                  AND reason = %s
            )
            """,
            (
                mouse_id,
                current_status,
                "系统初始化状态",
                mouse_id,
                current_status,
                "系统初始化状态",
            ),
        )


def _insert_devices(cursor, anchor: datetime) -> None:
    for device_id, device_type, device_name, mouse_id, online, voltage, current in DEVICES:
        last_seen = anchor if online else anchor - timedelta(minutes=35)
        cursor.execute(
            """
            INSERT INTO devices (
                device_id, device_type, device_name, mouse_id,
                online, voltage, current, last_seen
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (device_id) DO NOTHING
            """,
            (
                device_id,
                device_type,
                device_name,
                mouse_id,
                online,
                voltage,
                current,
                last_seen,
            ),
        )


def _insert_telemetry(cursor, anchor: datetime) -> None:
    """环境/设备遥测：每 5 分钟一条。temperature 表示环境温度。"""

    rng = random.Random(20260707)
    profiles = {
        "MOUSE-001": ("ESP32-001", 23.5, 55.0, False),
        "MOUSE-002": ("ESP32-002", 24.0, 61.0, True),
        "MOUSE-003": ("ESP32-003", 23.8, 58.0, False),
    }

    timestamps = [anchor - timedelta(minutes=5 * offset) for offset in range(12, -1, -1)]
    for mouse_id, (device_id, base_env_temp, base_humidity, is_dark) in profiles.items():
        for recorded_at in timestamps:
            environment_temperature = round(base_env_temp + rng.uniform(-0.5, 0.5), 2)
            humidity = round(base_humidity + rng.uniform(-1.2, 1.2), 1)
            voltage = round(5.0 + rng.uniform(-0.16, 0.16), 2)
            current = round(0.42 + rng.uniform(-0.08, 0.08), 2)
            cursor.execute(
                """
                INSERT INTO telemetry (
                    mouse_id, device_id, temperature, humidity,
                    is_dark, voltage, current, recorded_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (mouse_id, device_id, recorded_at) DO NOTHING
                """,
                (
                    mouse_id,
                    device_id,
                    environment_temperature,
                    humidity,
                    is_dark,
                    voltage,
                    current,
                    recorded_at,
                ),
            )


def _insert_vital_signs(cursor, anchor: datetime) -> None:
    """小鼠生命体征：每 1 分钟一条，和 telemetry 不同频。"""

    rng = random.Random(20260718)
    profiles = {
        "MOUSE-001": ("ESP32-001", 37.2, 420, 98.0, 0.0),
        "MOUSE-002": ("ESP32-002", 37.35, 450, 95.5, 1.05),
        "MOUSE-003": ("ESP32-003", 37.8, 438, 97.0, 0.25),
    }

    timestamps = [anchor - timedelta(minutes=offset) for offset in range(60, -1, -1)]
    for mouse_id, (device_id, base_body_temp, base_heart_rate, base_blood_oxygen, temp_rise) in profiles.items():
        for index, recorded_at in enumerate(timestamps):
            progress = index / max(1, len(timestamps) - 1)
            body_temperature = round(base_body_temp + temp_rise * progress + rng.uniform(-0.04, 0.04), 2)
            heart_rate = round(
                base_heart_rate
                + (35 * progress if mouse_id == "MOUSE-002" else 8 * progress)
                + rng.uniform(-4, 4),
                0,
            )
            blood_oxygen = round(
                base_blood_oxygen
                - (2.0 * progress if mouse_id == "MOUSE-002" else 0.3 * progress)
                + rng.uniform(-0.3, 0.3),
                1,
            )
            cursor.execute(
                """
                INSERT INTO vital_signs (
                    mouse_id, device_id, body_temperature,
                    heart_rate, blood_oxygen, recorded_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (mouse_id, device_id, recorded_at) DO NOTHING
                """,
                (
                    mouse_id,
                    device_id,
                    body_temperature,
                    heart_rate,
                    blood_oxygen,
                    recorded_at,
                ),
            )


def _insert_stimulation_events(cursor, anchor: datetime) -> None:
    events = [
        ("MOUSE-002", "ESP32-002", "electric_shock", 1500, None, anchor - timedelta(minutes=25)),
        ("MOUSE-003", "ESP32-003", "flash", 3000, None, anchor - timedelta(minutes=40)),
        ("MOUSE-001", "ESP32-001", "noise", 3000, None, anchor - timedelta(minutes=15)),
    ]

    for mouse_id, device_id, event_type, duration_ms, intensity, started_at in events:
        ended_at = started_at + timedelta(milliseconds=duration_ms)
        cursor.execute(
            """
            UPDATE stimulation_events
            SET device_id = %s,
                duration_ms = %s,
                intensity = %s,
                started_at = %s,
                ended_at = %s
            WHERE id = (
                SELECT id
                FROM stimulation_events
                WHERE mouse_id = %s
                  AND event_type = %s
                ORDER BY started_at DESC
                LIMIT 1
            )
            """,
            (
                device_id,
                duration_ms,
                intensity,
                started_at,
                ended_at,
                mouse_id,
                event_type,
            ),
        )
        if cursor.rowcount:
            continue

        cursor.execute(
            """
            INSERT INTO stimulation_events (
                mouse_id, device_id, event_type, duration_ms,
                intensity, started_at, ended_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                mouse_id,
                device_id,
                event_type,
                duration_ms,
                intensity,
                started_at,
                ended_at,
            ),
        )


def _count_table(cursor, table_name: str) -> int:
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return int(cursor.fetchone()[0])


def seed_data() -> bool:
    if not init_database():
        return False

    connection = None
    cursor = None
    try:
        connection = get_connection(raise_errors=True)
        cursor = connection.cursor()
        anchor = _seed_anchor()

        _insert_animals(cursor)
        _insert_devices(cursor, anchor)
        _insert_telemetry(cursor, anchor)
        _insert_vital_signs(cursor, anchor)
        _insert_stimulation_events(cursor, anchor)

        connection.commit()

        counts = {
            "animals": _count_table(cursor, "animals"),
            "devices": _count_table(cursor, "devices"),
            "telemetry": _count_table(cursor, "telemetry"),
            "vital_signs": _count_table(cursor, "vital_signs"),
            "stimulation_events": _count_table(cursor, "stimulation_events"),
            "animal_status_history": _count_table(cursor, "animal_status_history"),
        }
        print("initial research data seeded successfully")
        for table_name, count in counts.items():
            print(f"{table_name}: {count}")
        return True
    except DatabaseConnectionError as exc:
        print("seed data connection error:", exc)
        return False
    except Exception as exc:
        if connection is not None:
            connection.rollback()
        print("seed data error:", exc)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    sys.exit(0 if seed_data() else 1)
