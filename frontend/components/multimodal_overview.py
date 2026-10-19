from __future__ import annotations

from collections import Counter
from html import escape
from typing import Any

import streamlit as st


STIMULATION_LABELS = {
    "flash": "光刺激",
    "noise": "声音刺激",
    "electric_shock": "电击刺激",
}


def _reading(value: Any, unit: str, digits: int = 1) -> str:
    if value is None:
        return "暂无"
    try:
        return f"{float(value):.{digits}f}{unit}"
    except (TypeError, ValueError):
        return "暂无"


def _card(title: str, label: str, detail: str, status: str, available: bool) -> str:
    state_class = "available" if available else "missing"
    return f"""
    <div class="modality-card {state_class}">
        <div class="modality-card-head">
            <span class="modality-mark">{escape(label)}</span>
            <span class="modality-state">{escape(status)}</span>
        </div>
        <strong>{escape(title)}</strong>
        <p>{escape(detail)}</p>
    </div>
    """


def render_multimodal_overview(
    mouse_id: str,
    animal: dict[str, Any],
    vision_summary: dict[str, Any],
    stimulation_events: list[dict[str, Any]],
) -> None:
    has_vitals = any(
        animal.get(field) is not None
        for field in ("body_temperature", "heart_rate", "blood_oxygen")
    )
    vital_detail = " · ".join(
        (
            f"体温 {_reading(animal.get('body_temperature'), ' ℃')}",
            f"心率 {_reading(animal.get('heart_rate'), ' bpm', 0)}",
            f"血氧 {_reading(animal.get('blood_oxygen'), ' %')}",
        )
    )

    feature_rows = int(vision_summary.get("feature_rows") or 0)
    confidence = vision_summary.get("avg_frame_confidence")
    vision_detail = (
        f"已形成 {feature_rows} 帧行为特征"
        + (
            f" · 识别可信度 {_reading(float(confidence) * 100, ' %')}"
            if confidence is not None
            else ""
        )
        if feature_rows
        else "等待摄像头行为特征数据"
    )

    has_environment = any(
        animal.get(field) is not None
        for field in ("environment_temperature", "humidity", "is_dark")
    )
    environment_detail = " · ".join(
        (
            f"温度 {_reading(animal.get('environment_temperature'), ' ℃')}",
            f"湿度 {_reading(animal.get('humidity'), ' %')}",
            "暗环境" if animal.get("is_dark") else "明环境",
        )
    )

    stimulation_counts = Counter(
        str(event.get("event_type")) for event in stimulation_events
    )
    stimulation_detail = " · ".join(
        f"{label} {stimulation_counts.get(event_type, 0)} 次"
        for event_type, label in STIMULATION_LABELS.items()
    )

    cards = [
        _card("生理表型", "生", vital_detail, "已采集" if has_vitals else "待采集", has_vitals),
        _card(
            "视觉行为",
            "视",
            vision_detail,
            "已提取" if feature_rows else "待采集",
            bool(feature_rows),
        ),
        _card(
            "实验环境",
            "环",
            environment_detail,
            "已采集" if has_environment else "待采集",
            has_environment,
        ),
        _card(
            "刺激过程",
            "刺",
            stimulation_detail,
            f"近 24 小时 {len(stimulation_events)} 条",
            bool(stimulation_events),
        ),
    ]

    st.markdown(
        f"""
        <div class="multimodal-shell">
            <div class="multimodal-heading">
                <div>
                    <span>研究对象</span>
                    <strong>{escape(mouse_id)} 多模态证据概览</strong>
                </div>
                <div class="fusion-chip">四类证据统一汇聚</div>
            </div>
            <div class="modality-grid">{"".join(cards)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
