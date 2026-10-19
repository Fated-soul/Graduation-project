from __future__ import annotations

import math
import random
import sys
from datetime import datetime, timedelta, timezone

from psycopg2.extras import Json, execute_values

from backend.database.connection import DatabaseConnectionError, get_connection
from backend.database.init_db import init_database

MOUSE_ID = "MOUSE-001"
DEVICE_ID = "ESP32-001"


def _anchor() -> datetime:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    return now


def _ensure_demo_subject(cursor, anchor: datetime) -> None:
    cursor.execute(
        """
        INSERT INTO animals (
            mouse_id, current_status, experiment_name, experiment_stage
        )
        VALUES (%s, 'attention', '行为无助造模', '应激阶段')
        ON CONFLICT (mouse_id)
        DO UPDATE SET
            current_status = 'attention',
            experiment_name = '行为无助造模',
            experiment_stage = '应激阶段',
            updated_at = CURRENT_TIMESTAMP
        """,
        (MOUSE_ID,),
    )
    cursor.execute(
        """
        INSERT INTO devices (
            device_id, device_type, device_name, mouse_id,
            online, voltage, current, last_seen
        )
        VALUES (%s, 'esp32_s3', '1号实验箱 ESP32-S3', %s, TRUE, 5.04, 0.42, %s)
        ON CONFLICT (device_id)
        DO UPDATE SET
            device_type = 'esp32_s3',
            device_name = '1号实验箱 ESP32-S3',
            mouse_id = EXCLUDED.mouse_id,
            online = TRUE,
            voltage = 5.04,
            current = 0.42,
            last_seen = EXCLUDED.last_seen,
            updated_at = CURRENT_TIMESTAMP
        """,
        (DEVICE_ID, MOUSE_ID, anchor),
    )


def _seed_vital_signs(cursor, anchor: datetime) -> int:
    rng = random.Random(20260724)
    rows = []
    for minute in range(360, -1, -1):
        recorded_at = anchor - timedelta(minutes=minute)
        progress = (360 - minute) / 360
        wave = math.sin(progress * math.tau * 3)
        body_temperature = round(37.05 + 0.62 * progress + 0.08 * wave + rng.uniform(-0.035, 0.035), 2)
        heart_rate = round(418 + 34 * progress + 9 * wave + rng.uniform(-3.5, 3.5), 0)
        blood_oxygen = round(98.2 - 1.2 * progress + 0.25 * math.cos(progress * math.tau * 2) + rng.uniform(-0.18, 0.18), 1)
        rows.append(
            (
                MOUSE_ID,
                DEVICE_ID,
                body_temperature,
                heart_rate,
                blood_oxygen,
                recorded_at,
            )
        )

    execute_values(
        cursor,
        """
        INSERT INTO vital_signs (
            mouse_id, device_id, body_temperature,
            heart_rate, blood_oxygen, recorded_at
        )
        VALUES %s
        ON CONFLICT (mouse_id, device_id, recorded_at)
        DO UPDATE SET
            body_temperature = EXCLUDED.body_temperature,
            heart_rate = EXCLUDED.heart_rate,
            blood_oxygen = EXCLUDED.blood_oxygen
        """,
        rows,
        page_size=1000,
    )
    return len(rows)


def _seed_environment(cursor, anchor: datetime) -> int:
    rng = random.Random(20260725)
    rows = []
    for step in range(72, -1, -1):
        recorded_at = anchor - timedelta(minutes=step * 5)
        progress = (72 - step) / 72
        temperature = round(23.4 + 0.5 * math.sin(progress * math.tau * 2) + rng.uniform(-0.12, 0.12), 2)
        humidity = round(56.5 + 2.0 * math.cos(progress * math.tau * 1.5) + rng.uniform(-0.4, 0.4), 1)
        voltage = round(5.03 + rng.uniform(-0.04, 0.04), 2)
        current = round(0.42 + rng.uniform(-0.03, 0.03), 2)
        rows.append((MOUSE_ID, DEVICE_ID, temperature, humidity, False, voltage, current, recorded_at))

    execute_values(
        cursor,
        """
        INSERT INTO telemetry (
            mouse_id, device_id, temperature, humidity,
            is_dark, voltage, current, recorded_at
        )
        VALUES %s
        ON CONFLICT (mouse_id, device_id, recorded_at)
        DO UPDATE SET
            temperature = EXCLUDED.temperature,
            humidity = EXCLUDED.humidity,
            is_dark = EXCLUDED.is_dark,
            voltage = EXCLUDED.voltage,
            current = EXCLUDED.current
        """,
        rows,
        page_size=500,
    )
    return len(rows)


def _seed_status_history(cursor, anchor: datetime) -> int:
    cursor.execute(
        """
        DELETE FROM animal_status_history
        WHERE mouse_id = %s
          AND reason LIKE '演示数据:%%'
        """,
        (MOUSE_ID,),
    )
    rows = [
        (MOUSE_ID, "normal", "演示数据: 入组后生命体征稳定", anchor - timedelta(hours=5, minutes=30)),
        (MOUSE_ID, "normal", "演示数据: 进入行为无助造模适应观察", anchor - timedelta(hours=3, minutes=20)),
        (MOUSE_ID, "attention", "演示数据: 应激阶段心率波动增大", anchor - timedelta(minutes=42)),
        (MOUSE_ID, "attention", "演示数据: Agent 综合评分进入关注区间", anchor - timedelta(minutes=8)),
    ]
    execute_values(
        cursor,
        """
        INSERT INTO animal_status_history (
            mouse_id, status, reason, recorded_at
        )
        VALUES %s
        """,
        rows,
        page_size=100,
    )
    return len(rows)


def _seed_agent_analysis(cursor, anchor: datetime) -> int:
    cursor.execute(
        """
        DELETE FROM agent_analysis_results
        WHERE mouse_id = %s
          AND analysis_source = 'recording_demo'
        """,
        (MOUSE_ID,),
    )
    factors = ["体温轻度上升", "心率波动增大", "视觉活动轨迹可用", "应激阶段"]
    cursor.execute(
        """
        INSERT INTO agent_analysis_results (
            mouse_id, risk_score, risk_level, summary,
            vital_analysis, behavior_analysis, stage_analysis,
            risk_analysis, recommendation, control_strategy, factors,
            analysis_source, model_provider, model_name, analyzed_at
        )
        VALUES (
            %s, 57, '关注', %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            'recording_demo', 'demo', 'recording-demo-agent', %s
        )
        """,
        (
            MOUSE_ID,
            "MOUSE-001 当前处于行为无助造模应激阶段，生命体征整体可用。近 2 小时体温和心率呈轻度上行趋势，血氧仍在安全范围内，建议保持重点观察。",
            "生命体征曲线显示体温由约 37.1 ℃ 缓慢升至 37.7 ℃ 左右，心率由约 420 bpm 上升至 450 bpm 附近，血氧维持在 97% 左右，暂未达到高风险阈值。",
            "视觉关键点数据已入库，MOUSE-001 对应 animal0。最近导入数据包含 2330 帧行为特征，可用于分析中心点轨迹、帧间移动距离和关键点置信度。",
            "当前造模阶段为应激阶段，生命体征出现轻度波动符合阶段预期，但仍需观察是否持续升高。",
            "综合生命体征、阶段信息和视觉行为数据，当前风险处于关注区间，尚不建议判定为高风险。",
            "保持 ESP32-001 在线监测，录屏演示时可重点展示体温、心率、血氧曲线和 Agent 关注结论；暂不建议额外增加刺激强度。",
            "维持当前刺激策略，若连续 10 分钟体温超过 38.2 ℃ 或心率超过 470 bpm，再考虑暂停自动刺激并进入人工复核。",
            Json(factors),
            anchor - timedelta(seconds=20),
        ),
    )
    return 1


def seed_recording_data() -> bool:
    if not init_database():
        return False

    connection = None
    cursor = None
    try:
        connection = get_connection(raise_errors=True)
        cursor = connection.cursor()
        anchor = _anchor()

        _ensure_demo_subject(cursor, anchor)
        vital_rows = _seed_vital_signs(cursor, anchor)
        telemetry_rows = _seed_environment(cursor, anchor)
        status_rows = _seed_status_history(cursor, anchor)
        analysis_rows = _seed_agent_analysis(cursor, anchor)

        connection.commit()
        print("recording demo data seeded successfully")
        print(
            {
                "mouse_id": MOUSE_ID,
                "device_id": DEVICE_ID,
                "vital_signs": vital_rows,
                "telemetry": telemetry_rows,
                "status_history": status_rows,
                "agent_analysis_results": analysis_rows,
                "stimulation_events": "unchanged",
            }
        )
        return True
    except DatabaseConnectionError as exc:
        print("database connection failed:", exc)
        return False
    except Exception as exc:
        if connection is not None:
            connection.rollback()
        print("recording demo data seed failed:", exc)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    sys.exit(0 if seed_recording_data() else 1)
