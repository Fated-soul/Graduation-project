from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from components.metric_card import render_metric_card

EVENT_LABELS = {
    "electric_shock": "电击",
    "flash": "爆闪",
    "noise": "噪声",
}


def stimulation_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    electric_count = sum(1 for event in events if event.get("event_type") == "electric_shock")
    flash_count = sum(1 for event in events if event.get("event_type") == "flash")
    noise_count = sum(1 for event in events if event.get("event_type") == "noise")
    active_count = sum(1 for event in events if _is_currently_active(event))
    latest = events[0] if events else None
    return {
        "electric_shock": electric_count,
        "flash": flash_count,
        "noise": noise_count,
        "active": active_count,
        "total": len(events),
        "latest": latest,
    }


def _format_datetime(value: object) -> str:
    if value is None:
        return "-"
    try:
        timestamp = pd.to_datetime(value, format="mixed")
        if pd.isna(timestamp):
            return "-"
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return str(value)


def _format_int(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value)


def _format_seconds(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        seconds = float(value) / 1000
        return f"{seconds:.1f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return "-"


def _is_currently_active(event: dict[str, Any]) -> bool:
    if not event.get("is_active"):
        return False
    try:
        ended_at = pd.to_datetime(event.get("ended_at"), utc=True, format="mixed")
        if pd.isna(ended_at):
            return bool(event.get("is_active"))
        return bool(ended_at > pd.Timestamp.now(tz="UTC"))
    except (TypeError, ValueError):
        return bool(event.get("is_active"))


def stimulation_dataframe(events: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("event_type", ""))
        rows.append(
            {
                "刺激方式": EVENT_LABELS.get(event_type, "未知刺激"),
                "执行终端": event.get("device_id", "-"),
                "持续时间（秒）": _format_seconds(event.get("duration_ms")),
                "刺激强度": event.get("intensity") if event.get("intensity") is not None else "-",
                "正在刺激": "是" if _is_currently_active(event) else "否",
                "开始时间": _format_datetime(event.get("started_at")),
                "结束时间": _format_datetime(event.get("ended_at")),
                "下次间隔（秒）": _format_seconds(event.get("next_interval_ms")),
                "下次执行时间": _format_datetime(event.get("next_trigger_at")),
            }
        )
    return pd.DataFrame(rows)


def render_stimulation_metrics(events: list[dict[str, Any]], hours: int = 24) -> None:
    summary = stimulation_summary(events)
    latest = summary["latest"]
    latest_type = EVENT_LABELS.get(str(latest.get("event_type")), "未知刺激") if latest else "-"
    latest_time = _format_datetime(latest.get("started_at")) if latest else "暂无刺激记录"

    metric_cols = st.columns(4)
    metrics = [
        ("电击次数", summary["electric_shock"], "次", f"最近 {hours} 小时电击", "击", "关注" if summary["electric_shock"] else "正常"),
        ("爆闪次数", summary["flash"], "次", f"最近 {hours} 小时爆闪", "闪", "关注" if summary["flash"] else "正常"),
        ("噪声次数", summary["noise"], "次", f"最近 {hours} 小时噪声", "声", "关注" if summary["noise"] else "正常"),
        ("最近刺激", latest_type, "", latest_time, "刺", "关注" if latest else "正常"),
    ]
    for col, metric in zip(metric_cols, metrics, strict=True):
        with col:
            render_metric_card(*metric)


def render_stimulation_table(events: list[dict[str, Any]]) -> None:
    if not events:
        st.info("暂无电击、爆闪或噪声刺激记录。")
        return
    st.dataframe(stimulation_dataframe(events), width="stretch", hide_index=True)
