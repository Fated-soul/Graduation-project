from __future__ import annotations

from html import escape

import streamlit as st

from utils.constants import RISK_COLOR_CLASS


def status_class(status: str) -> str:
    fallback = {
        "正常": "status-normal",
        "在线": "status-normal",
        "进行中": "status-normal",
        "关注": "status-warning",
        "警告": "status-warning",
        "部分异常": "status-warning",
        "高风险": "status-danger",
        "异常": "status-danger",
        "设备异常": "status-agent",
        "数据异常": "status-muted",
        "离线": "status-muted",
    }
    return RISK_COLOR_CLASS.get(status) or fallback.get(status, "status-normal")


def render_status_pill(label: str, status: str | None = None) -> str:
    css_class = status_class(status or label)
    return f'<span class="status-pill {css_class}">{escape(label)}</span>'


def render_metric_card(
    title: str,
    value: str | int | float,
    unit: str,
    subtitle: str,
    icon: str,
    status: str = "正常",
) -> None:
    html = (
        '<div class="metric-card">'
        '<div class="metric-top">'
        f"<span>{escape(title)}</span>"
        f'<span class="metric-icon">{escape(icon)}</span>'
        "</div>"
        f'<div class="metric-value">{escape(str(value))}<span class="metric-unit">{escape(unit)}</span></div>'
        f'<div class="metric-subtitle">{render_status_pill(subtitle, status)}</div>'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_section_title(title: str, subtitle: str | None = None, right: str | None = None) -> None:
    right_html = f"<div>{right}</div>" if right else ""
    subtitle_html = f'<div class="section-subtitle">{escape(subtitle)}</div>' if subtitle else ""
    html = (
        '<div class="section-title">'
        "<div>"
        f"<h3>{escape(title)}</h3>"
        f"{subtitle_html}"
        "</div>"
        f"{right_html}"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def render_kv_grid(items: list[tuple[str, str | int | float]]) -> None:
    cells = "".join(
        (
            '<div class="kv-item">'
            f'<div class="kv-label">{escape(str(label))}</div>'
            f'<div class="kv-value">{escape(str(value))}</div>'
            "</div>"
        )
        for label, value in items
    )
    st.markdown(f'<div class="kv-grid">{cells}</div>', unsafe_allow_html=True)
