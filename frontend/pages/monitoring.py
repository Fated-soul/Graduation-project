from __future__ import annotations

import json
import random
import time

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from components.charts import (
    PLOT_CONFIG,
    create_blood_oxygen_chart,
    create_environment_chart,
    create_heart_rate_chart,
    create_temperature_chart,
)
from components.camera_stream import render_camera_stream
from components.metric_card import render_metric_card, render_section_title
from data.backend_data import (
    get_animals,
    get_control_connection_status,
    get_environment_frame,
    get_stimulation_settings,
    get_stimulation_history,
    get_vital_signs_frame,
    get_vision_summary,
    save_stimulation_setting,
    send_control_command,
)
from utils.api_client import get_api_base_url


STIMULATION_TYPES = [
    {
        "event_type": "flash",
        "label": "光刺激（爆闪）",
        "short_label": "光",
        "default_min_interval_ms": 30_000,
        "default_max_interval_ms": 60_000,
        "default_min_duration_ms": 1_000,
        "default_max_duration_ms": 5_000,
    },
    {
        "event_type": "noise",
        "label": "声音刺激（噪声）",
        "short_label": "声",
        "default_min_interval_ms": 30_000,
        "default_max_interval_ms": 60_000,
        "default_min_duration_ms": 2_000,
        "default_max_duration_ms": 5_000,
    },
    {
        "event_type": "electric_shock",
        "label": "电击刺激",
        "short_label": "电",
        "default_min_interval_ms": 35_000,
        "default_max_interval_ms": 45_000,
        "default_min_duration_ms": 2_000,
        "default_max_duration_ms": 8_000,
    },
]


def _latest_row(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="float64")
    return frame.ffill().bfill().iloc[-1]


def _number(value: object, digits: int = 1, empty: str = "-") -> str:
    if value is None or pd.isna(value):
        return empty
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return empty


def _render_visual_behavior_summary(summary: dict[str, object]) -> None:
    feature_rows = int(summary.get("feature_rows") or 0)
    total_movement = summary.get("total_movement_distance")
    average_movement = summary.get("avg_movement_distance")
    confidence = summary.get("avg_frame_confidence")
    confidence_percent = float(confidence) * 100 if confidence is not None else None

    metric_cols = st.columns(4)
    metrics = [
        ("有效观察画面", feature_rows, "帧", "视觉行为记录", "画", "正常" if feature_rows else "关注"),
        ("累计活动距离", _number(total_movement, 2), "", "活动轨迹累计值", "移", "正常"),
        ("平均活动幅度", _number(average_movement, 3), "", "相邻画面中的位置变化", "动", "正常"),
        ("识别可信度", _number(confidence_percent, 1), "%", "行为识别质量", "质", "正常" if confidence_percent and confidence_percent >= 70 else "关注"),
    ]
    for col, metric in zip(metric_cols, metrics, strict=True):
        with col:
            render_metric_card(*metric)


def _control_message(response: dict[str, object]) -> str:
    status_code = response.get("status_code")
    if status_code == 404:
        return "未找到对应的实验动物或执行终端。"
    if status_code in {409, 503}:
        return "执行终端当前未连接，请确认设备在线后重试。"
    return "操作未完成，请确认执行终端在线后重试。"


def _to_epoch_seconds(value: object) -> float | None:
    if value is None:
        return None
    try:
        timestamp = pd.to_datetime(value, utc=True, format="mixed")
        if pd.isna(timestamp):
            return None
        return float(timestamp.timestamp())
    except (TypeError, ValueError):
        return None


def _seconds_from_ms(value: int) -> int:
    return max(0, int(round(value / 1000)))


def _setting_key(device_id: str, event_type: str, field: str) -> str:
    return f"stim_setting_{device_id}_{event_type}_{field}"


def _current_setting_ms(device_id: str, event_type: str, field: str, default_ms: int) -> int:
    key = _setting_key(device_id, event_type, field)
    value_seconds = st.session_state.get(key, _seconds_from_ms(default_ms))
    try:
        return max(0, int(float(value_seconds) * 1000))
    except (TypeError, ValueError):
        return default_ms


def _latest_events_by_type(events: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    latest: dict[str, dict[str, object]] = {}
    for event in events:
        event_type = str(event.get("event_type", ""))
        current = latest.get(event_type)
        if current is None:
            latest[event_type] = event
            continue
        current_time = _to_epoch_seconds(current.get("started_at")) or 0
        event_time = _to_epoch_seconds(event.get("started_at")) or 0
        if event_time > current_time:
            latest[event_type] = event
    return latest


def _event_countdown_payload(
    *,
    selected_mouse: str,
    event_type: str,
    latest_event: dict[str, object] | None,
) -> dict[str, object]:
    now = time.time()
    active_until = None
    next_at = None

    if latest_event is not None:
        started_at = _to_epoch_seconds(latest_event.get("started_at"))
        ended_at = _to_epoch_seconds(latest_event.get("ended_at"))
        duration_ms = latest_event.get("duration_ms")
        if ended_at is None and started_at is not None and duration_ms is not None:
            try:
                ended_at = started_at + float(duration_ms) / 1000
            except (TypeError, ValueError):
                ended_at = None

        if bool(latest_event.get("is_active", True)) and ended_at is not None and ended_at > now:
            active_until = ended_at

        next_trigger_at = _to_epoch_seconds(latest_event.get("next_trigger_at"))
        if next_trigger_at is not None and next_trigger_at > now:
            next_at = next_trigger_at

    local_state = st.session_state.setdefault("stimulation_local_countdowns", {})
    local = local_state.get(f"{selected_mouse}:{event_type}")
    if isinstance(local, dict):
        local_active_until = local.get("active_until")
        local_next_at = local.get("next_at")
        if isinstance(local_active_until, (int, float)) and local_active_until > now:
            active_until = max(active_until or 0, float(local_active_until))
        if isinstance(local_next_at, (int, float)) and local_next_at > now:
            next_at = max(next_at or 0, float(local_next_at))

    return {
        "event_type": event_type,
        "active_until_ms": int(active_until * 1000) if active_until else None,
        "next_at_ms": int(next_at * 1000) if next_at else None,
        "active_left_ms": int((active_until - now) * 1000) if active_until else None,
        "next_left_ms": int((next_at - now) * 1000) if next_at else None,
        "is_active": bool(active_until),
    }


def _render_countdown_cards(cards: list[dict[str, object]]) -> None:
    payload = json.dumps(cards, ensure_ascii=False)
    html = f"""
    <div id="stim-countdown-root" style="display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;font-family:Arial,'Microsoft YaHei',sans-serif;">
    </div>
    <script>
    const cards = {payload};
    const labels = {{
      flash: "光刺激（爆闪）",
      noise: "声音刺激（噪声）",
      electric_shock: "电击刺激"
    }};
    const shorts = {{flash: "光", noise: "声", electric_shock: "电"}};
    const root = document.getElementById("stim-countdown-root");
    const loadedAt = Date.now();
    function secondsText(ms) {{
      const total = Math.max(0, Math.ceil(ms / 1000));
      const min = Math.floor(total / 60);
      const sec = total % 60;
      if (min > 0) return `${{min}}分 ${{sec}}秒`;
      return `${{sec}}秒`;
    }}
    function remainingMs(card, relativeKey, absoluteKey, now) {{
      const relative = card[relativeKey];
      if (typeof relative === "number") return relative - (now - loadedAt);
      const absolute = card[absoluteKey];
      if (absolute) return absolute - now;
      return 0;
    }}
    function render() {{
      const now = Date.now();
      root.innerHTML = cards.map((card) => {{
        let status = "待机";
        let detail = "等待执行终端提供下一次刺激时间";
        let color = "#0f766e";
        let bg = "linear-gradient(135deg,#ecfeff,#f8fafc)";
        const activeLeft = remainingMs(card, "active_left_ms", "active_until_ms", now);
        const nextLeft = remainingMs(card, "next_left_ms", "next_at_ms", now);
        if (activeLeft > 0) {{
          status = "正在刺激";
          detail = "剩余执行时间：" + secondsText(activeLeft);
          color = "#dc2626";
          bg = "linear-gradient(135deg,#fff1f2,#fff7ed)";
        }} else if (nextLeft > 0) {{
          status = "等待下一次";
          detail = "距离下一次执行：" + secondsText(nextLeft);
          color = "#2563eb";
          bg = "linear-gradient(135deg,#eff6ff,#f8fafc)";
        }}
        return `
          <div style="border:1px solid #dbeafe;border-radius:12px;padding:14px;background:${{bg}};min-height:118px;">
            <div style="display:flex;align-items:center;justify-content:space-between;">
              <div style="font-size:15px;font-weight:700;color:#17324d;">${{labels[card.event_type] || "未知刺激"}}</div>
              <div style="width:32px;height:32px;border-radius:999px;background:#e0f2fe;color:#0369a1;display:grid;place-items:center;font-weight:800;">${{shorts[card.event_type] || ""}}</div>
            </div>
            <div style="margin-top:12px;color:${{color}};font-size:20px;font-weight:800;">${{status}}</div>
            <div style="margin-top:8px;color:#475569;font-size:14px;line-height:1.6;">${{detail}}</div>
          </div>
        `;
      }}).join("");
    }}
    render();
    setInterval(render, 1000);
    </script>
    """
    components.html(html, height=150)


def _render_stable_countdown_panel(selected_mouse: str) -> None:
    initial_events = get_stimulation_history(selected_mouse, hours=24, limit=100)
    initial_cards = _build_countdown_cards(selected_mouse, initial_events)
    cards_payload = json.dumps(initial_cards, ensure_ascii=False)
    mouse_payload = json.dumps(selected_mouse, ensure_ascii=False)
    api_payload = json.dumps(get_api_base_url(), ensure_ascii=False)
    labels_payload = json.dumps(
        {
            "flash": "光刺激（爆闪）",
            "noise": "声音刺激（噪声）",
            "electric_shock": "电击刺激",
        },
        ensure_ascii=False,
    )
    shorts_payload = json.dumps(
        {"flash": "光", "noise": "声", "electric_shock": "电"},
        ensure_ascii=False,
    )

    html = f"""
    <style>
      #stim-countdown-root {{
        display:grid;
        grid-template-columns:repeat(3,minmax(0,1fr));
        gap:12px;
        font-family:Arial,'Microsoft YaHei',sans-serif;
      }}
      .stim-card {{
        border:1px solid #dbeafe;
        border-radius:12px;
        padding:14px;
        background:linear-gradient(135deg,#ecfeff,#f8fafc);
        min-height:118px;
        transition:background 180ms ease,border-color 180ms ease;
      }}
      .stim-head {{
        display:flex;
        align-items:center;
        justify-content:space-between;
      }}
      .stim-label {{
        font-size:15px;
        font-weight:700;
        color:#17324d;
      }}
      .stim-badge {{
        width:32px;
        height:32px;
        border-radius:999px;
        background:#e0f2fe;
        color:#0369a1;
        display:grid;
        place-items:center;
        font-weight:800;
      }}
      .stim-status {{
        margin-top:12px;
        color:#0f766e;
        font-size:20px;
        font-weight:800;
        transition:color 180ms ease;
      }}
      .stim-detail {{
        margin-top:8px;
        color:#475569;
        font-size:14px;
        line-height:1.6;
      }}
      @media (max-width:900px) {{
        #stim-countdown-root {{ grid-template-columns:1fr; }}
      }}
    </style>
    <div id="stim-countdown-root"></div>
    <script>
      let cards = {cards_payload};
      let loadedAt = Date.now();
      const selectedMouse = {mouse_payload};
      const apiBaseUrl = {api_payload}.replace(/\\/$/, "");
      const labels = {labels_payload};
      const shorts = {shorts_payload};
      const eventTypes = ["flash", "noise", "electric_shock"];
      const root = document.getElementById("stim-countdown-root");

      function createCards() {{
        root.innerHTML = eventTypes.map((eventType) => `
          <div class="stim-card" data-event-type="${{eventType}}">
            <div class="stim-head">
              <div class="stim-label">${{labels[eventType] || eventType}}</div>
              <div class="stim-badge">${{shorts[eventType] || ""}}</div>
            </div>
            <div class="stim-status">待机</div>
            <div class="stim-detail">等待执行终端提供下一次刺激时间</div>
          </div>
        `).join("");
      }}

      function secondsText(ms) {{
        const total = Math.max(0, Math.ceil(ms / 1000));
        const min = Math.floor(total / 60);
        const sec = total % 60;
        return min > 0 ? `${{min}}分${{sec}}秒` : `${{sec}}秒`;
      }}

      function remainingMs(card, relativeKey, absoluteKey, now) {{
        const relative = card[relativeKey];
        if (typeof relative === "number") return relative - (now - loadedAt);
        const absolute = card[absoluteKey];
        return absolute ? absolute - now : 0;
      }}

      function render() {{
        const now = Date.now();
        cards.forEach((card) => {{
          let status = "待机";
          let detail = "等待执行终端提供下一次刺激时间";
          let color = "#0f766e";
          let bg = "linear-gradient(135deg,#ecfeff,#f8fafc)";
          const activeLeft = remainingMs(card, "active_left_ms", "active_until_ms", now);
          const nextLeft = remainingMs(card, "next_left_ms", "next_at_ms", now);
          if (activeLeft > 0) {{
            status = "正在刺激";
            detail = "剩余执行时间：" + secondsText(activeLeft);
            color = "#dc2626";
            bg = "linear-gradient(135deg,#fff1f2,#fff7ed)";
          }} else if (nextLeft > 0) {{
            status = "等待下一次";
            detail = "距离下一次执行：" + secondsText(nextLeft);
            color = "#2563eb";
            bg = "linear-gradient(135deg,#eff6ff,#f8fafc)";
          }}

          const element = root.querySelector(`[data-event-type="${{card.event_type}}"]`);
          if (!element) return;
          element.style.background = bg;
          const statusEl = element.querySelector(".stim-status");
          const detailEl = element.querySelector(".stim-detail");
          if (statusEl.textContent !== status) statusEl.textContent = status;
          if (detailEl.textContent !== detail) detailEl.textContent = detail;
          statusEl.style.color = color;
        }});
      }}

      function toMs(value) {{
        if (!value) return null;
        const parsed = Date.parse(value);
        return Number.isNaN(parsed) ? null : parsed;
      }}

      function latestEventsByType(events) {{
        const latest = {{}};
        for (const event of events) {{
          const eventType = String(event.event_type || "");
          const eventTime = toMs(event.started_at) || 0;
          const currentTime = latest[eventType] ? (toMs(latest[eventType].started_at) || 0) : 0;
          if (!latest[eventType] || eventTime > currentTime) latest[eventType] = event;
        }}
        return latest;
      }}

      function cardFromEvent(eventType, event) {{
        const now = Date.now();
        let activeUntil = null;
        let nextAt = null;
        if (event) {{
          const startedAt = toMs(event.started_at);
          let endedAt = toMs(event.ended_at);
          if (!endedAt && startedAt && event.duration_ms) endedAt = startedAt + Number(event.duration_ms);
          if ((event.is_active ?? true) && endedAt && endedAt > now) activeUntil = endedAt;
          const nextTriggerAt = toMs(event.next_trigger_at);
          if (nextTriggerAt && nextTriggerAt > now) nextAt = nextTriggerAt;
        }}
        return {{
          event_type: eventType,
          active_until_ms: activeUntil,
          next_at_ms: nextAt,
          active_left_ms: activeUntil ? activeUntil - now : null,
          next_left_ms: nextAt ? nextAt - now : null,
          is_active: Boolean(activeUntil)
        }};
      }}

      async function refreshFromBackend() {{
        try {{
          const url = `${{apiBaseUrl}}/api/stimulation/${{encodeURIComponent(selectedMouse)}}?hours=24&limit=100&_=${{Date.now()}}`;
          const response = await fetch(url, {{cache: "no-store"}});
          if (!response.ok) return;
          const body = await response.json();
          const events = Array.isArray(body.data) ? body.data : [];
          const latest = latestEventsByType(events);
          loadedAt = Date.now();
          cards = eventTypes.map((eventType) => cardFromEvent(eventType, latest[eventType]));
          render();
        }} catch (error) {{
          // Keep the previous visual state if the backend is briefly unavailable.
        }}
      }}

      createCards();
      render();
      refreshFromBackend();
      setInterval(render, 1000);
      setInterval(refreshFromBackend, 500);
    </script>
    """
    components.html(html, height=155)


def _render_stable_stimulation_events_panel(selected_mouse: str) -> None:
    initial_events = get_stimulation_history(selected_mouse, hours=24, limit=100)
    events_payload = json.dumps(initial_events, ensure_ascii=False)
    mouse_payload = json.dumps(selected_mouse, ensure_ascii=False)
    api_payload = json.dumps(get_api_base_url(), ensure_ascii=False)

    html = """
    <style>
      #stim-events-root { font-family:Arial,'Microsoft YaHei',sans-serif; }
      .stim-event-metrics {
        display:grid;
        grid-template-columns:repeat(4,minmax(0,1fr));
        gap:12px;
        margin-bottom:14px;
      }
      .stim-event-metric {
        border:1px solid #dbeafe;
        border-radius:10px;
        padding:12px 14px;
        background:linear-gradient(135deg,#f8fafc,#eff6ff);
      }
      .stim-event-metric-label { color:#64748b; font-size:13px; }
      .stim-event-metric-value {
        color:#17324d;
        font-size:24px;
        font-weight:800;
        margin-top:4px;
      }
      .stim-event-meta {
        display:flex;
        justify-content:space-between;
        align-items:center;
        color:#64748b;
        font-size:13px;
        margin:4px 0 10px;
      }
      .stim-event-table-wrap {
        border:1px solid #dbeafe;
        border-radius:10px;
        overflow:hidden;
        background:#fff;
      }
      table.stim-event-table {
        width:100%;
        border-collapse:collapse;
        table-layout:fixed;
        font-size:13px;
      }
      .stim-event-table th {
        background:#f1f5f9;
        color:#334155;
        font-weight:700;
        padding:10px 8px;
        text-align:left;
        border-bottom:1px solid #dbeafe;
      }
      .stim-event-table td {
        color:#334155;
        padding:9px 8px;
        border-bottom:1px solid #e2e8f0;
        white-space:nowrap;
        overflow:hidden;
        text-overflow:ellipsis;
      }
      .stim-event-table tr:last-child td { border-bottom:none; }
      .stim-badge-type {
        display:inline-flex;
        align-items:center;
        justify-content:center;
        min-width:48px;
        border-radius:999px;
        padding:3px 8px;
        background:#e0f2fe;
        color:#0369a1;
        font-weight:700;
      }
      .stim-active { color:#dc2626; font-weight:700; }
      .stim-idle { color:#64748b; }
      .stim-empty {
        border:1px solid #dbeafe;
        border-radius:10px;
        padding:18px;
        color:#64748b;
        background:#f8fafc;
      }
      @media (max-width:900px) {
        .stim-event-metrics { grid-template-columns:repeat(2,minmax(0,1fr)); }
      }
    </style>
    <div id="stim-events-root">
      <div class="stim-event-metrics">
        <div class="stim-event-metric">
          <div class="stim-event-metric-label">电击次数</div>
          <div class="stim-event-metric-value" data-metric="electric_shock">0</div>
        </div>
        <div class="stim-event-metric">
          <div class="stim-event-metric-label">爆闪次数</div>
          <div class="stim-event-metric-value" data-metric="flash">0</div>
        </div>
        <div class="stim-event-metric">
          <div class="stim-event-metric-label">噪声次数</div>
          <div class="stim-event-metric-value" data-metric="noise">0</div>
        </div>
        <div class="stim-event-metric">
          <div class="stim-event-metric-label">最近刺激</div>
          <div class="stim-event-metric-value" data-metric="latest">-</div>
        </div>
      </div>
      <div class="stim-event-meta">
        <span data-meta="summary">最近 24 小时刺激记录</span>
        <span data-meta="updated">等待数据</span>
      </div>
      <div id="stim-event-content"></div>
    </div>
    <script>
      let events = __EVENTS__;
      const selectedMouse = __MOUSE__;
      const apiBaseUrl = __API_BASE__.replace(/\\/$/, "");
      const labels = {electric_shock: "电击", flash: "爆闪", noise: "噪声"};
      const content = document.getElementById("stim-event-content");

      function toMs(value) {
        if (!value) return null;
        const parsed = Date.parse(value);
        return Number.isNaN(parsed) ? null : parsed;
      }

      function formatTime(value) {
        const ms = toMs(value);
        if (!ms) return "-";
        const date = new Date(ms);
        const pad = (number) => String(number).padStart(2, "0");
        return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
      }

      function isActive(event) {
        if (!event || !event.is_active) return false;
        const endedAt = toMs(event.ended_at);
        return Boolean(endedAt && endedAt > Date.now());
      }

      function setText(selector, value) {
        const element = document.querySelector(selector);
        if (element && element.textContent !== String(value)) element.textContent = value;
      }

      function renderMetrics() {
        const counts = {electric_shock: 0, flash: 0, noise: 0};
        for (const event of events) {
          if (Object.prototype.hasOwnProperty.call(counts, event.event_type)) counts[event.event_type] += 1;
        }
        const latest = events[0];
        setText('[data-metric="electric_shock"]', counts.electric_shock);
        setText('[data-metric="flash"]', counts.flash);
        setText('[data-metric="noise"]', counts.noise);
        setText('[data-metric="latest"]', latest ? (labels[latest.event_type] || "未知刺激") : "-");
        setText('[data-meta="summary"]', `最近 24 小时共 ${events.length} 条刺激记录`);
        setText('[data-meta="updated"]', `自动更新：${new Date().toLocaleTimeString()}`);
      }

      function renderTable() {
        if (!events.length) {
          content.innerHTML = '<div class="stim-empty">暂无电击、爆闪或噪声刺激记录。</div>';
          return;
        }
        const rows = events.slice(0, 30).map((event) => {
          const active = isActive(event);
          return `
            <tr>
              <td><span class="stim-badge-type">${labels[event.event_type] || "未知刺激"}</span></td>
              <td>${event.device_id || "-"}</td>
              <td>${event.duration_ms == null ? "-" : (Number(event.duration_ms) / 1000).toFixed(1)}</td>
              <td class="${active ? "stim-active" : "stim-idle"}">${active ? "正在刺激" : "已结束"}</td>
              <td>${formatTime(event.started_at)}</td>
              <td>${formatTime(event.ended_at)}</td>
              <td>${event.next_interval_ms == null ? "-" : (Number(event.next_interval_ms) / 1000).toFixed(1)}</td>
              <td>${formatTime(event.next_trigger_at)}</td>
            </tr>
          `;
        }).join("");
        content.innerHTML = `
          <div class="stim-event-table-wrap">
            <table class="stim-event-table">
              <thead>
                <tr>
                  <th>刺激方式</th>
                  <th>执行终端</th>
                  <th>持续时间（秒）</th>
                  <th>状态</th>
                  <th>开始时间</th>
                  <th>结束时间</th>
                  <th>下次间隔（秒）</th>
                  <th>下次执行</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
        `;
      }

      function render() {
        renderMetrics();
        renderTable();
      }

      async function refreshFromBackend() {
        try {
          const url = `${apiBaseUrl}/api/stimulation/${encodeURIComponent(selectedMouse)}?hours=24&limit=100&_=${Date.now()}`;
          const response = await fetch(url, {cache: "no-store"});
          if (!response.ok) return;
          const body = await response.json();
          events = Array.isArray(body.data) ? body.data : [];
          render();
        } catch (error) {
          // 网络抖动时保持当前内容，避免界面闪烁。
        }
      }

      render();
      refreshFromBackend();
      setInterval(refreshFromBackend, 1500);
      setInterval(renderMetrics, 1000);
    </script>
    """
    html = (
        html.replace("__EVENTS__", events_payload)
        .replace("__MOUSE__", mouse_payload)
        .replace("__API_BASE__", api_payload)
    )
    components.html(html, height=520)


def _record_manual_countdown(
    *,
    selected_mouse: str,
    event_type: str,
    duration_ms: int,
    interval_ms: int,
) -> None:
    now = time.time()
    st.session_state.setdefault("stimulation_local_countdowns", {})[
        f"{selected_mouse}:{event_type}"
    ] = {
        "active_until": now + duration_ms / 1000,
        "next_at": now + duration_ms / 1000 + interval_ms / 1000,
    }


def _settings_by_type(device_id: str | None) -> dict[str, dict[str, object]]:
    return {
        str(setting.get("event_type")): setting
        for setting in get_stimulation_settings(device_id)
        if setting.get("event_type")
    }


def _build_countdown_cards(
    selected_mouse: str,
    stimulation_events: list[dict[str, object]],
) -> list[dict[str, object]]:
    latest_events = _latest_events_by_type(stimulation_events)
    return [
        {
            **item,
            **_event_countdown_payload(
                selected_mouse=selected_mouse,
                event_type=str(item["event_type"]),
                latest_event=latest_events.get(str(item["event_type"])),
            ),
        }
        for item in STIMULATION_TYPES
    ]


def _render_control_panel(
    selected_mouse: str,
    device_id: str | None,
) -> None:
    render_section_title(
        "造模刺激方案与实时执行",
        "配置光、声和电击刺激的随机间隔与持续时间，并实时观察当前执行状态",
    )

    control_online = get_control_connection_status(device_id)
    device_text = device_id or "未绑定设备"
    status_text = "可立即执行" if control_online else "暂未连接"
    st.caption(f"执行终端：{device_text} · {status_text}")

    _render_stable_countdown_panel(selected_mouse)

    if not device_id:
        st.warning("当前实验动物没有绑定刺激执行终端，暂时无法执行刺激。")
        return
    if not control_online:
        st.info("刺激执行终端暂未连接。设置可以保存，终端上线后请再次下发。")

    settings_by_type = _settings_by_type(device_id)
    tabs = st.tabs([str(item["label"]) for item in STIMULATION_TYPES])
    for tab, item in zip(tabs, STIMULATION_TYPES, strict=True):
        event_type = str(item["event_type"])
        setting = settings_by_type.get(event_type, {})
        enabled_default = bool(setting.get("enabled", True))
        defaults = {
            "min_interval": int(setting.get("min_interval_ms", item["default_min_interval_ms"])),
            "max_interval": int(setting.get("max_interval_ms", item["default_max_interval_ms"])),
            "min_duration": int(setting.get("min_duration_ms", item["default_min_duration_ms"])),
            "max_duration": int(setting.get("max_duration_ms", item["default_max_duration_ms"])),
        }

        with tab:
            st.toggle(
                "启用自动随机触发",
                value=enabled_default,
                key=_setting_key(device_id, event_type, "enabled"),
            )
            cols = st.columns(4)
            with cols[0]:
                st.number_input(
                    "最小间隔（秒）",
                    min_value=0,
                    max_value=3600,
                    value=_seconds_from_ms(defaults["min_interval"]),
                    step=1,
                    key=_setting_key(device_id, event_type, "min_interval"),
                )
            with cols[1]:
                st.number_input(
                    "最大间隔（秒）",
                    min_value=0,
                    max_value=3600,
                    value=_seconds_from_ms(defaults["max_interval"]),
                    step=1,
                    key=_setting_key(device_id, event_type, "max_interval"),
                )
            with cols[2]:
                st.number_input(
                    "最小刺激时间（秒）",
                    min_value=1,
                    max_value=60,
                    value=max(1, _seconds_from_ms(defaults["min_duration"])),
                    step=1,
                    key=_setting_key(device_id, event_type, "min_duration"),
                )
            with cols[3]:
                st.number_input(
                    "最大刺激时间（秒）",
                    min_value=1,
                    max_value=60,
                    value=max(1, _seconds_from_ms(defaults["max_duration"])),
                    step=1,
                    key=_setting_key(device_id, event_type, "max_duration"),
                )

            min_interval_ms = _current_setting_ms(device_id, event_type, "min_interval", defaults["min_interval"])
            max_interval_ms = _current_setting_ms(device_id, event_type, "max_interval", defaults["max_interval"])
            min_duration_ms = max(1_000, _current_setting_ms(device_id, event_type, "min_duration", defaults["min_duration"]))
            max_duration_ms = max(1_000, _current_setting_ms(device_id, event_type, "max_duration", defaults["max_duration"]))
            enabled = bool(st.session_state.get(_setting_key(device_id, event_type, "enabled"), enabled_default))

            if max_interval_ms < min_interval_ms:
                st.warning("最大间隔不能小于最小间隔。")
            if max_duration_ms < min_duration_ms:
                st.warning("最大刺激时间不能小于最小刺激时间。")

            action_cols = st.columns(2)
            with action_cols[0]:
                if st.button(
                    f"保存并下发{item['short_label']}刺激设置",
                    width="stretch",
                    key=f"save_stim_setting_{selected_mouse}_{event_type}",
                    disabled=max_interval_ms < min_interval_ms or max_duration_ms < min_duration_ms,
                ):
                    response = save_stimulation_setting(
                        mouse_id=selected_mouse,
                        device_id=device_id,
                        event_type=event_type,
                        enabled=enabled,
                        min_interval_ms=min_interval_ms,
                        max_interval_ms=max_interval_ms,
                        min_duration_ms=min_duration_ms,
                        max_duration_ms=max_duration_ms,
                    )
                    if response.get("success"):
                        delivered = bool(response.get("data", {}).get("delivered"))
                        if delivered:
                            st.success("刺激设置已保存，并已发送到执行终端。")
                        else:
                            st.warning("刺激设置已保存，但执行终端当前未连接。")
                    else:
                        st.error(_control_message(response))

            with action_cols[1]:
                if st.button(
                    f"立即执行{item['short_label']}刺激（无视倒计时）",
                    width="stretch",
                    type="primary",
                    key=f"manual_stim_{selected_mouse}_{event_type}",
                    disabled=max_duration_ms < min_duration_ms,
                ):
                    duration_ms = random.randint(min_duration_ms, max_duration_ms)
                    interval_ms = random.randint(min_interval_ms, max_interval_ms) if max_interval_ms >= min_interval_ms else 0
                    response = send_control_command(
                        selected_mouse,
                        device_id,
                        event_type,
                        duration_ms,
                    )
                    if response.get("success"):
                        _record_manual_countdown(
                            selected_mouse=selected_mouse,
                            event_type=event_type,
                            duration_ms=duration_ms,
                            interval_ms=interval_ms,
                        )
                        st.success(
                            f"已立即下发{item['label']}，本次随机刺激 {duration_ms / 1000:.1f} 秒，"
                            f"下一次倒计时已重置为 {(duration_ms + interval_ms) / 1000:.1f} 秒。"
                        )
                    else:
                        st.error(_control_message(response))


def render() -> None:
    animals = get_animals()
    if not animals:
        st.warning("暂无实验动物。请先在“实验动物”页面添加研究对象和采集终端。")
        return

    mouse_options = [str(animal["id"]) for animal in animals]
    if (
        st.session_state.get("monitor_mouse") == "MOUSE-002"
        and "MOUSE-001" in mouse_options
        and not st.session_state.get("monitor_mouse_default_migrated")
    ):
        st.session_state.monitor_mouse = "MOUSE-001"
        st.session_state.monitor_mouse_default_migrated = True
    current_mouse = st.session_state.monitor_mouse
    index = mouse_options.index(current_mouse) if current_mouse in mouse_options else 0
    selected_mouse = st.selectbox(
        "选择实验动物",
        mouse_options,
        index=index,
        key="monitor_mouse",
    )

    vital_df = get_vital_signs_frame(selected_mouse, 6, st.session_state.data_refresh_count)
    env_df = get_environment_frame(selected_mouse, 6, st.session_state.data_refresh_count)
    vision_summary = get_vision_summary(selected_mouse)
    latest = _latest_row(vital_df)
    env_latest = _latest_row(env_df)

    animal = next((item for item in animals if item["id"] == selected_mouse), {})
    device_id = animal.get("device_id")
    voltage = animal.get("voltage")
    current = animal.get("current")

    body_temperature = float(latest.get("temperature", 0))
    heart_rate = float(latest.get("heart_rate", 0))
    blood_oxygen = float(latest.get("blood_oxygen", 0))
    env_temperature = env_latest.get("environment_temperature")
    humidity = env_latest.get("humidity")

    metric_cols = st.columns(6)
    metrics = [
        ("小鼠体温", _number(body_temperature), "℃", "生理表型", "温", "高风险" if body_temperature >= 38 else "正常"),
        ("心率", _number(heart_rate, 0), "bpm", "生理表型", "率", "高风险" if heart_rate >= 470 else "正常"),
        ("血氧", _number(blood_oxygen), "%", "生理表型", "氧", "关注" if blood_oxygen < 94 else "正常"),
        ("环境温度", _number(env_temperature), "℃", "实验环境", "环", "正常"),
        ("环境湿度", _number(humidity), "%", "实验环境", "湿", "正常"),
        ("采集终端", f"{_number(voltage, 2)}V / {_number(current, 2)}A", "", "运行状态", "端", "正常"),
    ]
    for col, metric in zip(metric_cols, metrics, strict=True):
        with col:
            render_metric_card(*metric)

    render_section_title("视觉行为观测", f"当前研究对象：{selected_mouse}")
    render_camera_stream(selected_mouse)

    render_section_title("视觉行为量化", "基于视频关键点与帧间位移形成可供 Agent 使用的行为证据")
    _render_visual_behavior_summary(vision_summary)

    render_section_title(
        "生理与环境时序",
        f"同步展示 {selected_mouse} 的生命体征和实验环境变化",
    )
    chart_grid = st.columns(2)
    with chart_grid[0]:
        st.plotly_chart(create_temperature_chart(vital_df), width="stretch", config=PLOT_CONFIG)
    with chart_grid[1]:
        st.plotly_chart(create_heart_rate_chart(vital_df), width="stretch", config=PLOT_CONFIG)
    chart_grid_2 = st.columns(2)
    with chart_grid_2[0]:
        st.plotly_chart(create_blood_oxygen_chart(vital_df), width="stretch", config=PLOT_CONFIG)
    with chart_grid_2[1]:
        st.plotly_chart(create_environment_chart(env_df), width="stretch", config=PLOT_CONFIG)

    _render_control_panel(
        selected_mouse,
        str(device_id) if device_id else None,
    )

    render_section_title(
        "造模刺激记录",
        f"记录 {selected_mouse} 最近 24 小时接受的光、声和电击刺激过程",
    )
    _render_stable_stimulation_events_panel(selected_mouse)
