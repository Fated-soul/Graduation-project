from __future__ import annotations

from html import escape

import streamlit as st

from utils.constants import device_type_label


def _device_status_class(status: str) -> tuple[str, str]:
    if status in {"在线", "正常"}:
        return "status-normal", "dot"
    if status in {"部分异常", "异常"}:
        return "status-warning", "dot warn"
    return "status-danger", "dot danger"


def render_device_status(
    name: str,
    status: str,
    current: int | None = None,
    total: int | None = None,
) -> None:
    name = device_type_label(name)
    css_class, dot_class = _device_status_class(status)
    count = f"{current} / {total} 在线" if current is not None and total is not None else status
    st.markdown(
        f"""
        <div class="soft-card" style="margin-bottom:.65rem;padding:.78rem .82rem;">
            <div style="display:flex;justify-content:space-between;align-items:center;gap:.8rem;">
                <div style="display:flex;align-items:center;gap:.62rem;">
                    <span class="{dot_class}"></span>
                    <strong style="color:#17324d;">{escape(name)}</strong>
                </div>
                <span class="status-pill {css_class}">{escape(count)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_device_table(devices: list[dict[str, object]]) -> None:
    def reading(value: object, unit: str) -> str:
        if value is None:
            return "-"
        try:
            return f"{float(value):.2f} {unit}"
        except (TypeError, ValueError):
            return "-"

    rows = ""
    for device in devices:
        css_class, dot_class = _device_status_class(str(device["status"]))
        issue = str(device.get("issue", "")) or "正常"
        rows += f"""
        <tr>
            <td><strong>{escape(str(device["id"]))}</strong></td>
            <td>{escape(device_type_label(device.get("type")))}</td>
            <td>{escape(str(device["target"]))}</td>
            <td>{escape(str(device["location"]))}</td>
            <td><span class="status-pill {css_class}"><span class="{dot_class}"></span>{escape(str(device["status"]))}</span></td>
            <td>{escape(str(device["last_seen"]))}</td>
            <td>{escape(reading(device.get("voltage"), "V"))}</td>
            <td>{escape(reading(device.get("current"), "A"))}</td>
            <td>{escape(issue)}</td>
        </tr>
        """

    st.markdown(
        f"""
        <table class="data-table">
            <thead>
                <tr>
                    <th>设备编号</th>
                    <th>设备类型</th>
                    <th>绑定对象</th>
                    <th>设备位置</th>
                    <th>在线状态</th>
                    <th>最后通信时间</th>
                    <th>供电电压</th>
                    <th>工作电流</th>
                    <th>运行情况</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )
