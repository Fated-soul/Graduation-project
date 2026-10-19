from __future__ import annotations

import re

import streamlit as st

from components.device_status import render_device_table
from components.metric_card import render_metric_card, render_section_title
from data.backend_data import create_device_record, delete_device_record, get_animals, get_devices
from utils.constants import DEVICE_TYPE_LABELS, device_type_label

DEVICE_TYPES = list(DEVICE_TYPE_LABELS)


def _next_code(prefix: str, existing: list[str]) -> str:
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    numbers = []
    for value in existing:
        match = pattern.match(value)
        if match:
            numbers.append(int(match.group(1)))
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def _api_success(response: dict[str, object] | None) -> bool:
    return bool(response and response.get("success") is True)


def _api_error_message(response: dict[str, object] | None) -> str:
    if response is None:
        return "数据服务暂时不可用，请稍后重试"
    messages = {
        400: "提交内容不符合要求，请检查后重试",
        404: "未找到要操作的记录",
        409: "编号已存在，或该记录仍被实验对象使用",
        422: "填写内容不完整或格式不正确",
        500: "数据保存失败，请稍后重试",
    }
    return messages.get(response.get("status_code"), "操作未完成，请稍后重试")


def _render_device_management(devices: list[dict[str, object]]) -> None:
    animals = get_animals()
    mouse_ids = [str(animal.get("id")) for animal in animals if animal.get("id")]
    device_ids = [str(device.get("id")) for device in devices if device.get("id")]
    default_device_id = _next_code("ESP32", device_ids)

    render_section_title("采集终端配置", "终端可独立维护，并按实验需要绑定到任意研究对象。")
    with st.form("device_page_create_form", clear_on_submit=True):
        cols = st.columns([1.1, 1.1, 1.8, 1.2, 1])
        device_id = cols[0].text_input("设备编号", value=default_device_id, max_chars=50)
        device_type = cols[1].selectbox(
            "设备类型",
            DEVICE_TYPES,
            format_func=device_type_label,
        )
        device_name = cols[2].text_input("设备名称", value=f"{default_device_id} 实验箱 ESP32-S3", max_chars=100)
        bind_mouse = cols[3].selectbox("绑定实验鼠", ["不绑定"] + mouse_ids)
        submitted = cols[4].form_submit_button("添加设备", width="stretch")

    if submitted:
        clean_device_id = device_id.strip()
        clean_device_name = device_name.strip()
        if not clean_device_id or not clean_device_name:
            st.error("设备编号和设备名称不能为空。")
        else:
            response = create_device_record(
                clean_device_id,
                clean_device_name,
                device_type=device_type,
                mouse_id=None if bind_mouse == "不绑定" else bind_mouse,
            )
            if _api_success(response):
                st.success(f"已添加 {clean_device_id}。")
                st.rerun()
            else:
                st.error(f"添加失败：{_api_error_message(response)}")

    with st.expander("删除设备", expanded=False):
        if not devices:
            st.info("暂无设备。")
        for device in devices:
            device_id = str(device.get("id") or "")
            cols = st.columns([1.4, 1.2, 1.6, 1])
            cols[0].markdown(f"**{device_id}**")
            cols[1].caption(f"类型：{device_type_label(device.get('type'))}")
            cols[2].caption(f"绑定：{device.get('target', '未绑定')}")
            if cols[3].button("删除", key=f"devices_page_delete_{device_id}", width="stretch"):
                response = delete_device_record(device_id)
                if _api_success(response):
                    st.success(f"已删除 {device_id}。")
                    st.rerun()
                else:
                    st.error(f"删除失败：{_api_error_message(response)}")


def render() -> None:
    devices = get_devices()
    total = len(devices)
    online = sum(1 for device in devices if device.get("online"))
    offline = total - online
    abnormal = sum(1 for device in devices if device.get("status") == "异常")

    metric_cols = st.columns(4)
    metrics = [
        ("采集终端", total, "台", "传感器、摄像头与执行终端", "端", "正常"),
        ("在线", online, "台", "数据采集链路可用", "在", "正常"),
        ("异常", abnormal, "台", "需要检查数据质量", "异", "关注" if abnormal else "正常"),
        ("离线", offline, "台", "可能造成模态数据缺失", "离", "高风险" if offline else "正常"),
    ]
    for col, metric in zip(metric_cols, metrics, strict=True):
        with col:
            render_metric_card(*metric)

    render_section_title("采集与刺激终端", "查看终端绑定对象、在线状态、供电情况和最近通信时间")
    render_device_table(devices)

    _render_device_management(devices)
