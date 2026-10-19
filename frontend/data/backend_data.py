from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import pandas as pd

from data.data_generator import (
    generate_data_center_metrics,
    generate_environment_data,
    generate_vital_sign_data,
)
from data.mock_data import ANIMALS as MOCK_ANIMALS
from data.mock_data import AGENT_ANALYSIS as MOCK_AGENT_ANALYSIS
from data.mock_data import DEVICES as MOCK_DEVICES
from data.mock_data import EXPERIMENTS as MOCK_EXPERIMENTS
from utils.api_client import api_data, api_request, backend_health, get_api_base_url, mock_fallback_enabled

STATUS_LABELS = {
    "normal": "正常",
    "attention": "关注",
    "high_risk": "高风险",
    "offline": "离线",
}

STAGE_PROGRESS = {
    "准备阶段": 15,
    "适应阶段": 30,
    "应激阶段": 58,
    "行为测试阶段": 76,
    "观察阶段": 82,
    "完成": 100,
}

VITAL_COLUMNS = ["timestamp", "temperature", "heart_rate", "blood_oxygen", "activity"]
ENVIRONMENT_COLUMNS = ["timestamp", "environment_temperature", "humidity"]


def is_backend_available() -> bool:
    health = backend_health()
    return bool(health and health.get("database") == "connected")


def get_connection_label() -> str:
    if is_backend_available():
        return "研究数据已连接"
    return "研究数据服务未连接"


def _first_value(*values: Any, default: Any = None) -> Any:
    for value in values:
        if value is not None:
            return value
    return default


def _parse_backend_datetime(values: Any) -> pd.Series:
    return pd.to_datetime(values, format="mixed")


def _empty_frame(columns: list[str] | pd.Index) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _mock_vital_frame(mouse_id: str, hours: int, refresh_count: int) -> pd.DataFrame:
    frame = generate_vital_sign_data(mouse_id, hours, refresh_count)
    frame["blood_oxygen"] = 97.0
    return frame


def get_animals() -> list[dict[str, Any]]:
    raw_animals = api_data("/api/animals")
    raw_devices = api_data("/api/devices")
    if not isinstance(raw_animals, list) or not isinstance(raw_devices, list):
        return [dict(animal) for animal in MOCK_ANIMALS] if mock_fallback_enabled() else []

    devices_by_mouse: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for device in raw_devices:
        if device.get("mouse_id"):
            devices_by_mouse[str(device.get("mouse_id"))].append(device)

    animals: list[dict[str, Any]] = []
    for animal in raw_animals:
        mouse_id = str(animal["mouse_id"])
        latest_telemetry = api_data(f"/api/telemetry/latest/{mouse_id}") or {}
        latest_vital_signs = api_data(f"/api/vital-signs/latest/{mouse_id}") or {}
        bound_devices = devices_by_mouse.get(mouse_id, [])
        primary_device = next((device for device in bound_devices if device.get("online")), bound_devices[0] if bound_devices else {})
        device_ids = ", ".join(str(device.get("device_id")) for device in bound_devices if device.get("device_id"))
        status = str(animal.get("current_status", "normal"))
        created_at = str(animal.get("created_at", ""))[:16].replace("T", " ")

        body_temperature = latest_vital_signs.get("body_temperature")
        heart_rate = latest_vital_signs.get("heart_rate")
        blood_oxygen = latest_vital_signs.get("blood_oxygen")
        environment_temperature = latest_telemetry.get("temperature")

        animals.append(
            {
                "id": mouse_id,
                "mouse_id": mouse_id,
                "device_id": primary_device.get("device_id"),
                "device_ids": device_ids,
                "experiment": "行为无助造模",
                "stage": animal.get("experiment_stage") or "",
                # 兼容旧图表/表格：temperature 在前端仍表示“小鼠体温”，数据库 telemetry.temperature 表示环境温度。
                "temperature": body_temperature,
                "body_temperature": body_temperature,
                "environment_temperature": environment_temperature,
                "heart_rate": heart_rate,
                "blood_oxygen": blood_oxygen,
                "humidity": latest_telemetry.get("humidity"),
                "is_dark": latest_telemetry.get("is_dark"),
                "voltage": latest_telemetry.get("voltage", primary_device.get("voltage")),
                "current": latest_telemetry.get("current", primary_device.get("current")),
                "activity": None,
                "risk_level": STATUS_LABELS.get(status, status),
                "status_code": status,
                "online": any(bool(device.get("online")) for device in bound_devices) and status != "offline",
                "group_time": created_at,
                "updated_at": animal.get("updated_at"),
            }
        )

    return animals


def create_animal_record(
    mouse_id: str,
    experiment_stage: str = "准备阶段",
    current_status: str = "normal",
) -> dict[str, Any] | None:
    return api_request(
        "/api/animals",
        method="POST",
        payload={
            "mouse_id": mouse_id,
            "current_status": current_status,
            "experiment_name": "行为无助造模",
            "experiment_stage": experiment_stage,
        },
        timeout=3.0,
        return_errors=True,
    )


def update_animal_stage(mouse_id: str, experiment_stage: str) -> dict[str, Any] | None:
    return api_request(
        f"/api/animals/{mouse_id}/stage",
        method="PATCH",
        payload={"experiment_stage": experiment_stage},
        timeout=3.0,
        return_errors=True,
    )


def update_animal_device_binding(mouse_id: str, device_id: str | None) -> dict[str, Any] | None:
    return api_request(
        f"/api/animals/{mouse_id}/device",
        method="PATCH",
        payload={"device_id": device_id},
        timeout=3.0,
        return_errors=True,
    )


def delete_animal_record(mouse_id: str) -> dict[str, Any] | None:
    return api_request(
        f"/api/animals/{mouse_id}",
        method="DELETE",
        timeout=3.0,
        return_errors=True,
    )


def get_devices() -> list[dict[str, Any]]:
    raw_devices = api_data("/api/devices")
    if not isinstance(raw_devices, list):
        return [dict(device) for device in MOCK_DEVICES] if mock_fallback_enabled() else []

    devices: list[dict[str, Any]] = []
    for device in raw_devices:
        online = bool(device.get("online"))
        last_seen = str(device.get("last_seen") or "")
        devices.append(
            {
                "id": device.get("device_id"),
                "device_id": device.get("device_id"),
                "type": device.get("device_type"),
                "target": device.get("mouse_id") or "未绑定",
                "location": device.get("device_name"),
                "status": "在线" if online else "离线",
                "online": online,
                "last_seen": last_seen[:19].replace("T", " "),
                "issue": "正常" if online else "设备离线",
                "voltage": device.get("voltage"),
                "current": device.get("current"),
            }
        )
    return devices


def create_device_record(
    device_id: str,
    device_name: str,
    device_type: str = "esp32_s3",
    mouse_id: str | None = None,
) -> dict[str, Any] | None:
    payload = {
        "device_id": device_id,
        "device_type": device_type,
        "device_name": device_name,
        "mouse_id": mouse_id or None,
        "online": False,
    }
    return api_request(
        "/api/devices",
        method="POST",
        payload=payload,
        timeout=3.0,
        return_errors=True,
    )


def delete_device_record(device_id: str) -> dict[str, Any] | None:
    return api_request(
        f"/api/devices/{device_id}",
        method="DELETE",
        timeout=3.0,
        return_errors=True,
    )


def get_agent_analysis(mouse_id: str) -> dict[str, Any] | None:
    analysis = api_data(f"/api/agent/analysis-results/{mouse_id}/latest")
    if isinstance(analysis, dict):
        return analysis
    if mock_fallback_enabled():
        mock_analysis = MOCK_AGENT_ANALYSIS.get(mouse_id)
        return dict(mock_analysis) if mock_analysis else None
    return None


def _display_time(value: Any) -> str:
    if not value:
        return "-"
    try:
        timestamp = pd.to_datetime(value, utc=True)
        return timestamp.tz_convert("Asia/Shanghai").strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(value)[:16].replace("T", " ")


def _relative_time(value: Any) -> str:
    if not value:
        return "时间未记录"
    try:
        timestamp = pd.to_datetime(value, utc=True)
        seconds = max(0, int((pd.Timestamp.now(tz="UTC") - timestamp).total_seconds()))
    except (TypeError, ValueError):
        return "时间未记录"
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86_400:
        return f"{seconds // 3600} 小时前"
    return f"{seconds // 86_400} 天前"


def _record_reason(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "状态已更新"
    if text.lower() == "mock initial status":
        return "系统初始化状态"
    if text.startswith("演示数据:") or text.startswith("演示数据："):
        return text[5:].strip()
    return text


def get_risk_events(animals: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Build the review queue from current animal state and stored Agent results."""
    source_animals = animals if animals is not None else get_animals()
    events: list[dict[str, str]] = []
    for animal in source_animals:
        mouse_id = str(animal.get("id") or "")
        if not mouse_id:
            continue
        analysis = get_agent_analysis(mouse_id) or {}
        status_code = str(animal.get("status_code") or "normal")
        risk_score = int(analysis.get("risk_score") or 0)
        raw_level = str(analysis.get("risk_level") or animal.get("risk_level") or "正常")
        level = STATUS_LABELS.get(raw_level, raw_level)
        needs_review = status_code in {"attention", "high_risk", "offline"} or risk_score >= 50
        if not needs_review:
            continue

        if status_code == "offline":
            level = "数据异常"
            title = "连续观测数据不完整"
            review_status = "数据不足"
        elif status_code == "high_risk" or risk_score >= 80:
            level = "高风险"
            title = "多模态评估提示高风险"
            review_status = "待复核"
        else:
            level = "警告"
            title = "当前状态需要重点观察"
            review_status = "待复核"

        analyzed_at = analysis.get("analyzed_at") or animal.get("updated_at")
        readings = []
        if animal.get("body_temperature") is not None:
            readings.append(f"体温 {float(animal['body_temperature']):.1f} ℃")
        if animal.get("heart_rate") is not None:
            readings.append(f"心率 {float(animal['heart_rate']):.0f} bpm")
        if animal.get("blood_oxygen") is not None:
            readings.append(f"血氧 {float(animal['blood_oxygen']):.1f} %")

        events.append(
            {
                "id": f"RISK-{mouse_id}",
                "time": _display_time(analyzed_at),
                "level": level,
                "target": mouse_id,
                "description": title,
                "status": review_status,
                "agent_judgement": str(analysis.get("summary") or "当前状态由实验动物记录判定，尚未形成智能分析结论。"),
                "abnormal_data": "，".join(readings) if readings else "当前缺少可用生命体征记录",
                "advice": str(analysis.get("recommendation") or "请实验人员核对采集终端和实验动物当前状态。"),
                "ago": _relative_time(analyzed_at),
                "risk_score": str(risk_score),
            }
        )

    level_order = {"高风险": 0, "警告": 1, "数据异常": 2}
    return sorted(events, key=lambda item: (level_order.get(item["level"], 9), item["target"]))


def get_vision_summary(mouse_id: str) -> dict[str, Any]:
    summary = api_data(f"/api/vision/summary/{mouse_id}")
    return summary if isinstance(summary, dict) else {}


def get_device_groups() -> list[dict[str, Any]]:
    devices = get_devices()
    if not devices:
        return []

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for device in devices:
        grouped[str(device.get("type", "unknown"))].append(device)

    groups: list[dict[str, Any]] = []
    for device_type, items in sorted(grouped.items()):
        current = sum(1 for item in items if item.get("online"))
        total = len(items)
        groups.append(
            {
                "name": device_type,
                "current": current,
                "total": total,
                "status": "在线" if current == total else "部分异常" if current else "离线",
            }
        )
    return groups


def _series_or_default(frame: pd.DataFrame, column: str, fallback: pd.Series | float) -> pd.Series:
    if column in frame:
        series = pd.to_numeric(frame[column], errors="coerce")
    else:
        series = pd.Series([None] * len(frame))
    if isinstance(fallback, pd.Series):
        return series.fillna(fallback.reset_index(drop=True))
    return series.fillna(fallback)


def get_vital_signs_frame(
    mouse_id: str,
    hours: int,
    refresh_count: int = 0,
) -> pd.DataFrame:
    history = api_data(f"/api/vital-signs/history/{mouse_id}?hours={hours}&limit=10000")
    if not isinstance(history, list):
        if is_backend_available() or not mock_fallback_enabled():
            return _empty_frame(VITAL_COLUMNS)
        return _mock_vital_frame(mouse_id, hours, refresh_count)
    if not history:
        return _empty_frame(VITAL_COLUMNS) if is_backend_available() or not mock_fallback_enabled() else _mock_vital_frame(mouse_id, hours, refresh_count)

    frame = pd.DataFrame(history)
    frame["timestamp"] = _parse_backend_datetime(frame["recorded_at"])
    frame = frame.sort_values("timestamp").reset_index(drop=True)
    fallback = generate_vital_sign_data(mouse_id, hours, refresh_count).reset_index(drop=True)
    fallback = fallback.reindex(range(len(frame))).interpolate(limit_direction="both").ffill().bfill()

    frame["temperature"] = _series_or_default(frame, "body_temperature", fallback["temperature"])
    frame["heart_rate"] = _series_or_default(frame, "heart_rate", fallback["heart_rate"])
    frame["blood_oxygen"] = _series_or_default(frame, "blood_oxygen", 97.0)
    frame["activity"] = fallback["activity"].to_numpy()

    return frame[["timestamp", "temperature", "heart_rate", "blood_oxygen", "activity"]]


def get_telemetry_frame(
    mouse_id: str,
    hours: int,
    refresh_count: int = 0,
) -> pd.DataFrame:
    """兼容旧页面函数名：这里返回的是生命体征曲线。"""

    return get_vital_signs_frame(mouse_id, hours, refresh_count)


def get_environment_frame(
    mouse_id: str,
    hours: int,
    refresh_count: int = 0,
) -> pd.DataFrame:
    history = api_data(f"/api/telemetry/history/{mouse_id}?hours={hours}&limit=5000")
    if not isinstance(history, list):
        if is_backend_available() or not mock_fallback_enabled():
            return _empty_frame(ENVIRONMENT_COLUMNS)
        return generate_environment_data(hours, refresh_count)
    if not history:
        return _empty_frame(ENVIRONMENT_COLUMNS) if is_backend_available() or not mock_fallback_enabled() else generate_environment_data(hours, refresh_count)

    frame = pd.DataFrame(history)
    frame["timestamp"] = _parse_backend_datetime(frame["recorded_at"])
    frame["environment_temperature"] = pd.to_numeric(frame["temperature"], errors="coerce")
    frame["humidity"] = pd.to_numeric(frame["humidity"], errors="coerce")
    return frame.sort_values("timestamp")[["timestamp", "environment_temperature", "humidity"]]


def get_experiments(animals: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    source_animals = animals if animals is not None else get_animals()
    if not source_animals:
        return [dict(experiment) for experiment in MOCK_EXPERIMENTS] if mock_fallback_enabled() and not is_backend_available() else []
    if source_animals == MOCK_ANIMALS:
        return [dict(experiment) for experiment in MOCK_EXPERIMENTS]

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for animal in source_animals:
        grouped[str(animal.get("experiment") or "未命名实验")].append(animal)

    experiments: list[dict[str, Any]] = []
    for index, (name, group_animals) in enumerate(sorted(grouped.items()), start=1):
        stage_counter = Counter(str(animal.get("stage") or "") for animal in group_animals)
        stage = stage_counter.most_common(1)[0][0] if stage_counter else "准备阶段"
        progress = STAGE_PROGRESS.get(stage, 50)
        high_risk = sum(1 for animal in group_animals if animal.get("status_code") == "high_risk")
        start_dates = [
            str(animal.get("group_time") or "")[:10]
            for animal in group_animals
            if animal.get("group_time")
        ]
        completed = all(str(animal.get("stage")) == "完成" for animal in group_animals)
        experiments.append(
            {
                "id": f"EXP-{index:03d}",
                "name": name,
                "animal_count": len(group_animals),
                "start_date": min(start_dates) if start_dates else "-",
                "stage": stage.replace("阶段", ""),
                "progress": progress,
                "status": "已完成" if completed else "进行中",
                "animals": [str(animal["id"]) for animal in group_animals],
                "summary": (
                    f"行为无助造模当前纳入 {len(group_animals)} 只实验鼠，"
                    f"主要处于{stage}，其中高风险对象 {high_risk} 只。"
                    "系统持续汇聚生理、行为、环境和刺激过程数据，用于阶段评估与辅助决策。"
                ),
            }
        )
    return experiments


def get_research_activity(
    animals: list[dict[str, Any]] | None = None,
    limit: int = 30,
) -> list[dict[str, str]]:
    """Combine persisted status, stimulation and analysis records for the study log."""
    source_animals = animals if animals is not None else get_animals()
    activity: list[dict[str, Any]] = []
    stimulation_labels = {
        "flash": "光刺激",
        "noise": "声音刺激",
        "electric_shock": "电击刺激",
    }
    for animal in source_animals:
        mouse_id = str(animal.get("id") or "")
        if not mouse_id:
            continue
        for record in get_status_history(mouse_id, limit=5):
            status = STATUS_LABELS.get(str(record.get("status")), str(record.get("status") or "未知"))
            reason = _record_reason(record.get("reason"))
            activity.append(
                {
                    "sort_time": record.get("recorded_at"),
                    "时间": _display_time(record.get("recorded_at")),
                    "实验动物": mouse_id,
                    "记录类型": "状态评估",
                    "记录内容": f"状态调整为{status}：{reason}",
                }
            )
        for event in get_stimulation_history(mouse_id, hours=168, limit=5):
            event_type = stimulation_labels.get(str(event.get("event_type")), "其他刺激")
            duration = event.get("duration_ms")
            duration_text = f"，持续 {float(duration) / 1000:g} 秒" if duration is not None else ""
            activity.append(
                {
                    "sort_time": event.get("started_at"),
                    "时间": _display_time(event.get("started_at")),
                    "实验动物": mouse_id,
                    "记录类型": "刺激执行",
                    "记录内容": f"执行{event_type}{duration_text}",
                }
            )
        analysis = get_agent_analysis(mouse_id)
        if analysis:
            activity.append(
                {
                    "sort_time": analysis.get("analyzed_at"),
                    "时间": _display_time(analysis.get("analyzed_at")),
                    "实验动物": mouse_id,
                    "记录类型": "辅助评估",
                    "记录内容": (
                        f"风险评分 {analysis.get('risk_score', '-')}，"
                        f"结论为 {analysis.get('risk_level', '未判定')}"
                    ),
                }
            )

    def sort_time(item: dict[str, Any]) -> float:
        timestamp = pd.to_datetime(item.get("sort_time"), utc=True, errors="coerce")
        if timestamp is None or pd.isna(timestamp):
            return float("-inf")
        return float(timestamp.timestamp())

    activity.sort(key=sort_time, reverse=True)
    return [
        {key: str(value) for key, value in item.items() if key != "sort_time"}
        for item in activity[:limit]
    ]


def get_status_history(mouse_id: str, limit: int = 20) -> list[dict[str, Any]]:
    history = api_data(f"/api/animals/{mouse_id}/status-history?limit={limit}")
    return history if isinstance(history, list) else []


def get_stimulation_history(mouse_id: str, hours: int = 24, limit: int = 50) -> list[dict[str, Any]]:
    history = api_data(f"/api/stimulation/{mouse_id}?hours={hours}&limit={limit}")
    return history if isinstance(history, list) else []


def get_stimulation_settings(device_id: str | None) -> list[dict[str, Any]]:
    if not device_id:
        return []
    settings = api_data(f"/api/stimulation/settings/{device_id}")
    return settings if isinstance(settings, list) else []


def save_stimulation_setting(
    *,
    mouse_id: str,
    device_id: str,
    event_type: str,
    enabled: bool,
    min_interval_ms: int,
    max_interval_ms: int,
    min_duration_ms: int,
    max_duration_ms: int,
) -> dict[str, Any]:
    response = api_request(
        "/api/stimulation/settings",
        method="PUT",
        payload={
            "mouse_id": mouse_id,
            "device_id": device_id,
            "event_type": event_type,
            "enabled": enabled,
            "min_interval_ms": min_interval_ms,
            "max_interval_ms": max_interval_ms,
            "min_duration_ms": min_duration_ms,
            "max_duration_ms": max_duration_ms,
        },
        timeout=3.0,
        return_errors=True,
    )
    if response is None:
        return {
            "success": False,
            "message": "后端未连接或请求超时，刺激设置没有保存。",
        }
    return response


def get_control_connection_status(device_id: str | None) -> bool:
    if not device_id:
        return False
    connections = api_data("/api/control-commands/connections")
    if not isinstance(connections, dict):
        return False
    connected_ids = connections.get("connected_device_ids")
    return isinstance(connected_ids, list) and device_id in connected_ids


def send_control_command(
    mouse_id: str,
    device_id: str,
    command_type: str,
    duration_ms: int,
    intensity: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mouse_id": mouse_id,
        "device_id": device_id,
        "command_type": command_type,
        "duration_ms": duration_ms,
    }
    if intensity is not None:
        payload["intensity"] = intensity

    response = api_request(
        "/api/control-commands",
        method="POST",
        payload=payload,
        timeout=3.0,
        return_errors=True,
    )
    if response is None:
        return {
            "success": False,
            "message": "后端未连接或请求超时，命令没有下发。",
        }
    return response


def confirm_agent_recommendation(analysis_id: int) -> dict[str, Any]:
    response = api_request(
        f"/api/agent/analysis-results/{analysis_id}/confirm",
        method="POST",
        timeout=3.0,
        return_errors=True,
    )
    if response is None:
        return {
            "success": False,
            "message": "后端未连接或请求超时，建议确认结果没有保存。",
        }
    return response


def get_data_center_metrics(refresh_count: int = 0) -> dict[str, pd.DataFrame]:
    animals = get_animals()
    template = generate_data_center_metrics(refresh_count)
    if not is_backend_available():
        if mock_fallback_enabled():
            return template
        return {
            "trend": _empty_frame(template["trend"].columns),
            "type_share": _empty_frame(template["type_share"].columns),
            "experiments": _empty_frame(template["experiments"].columns),
            "devices": _empty_frame(template["devices"].columns),
        }

    telemetry_rows: list[dict[str, Any]] = []
    vital_rows: list[dict[str, Any]] = []
    for animal in animals:
        mouse_id = str(animal["id"])
        telemetry_history = api_data(f"/api/telemetry/history/{mouse_id}?hours=24&limit=5000")
        vital_history = api_data(f"/api/vital-signs/history/{mouse_id}?hours=24&limit=10000")
        if isinstance(telemetry_history, list):
            telemetry_rows.extend(telemetry_history)
        if isinstance(vital_history, list):
            vital_rows.extend(vital_history)

    combined_rows = telemetry_rows + vital_rows
    if combined_rows:
        history_df = pd.DataFrame(combined_rows)
        history_df["timestamp"] = _parse_backend_datetime(history_df["recorded_at"]).dt.floor("h")
        count_df = history_df.groupby("timestamp").size().reset_index(name="count")
        y_col = [col for col in template["trend"].columns if col != "timestamp"][0]
        trend = pd.DataFrame({"timestamp": count_df["timestamp"], y_col: count_df["count"]})
    else:
        trend = _empty_frame(template["trend"].columns)

    type_name_col = template["type_share"].columns[0]
    type_value_col = template["type_share"].columns[1]
    vision_feature_rows = sum(
        int(get_vision_summary(str(animal["id"])).get("feature_rows") or 0)
        for animal in animals
    )
    type_share = pd.DataFrame(
        {
            type_name_col: ["生命体征", "视觉行为", "实验环境", "刺激过程"],
            type_value_col: [
                len(vital_rows),
                vision_feature_rows,
                len(telemetry_rows),
                sum(len(get_stimulation_history(str(animal["id"]))) for animal in animals),
            ],
        }
    )
    if int(type_share[type_value_col].sum()) == 0:
        type_share = _empty_frame(template["type_share"].columns)

    exp_x = template["experiments"].columns[0]
    exp_y = template["experiments"].columns[1]
    experiments = get_experiments(animals)
    experiment_data = (
        pd.DataFrame(
            {
                exp_x: [experiment["name"] for experiment in experiments],
                exp_y: [experiment["animal_count"] for experiment in experiments],
            }
        )
        if experiments
        else _empty_frame(template["experiments"].columns)
    )

    dev_x = template["devices"].columns[0]
    dev_y = template["devices"].columns[1]
    devices = get_devices()
    device_data = (
        pd.DataFrame(
            {
                dev_x: [device["id"] for device in devices],
                dev_y: [1 if device["online"] else 0 for device in devices],
            }
        )
        if devices
        else _empty_frame(template["devices"].columns)
    )

    return {
        "trend": trend,
        "type_share": type_share,
        "experiments": experiment_data,
        "devices": device_data,
    }


def backend_summary() -> dict[str, Any]:
    return {
        "base_url": get_api_base_url(),
        "connected": is_backend_available(),
        "label": get_connection_label(),
    }
