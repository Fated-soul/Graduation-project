from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components


_COMPONENT_DIR = Path(__file__).with_name("synchronized_player_frontend")
_synchronized_player = components.declare_component(
    "mingcha_synchronized_player",
    path=str(_COMPONENT_DIR),
)


def render_synchronized_player(
    *,
    video_url: str | None,
    duration_seconds: float | None,
    modeling_events: list[dict[str, Any]],
    signal_windows: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    session_type: str = "fear_conditioning",
    compact: bool = False,
    key: str,
) -> float | None:
    """Render the synchronized viewer and return a user-selected video time."""
    duration = _resolve_duration(
        duration_seconds,
        modeling_events,
        signal_windows,
        annotations,
    )
    payload = {
        "duration": duration,
        "sessionType": session_type,
        "events": [
            {
                "type": item.get("event_type") or "behavior_state",
                "label": item.get("event_label") or "造模事件",
                "start": float(item.get("start_time_seconds") or 0),
                "stop": float(
                    item.get("stop_time_seconds")
                    or item.get("start_time_seconds")
                    or 0
                ),
                "value": item.get("numeric_value"),
                "unit": item.get("unit") or "",
            }
            for item in modeling_events
        ],
        "signals": [
            {
                "modality": item.get("modality") or "motion",
                "name": item.get("signal_name") or "多模态信号",
                "time": (
                    float(item.get("window_start_seconds") or 0)
                    + float(item.get("window_end_seconds") or 0)
                )
                / 2,
                "value": float(item.get("mean_value") or 0),
                "unit": item.get("unit") or "",
            }
            for item in signal_windows
        ],
        "annotations": [
            {
                "time": float(item.get("timestamp_seconds") or 0),
                "category": item.get("category") or "人工复核",
                "note": item.get("note") or "",
            }
            for item in annotations
            if item.get("timestamp_seconds") is not None
        ],
    }
    selected_time = _synchronized_player(
        video_url=video_url or "",
        payload=payload,
        compact=compact,
        default=None,
        key=key,
    )
    try:
        return float(selected_time) if selected_time is not None else None
    except (TypeError, ValueError):
        return None


def _resolve_duration(
    stored_duration: float | None,
    events: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
) -> float:
    values = [float(stored_duration or 0)]
    values.extend(
        float(item.get("stop_time_seconds") or item.get("start_time_seconds") or 0)
        for item in events
    )
    values.extend(float(item.get("window_end_seconds") or 0) for item in signals)
    values.extend(
        float(item.get("timestamp_seconds") or 0)
        for item in annotations
        if item.get("timestamp_seconds") is not None
    )
    return max(1.0, max(values, default=1.0))
