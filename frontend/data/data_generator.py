from __future__ import annotations

from datetime import datetime
import random

import numpy as np
import pandas as pd


def _seed_for(*parts: object) -> int:
    raw = "|".join(str(part) for part in parts)
    return sum(ord(char) for char in raw)


def _time_index(hours: int) -> pd.DatetimeIndex:
    points = {1: 13, 6: 37, 24: 97}.get(hours, max(13, hours * 6 + 1))
    return pd.date_range(end=datetime.now(), periods=points, freq=f"{max(1, hours * 60 // (points - 1))}min")


def generate_temperature_data(mouse_id: str = "MOUSE-001", hours: int = 6, refresh_count: int = 0) -> pd.Series:
    return generate_vital_sign_data(mouse_id, hours, refresh_count)["temperature"]


def generate_heart_rate_data(mouse_id: str = "MOUSE-001", hours: int = 6, refresh_count: int = 0) -> pd.Series:
    return generate_vital_sign_data(mouse_id, hours, refresh_count)["heart_rate"]


def generate_activity_data(mouse_id: str = "MOUSE-001", hours: int = 6, refresh_count: int = 0) -> pd.Series:
    return generate_vital_sign_data(mouse_id, hours, refresh_count)["activity"]


def generate_vital_sign_data(
    mouse_id: str,
    hours: int,
    refresh_count: int = 0,
) -> pd.DataFrame:
    timestamps = _time_index(hours)
    x = np.linspace(0, 1, len(timestamps))
    rng = np.random.default_rng(_seed_for(mouse_id, hours, refresh_count))

    if mouse_id == "MOUSE-002":
        temperature = 37.25 + 1.15 * x + rng.normal(0, 0.035 + 0.025 * x, len(x))
        heart_rate = 438 + 45 * x + np.sin(x * 8 * np.pi) * (8 + 14 * x) + rng.normal(0, 4.2, len(x))
        activity = 69 - 23 * x + rng.normal(0, 2.2, len(x))
    elif mouse_id in {"MOUSE-003", "MOUSE-008"}:
        temperature = 37.2 + 0.48 * x + rng.normal(0, 0.045, len(x))
        heart_rate = 426 + 28 * x + np.sin(x * 5 * np.pi) * 7 + rng.normal(0, 4.5, len(x))
        activity = 74 - 13 * x + rng.normal(0, 2.4, len(x))
    elif mouse_id == "MOUSE-006":
        temperature = 37.1 + 0.16 * np.sin(x * 3 * np.pi) + rng.normal(0, 0.035, len(x))
        heart_rate = 424 + 12 * np.sin(x * 5 * np.pi) + rng.normal(0, 4.0, len(x))
        activity = 70 + 4 * np.sin(x * 3 * np.pi) + rng.normal(0, 2.0, len(x))
    else:
        baseline_shift = (_seed_for(mouse_id) % 7) * 0.025
        temperature = 37.05 + baseline_shift + 0.16 * np.sin(x * 2 * np.pi) + rng.normal(0, 0.035, len(x))
        heart_rate = 418 + (_seed_for(mouse_id) % 19) + 10 * np.sin(x * 4 * np.pi) + rng.normal(0, 3.5, len(x))
        activity = 78 + 7 * np.sin(x * 2.5 * np.pi) + rng.normal(0, 2.0, len(x))

    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "temperature": np.round(np.clip(temperature, 36.5, 39.2), 2),
            "heart_rate": np.round(np.clip(heart_rate, 380, 520), 0).astype(float),
            "activity": np.round(np.clip(activity, 28, 94), 1),
        }
    )

    if mouse_id == "MOUSE-006":
        missing_index = frame.index[-4:-1:2]
        frame.loc[missing_index, ["temperature", "heart_rate", "activity"]] = np.nan

    return frame


def generate_environment_data(hours: int = 6, refresh_count: int = 0) -> pd.DataFrame:
    timestamps = _time_index(hours)
    x = np.linspace(0, 1, len(timestamps))
    rng = np.random.default_rng(_seed_for("environment", hours, refresh_count))
    temp = 23.4 + 0.35 * np.sin(x * 2 * np.pi) + rng.normal(0, 0.06, len(x))
    humidity = 51.5 + 2.3 * np.sin(x * 1.4 * np.pi + 0.4) + rng.normal(0, 0.35, len(x))
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "environment_temperature": np.round(temp, 1),
            "humidity": np.round(humidity, 1),
        }
    )


def generate_device_status() -> list[dict[str, object]]:
    rng = random.Random(_seed_for("device-status", datetime.now().date()))
    return [
        {"name": "ESP32-S3 控制器", "current": 6, "total": 6, "status": "在线"},
        {"name": "生命体征传感器", "current": 6, "total": 6, "status": "在线"},
        {"name": "行为监测摄像头", "current": 4, "total": 5, "status": "部分异常"},
        {"name": "环境传感器", "current": 2, "total": 2, "status": "在线"},
        {"name": "多模态数据融合", "current": None, "total": None, "status": "正常"},
        {"name": "Agent 辅助决策", "current": None, "total": None, "status": "正常"},
    ] + [
        {"name": "链路质量", "current": rng.randint(88, 96), "total": 100, "status": "在线"}
    ]


def generate_data_center_metrics(refresh_count: int = 0) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(_seed_for("data-center", refresh_count))
    timestamps = pd.date_range(end=datetime.now(), periods=24, freq="h")
    base = np.linspace(38, 62, len(timestamps)) + 8 * np.sin(np.linspace(0, 2.2 * np.pi, len(timestamps)))
    volume = np.clip(base + rng.normal(0, 2.8, len(timestamps)), 26, 78)
    trend = pd.DataFrame({"timestamp": timestamps, "采集记录": np.round(volume, 0).astype(int)})
    type_share = pd.DataFrame(
        {
            "数据类型": ["生命体征", "视觉行为", "实验环境", "刺激过程"],
            "数量": [824, 326, 132, 68],
        }
    )
    experiments = pd.DataFrame(
        {
            "实验": ["行为无助造模"],
            "动物数量": [12],
        }
    )
    devices = pd.DataFrame(
        {
            "设备": ["ESP32-002", "ESP32-001", "CAM-02", "HR-01", "ENV-01", "CAM-04"],
            "在线状态": [1, 1, 1, 1, 1, 0],
        }
    )
    return {
        "trend": trend,
        "type_share": type_share,
        "experiments": experiments,
        "devices": devices,
    }
