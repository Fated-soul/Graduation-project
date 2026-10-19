from __future__ import annotations

from datetime import datetime
from statistics import mean
from typing import Any

from agent.schemas import AnalysisResult


def build_rule_analysis(context: dict[str, Any]) -> AnalysisResult:
    mouse_id = str(context["mouse_id"])
    animal = context.get("animal") or {}
    devices = context.get("devices") or []
    latest = context.get("vital_latest") or {}
    vital_history = context.get("vital_history") or []
    stimulation_history = context.get("stimulation_history") or []
    vision = context.get("vision_summary") or {}

    temperature = _number(latest.get("body_temperature"))
    heart_rate = _number(latest.get("heart_rate"))
    blood_oxygen = _number(latest.get("blood_oxygen"))
    score = 0
    factors: list[str] = []

    if temperature is None:
        factors.append("缺少小鼠体温数据")
        score += 8
    elif temperature >= 38.5:
        factors.append("小鼠体温明显升高")
        score += 32
    elif temperature >= 38.0:
        factors.append("小鼠体温偏高")
        score += 18
    elif temperature <= 35.0:
        factors.append("小鼠体温明显偏低")
        score += 28
    elif temperature <= 36.0:
        factors.append("小鼠体温偏低")
        score += 12

    if heart_rate is None:
        factors.append("缺少心率数据")
        score += 6
    elif heart_rate >= 500:
        factors.append("心率明显偏高")
        score += 28
    elif heart_rate >= 470:
        factors.append("心率偏高")
        score += 16
    elif heart_rate <= 250:
        factors.append("心率明显偏低")
        score += 24

    if blood_oxygen is None:
        factors.append("缺少血氧数据")
        score += 6
    elif blood_oxygen <= 90:
        factors.append("血氧明显偏低")
        score += 35
    elif blood_oxygen <= 94:
        factors.append("血氧偏低")
        score += 20
    elif blood_oxygen <= 96:
        factors.append("血氧需关注")
        score += 8

    temperature_trend = _trend(vital_history, "body_temperature")
    heart_rate_trend = _trend(vital_history, "heart_rate")
    if temperature_trend is not None and temperature_trend >= 0.5:
        factors.append("体温呈上升趋势")
        score += 8
    if heart_rate_trend is not None and heart_rate_trend >= 40:
        factors.append("心率呈上升趋势")
        score += 8

    if devices and not any(bool(device.get("online")) for device in devices):
        factors.append("绑定设备离线")
        score += 20

    recent_stimulation_count = len(stimulation_history)
    if recent_stimulation_count >= 30:
        factors.append("近期刺激次数较多")
        score += 10

    frame_count = int(_number(vision.get("feature_rows")) or 0)
    vision_confidence = _number(vision.get("avg_frame_confidence"))
    if frame_count == 0:
        factors.append("暂无足够的行为影像数据")
    elif vision_confidence is not None and vision_confidence < 0.5:
        factors.append("视觉数据置信度偏低")
        score += 8

    score = max(0, min(100, score))
    if score >= 60:
        risk_level = "高风险"
    elif score >= 30:
        risk_level = "关注"
    else:
        risk_level = "正常"

    stage = str(animal.get("experiment_stage") or "未设置")
    vital_analysis = _vital_analysis(
        temperature,
        heart_rate,
        blood_oxygen,
        temperature_trend,
        heart_rate_trend,
    )
    behavior_analysis = _behavior_analysis(vision, frame_count, vision_confidence)
    stage_analysis = (
        f"当前处于{stage}。建议结合这一阶段的连续变化观察小鼠状态，"
        "不要只根据某一次测量结果作出判断。"
    )
    risk_analysis = (
        f"目前风险评分为 {score}/100，整体状态为{risk_level}。"
        f"需要关注的情况包括：{'、'.join(factors) if factors else '目前各项指标未见明显异常'}。"
    )

    if risk_level == "高风险":
        recommendation = "建议暂停自动刺激，立即进行人工复核，并持续观察生命体征变化。"
        control_strategy = "人工确认后暂停自动刺激；未经确认不得由 Agent 直接控制设备。"
    elif risk_level == "关注":
        recommendation = "建议保持重点观察，适当延长刺激间隔，并复查体温、心率和血氧趋势。"
        control_strategy = "维持监测，参数调整需由实验人员确认后通过控制接口下发。"
    else:
        recommendation = "当前可继续既定造模流程，并保持生命体征和行为数据连续采集。"
        control_strategy = "维持现有刺激设置，所有控制操作仍由实验人员确认。"

    summary = (
        f"{mouse_id} 当前处于{stage}，整体状态为{risk_level}，风险评分 {score}/100。"
        f"{'目前需要关注' + '、'.join(factors[:4]) if factors else '目前体征与活动情况总体稳定'}。"
    )
    return AnalysisResult(
        mouse_id=mouse_id,
        risk_score=score,
        risk_level=risk_level,
        summary=summary,
        vital_analysis=vital_analysis,
        behavior_analysis=behavior_analysis,
        stage_analysis=stage_analysis,
        risk_analysis=risk_analysis,
        recommendation=recommendation,
        control_strategy=control_strategy,
        factors=factors[:10],
        analysis_source="rules",
        experiment_stage=stage,
        analyzed_at=datetime.now(),
    )


def build_parameter_recommendation(
    context: dict[str, Any], analysis: AnalysisResult
) -> dict[str, Any]:
    history = context.get("stimulation_history") or []
    latest_event = history[0] if history else {}
    current_duration = int(_number(latest_event.get("duration_ms")) or 0)
    current_intensity = _number(latest_event.get("intensity"))
    interval_ms = _estimate_interval_ms(history)

    if analysis.risk_level == "高风险":
        actions = ["暂停自动刺激", "立即人工复核生命体征"]
        proposed_duration = max(100, int(current_duration * 0.6)) if current_duration else None
        proposed_interval = int(interval_ms * 1.5) if interval_ms else None
    elif analysis.risk_level == "关注":
        actions = ["保持重点观察", "人工确认后适当延长刺激间隔"]
        proposed_duration = max(100, int(current_duration * 0.8)) if current_duration else None
        proposed_interval = int(interval_ms * 1.2) if interval_ms else None
    else:
        actions = ["维持当前方案", "继续采集生命体征和行为数据"]
        proposed_duration = current_duration or None
        proposed_interval = interval_ms

    return {
        "action": actions,
        "reason": analysis.factors or ["目前各项指标未见明显异常"],
        "parameters": {
            "latest_stimulation_event": {
                "duration_ms": current_duration or None,
                "interval_ms": interval_ms,
                "intensity": current_intensity,
            },
            "proposed": {
                "duration_ms": proposed_duration,
                "interval_ms": proposed_interval,
                "intensity": current_intensity,
            },
            "confidence": 0.78 if history else 0.55,
            "guidance": "候选参数仅用于辅助决策，确认后才可通过控制命令接口下发。",
        },
    }


def compact_context(context: dict[str, Any], analysis: AnalysisResult) -> dict[str, Any]:
    return {
        "mouse_id": context.get("mouse_id"),
        "animal": context.get("animal"),
        "devices": context.get("devices"),
        "latest_vital_signs": context.get("vital_latest"),
        "latest_vital_history": (context.get("vital_history") or [])[-24:],
        "latest_environment_history": (context.get("telemetry_history") or [])[-12:],
        "latest_stimulation_events": (context.get("stimulation_history") or [])[:20],
        "stimulation_settings": context.get("stimulation_settings"),
        "vision_summary": context.get("vision_summary"),
        "rule_analysis": analysis.model_dump(mode="json"),
    }


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _trend(rows: list[dict[str, Any]], field: str) -> float | None:
    values = [_number(row.get(field)) for row in rows]
    valid = [value for value in values if value is not None]
    if len(valid) < 2:
        return None
    return valid[-1] - valid[0]


def _vital_analysis(
    temperature: float | None,
    heart_rate: float | None,
    blood_oxygen: float | None,
    temperature_trend: float | None,
    heart_rate_trend: float | None,
) -> str:
    values = [
        f"小鼠体温 {temperature:.1f} ℃" if temperature is not None else "小鼠体温暂无数据",
        f"心率 {heart_rate:.0f} bpm" if heart_rate is not None else "心率暂无数据",
        f"血氧 {blood_oxygen:.1f}%" if blood_oxygen is not None else "血氧暂无数据",
    ]
    trends = []
    if temperature_trend is not None:
        trends.append(f"体温窗口变化 {temperature_trend:+.2f} ℃")
    if heart_rate_trend is not None:
        trends.append(f"心率窗口变化 {heart_rate_trend:+.0f} bpm")
    return "，".join(values) + ("；" + "，".join(trends) if trends else "。")


def _behavior_analysis(
    vision: dict[str, Any], frame_count: int, confidence: float | None
) -> str:
    if frame_count == 0:
        return "目前没有足够的行为影像数据，因此暂时无法判断活动情况。"
    total_movement = _number(vision.get("total_movement_distance"))
    avg_movement = _number(vision.get("avg_movement_distance"))
    pieces = [f"本次共观察到 {frame_count} 帧画面"]
    if total_movement is not None:
        pieces.append(f"累计移动距离 {total_movement:.2f}")
    if avg_movement is not None:
        pieces.append(f"相邻画面间的平均移动距离为 {avg_movement:.3f}")
    if confidence is not None:
        pieces.append(f"影像识别可信度约为 {confidence:.1%}")
    return "，".join(pieces) + "。"


def _estimate_interval_ms(history: list[dict[str, Any]]) -> int | None:
    timestamps: list[datetime] = []
    for event in history[:10]:
        raw = event.get("started_at")
        if not raw:
            continue
        try:
            timestamps.append(datetime.fromisoformat(str(raw).replace("Z", "+00:00")))
        except ValueError:
            continue
    if len(timestamps) < 2:
        return None
    timestamps.sort()
    intervals = [
        (later - earlier).total_seconds() * 1000
        for earlier, later in zip(timestamps, timestamps[1:])
        if later > earlier
    ]
    return int(mean(intervals)) if intervals else None
