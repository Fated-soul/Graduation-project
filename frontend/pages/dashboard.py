from __future__ import annotations

from datetime import datetime

import streamlit as st

from components.agent_card import render_agent_card
from components.alert_list import render_alert_items
from components.animal_table import render_animal_table
from components.charts import PLOT_CONFIG, create_heart_rate_chart, create_temperature_chart
from components.device_status import render_device_status
from components.experiment_progress import render_experiment_progress
from components.metric_card import render_metric_card, render_section_title
from components.multimodal_overview import render_multimodal_overview
from data.backend_data import (
    get_animals,
    get_device_groups,
    get_experiments,
    get_risk_events,
    get_stimulation_history,
    get_telemetry_frame,
    get_vision_summary,
)
from utils.constants import TIME_RANGE_OPTIONS


def _time_range_selector() -> str:
    options = list(TIME_RANGE_OPTIONS)
    current = st.session_state.selected_time_range
    index = options.index(current) if current in options else 0
    selected = st.radio(
        "时间范围",
        options,
        horizontal=True,
        index=index,
        key="dashboard_time_range_radio",
    )
    st.session_state.selected_time_range = selected
    return selected


def render() -> None:
    animals = get_animals()
    experiments = get_experiments(animals)
    device_groups = get_device_groups()
    risk_events = get_risk_events(animals)

    total_animals = len(animals)
    online_animals = sum(1 for animal in animals if animal.get("online"))
    high_risk = sum(1 for animal in animals if animal.get("status_code") == "high_risk")
    attention = sum(1 for animal in animals if animal.get("status_code") == "attention")
    average_progress = round(
        sum(int(experiment["progress"]) for experiment in experiments) / len(experiments)
    ) if experiments else 0

    with st.container(border=True):
        controls = st.columns([1.2, 1.2, 0.8])
        with controls[0]:
            mouse_options = [str(animal["id"]) for animal in animals]
            current_mouse = st.session_state.selected_mouse
            if mouse_options:
                index = mouse_options.index(current_mouse) if current_mouse in mouse_options else 0
                selected_mouse = st.selectbox("当前研究对象", mouse_options, index=index, key="selected_mouse")
            else:
                selected_mouse = ""
                st.session_state.selected_mouse = ""
                st.selectbox("当前研究对象", ["暂无实验动物"], disabled=True)
        with controls[1]:
            selected_range = _time_range_selector()
        with controls[2]:
            st.markdown('<div class="toolbar-label">数据更新</div>', unsafe_allow_html=True)
            if st.button("刷新当前数据", width="stretch", type="primary"):
                st.session_state.data_refresh_count += 1
                st.session_state.last_refresh_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.rerun()
            st.caption(f"最近刷新：{st.session_state.last_refresh_time}")

    selected_animal = next(
        (animal for animal in animals if str(animal["id"]) == selected_mouse),
        {},
    )
    vision_summary = get_vision_summary(selected_mouse) if selected_mouse else {}
    stimulation_events = (
        get_stimulation_history(selected_mouse, hours=24, limit=100)
        if selected_mouse
        else []
    )
    modality_count = sum(
        (
            any(selected_animal.get(key) is not None for key in ("body_temperature", "heart_rate", "blood_oxygen")),
            bool(int(vision_summary.get("feature_rows") or 0)),
            any(selected_animal.get(key) is not None for key in ("environment_temperature", "humidity", "is_dark")),
            bool(stimulation_events),
        )
    )

    metric_cols = st.columns(4)
    metrics = [
        ("在组动物", total_animals, "只", f"在线 {online_animals} 只", "鼠", "正常" if online_animals == total_animals else "关注"),
        ("当前数据覆盖", modality_count, "/ 4", "生理 · 行为 · 环境 · 刺激", "融", "正常" if modality_count == 4 else "关注"),
        ("待复核对象", len(risk_events), "只", f"高风险 {high_risk} · 关注 {attention}", "险", "高风险" if high_risk else "关注" if risk_events else "正常"),
        ("队列进度", average_progress, "%", "行为无助造模", "程", "正常"),
    ]
    for col, metric in zip(metric_cols, metrics, strict=True):
        with col:
            render_metric_card(*metric)

    if selected_mouse:
        render_multimodal_overview(
            selected_mouse,
            selected_animal,
            vision_summary,
            stimulation_events,
        )
    else:
        st.info("尚未建立实验动物档案，请先在“实验动物”页面添加研究对象。")

    render_section_title("生理表型趋势", f"{selected_mouse or '当前无研究对象'} · {selected_range}")
    chart_cols = st.columns(2)
    if selected_mouse:
        vital_df = get_telemetry_frame(
            selected_mouse,
            TIME_RANGE_OPTIONS[selected_range],
            st.session_state.data_refresh_count,
        )
        with chart_cols[0]:
            st.plotly_chart(create_temperature_chart(vital_df), width="stretch", config=PLOT_CONFIG)
        with chart_cols[1]:
            st.plotly_chart(create_heart_rate_chart(vital_df), width="stretch", config=PLOT_CONFIG)
    else:
        with chart_cols[0]:
            st.info("暂无体温趋势数据。")
        with chart_cols[1]:
            st.info("暂无心率趋势数据。")

    agent_col, side_col = st.columns([1.08, 0.92])
    with agent_col:
        if selected_mouse:
            render_agent_card(selected_mouse)
        else:
            st.info("请选择研究对象后查看辅助评估。")
        if st.session_state.control_logs:
            render_section_title("最近决策执行记录", "实验人员确认后的刺激控制操作")
            display_logs = [
                {
                    "执行时间": log.get("timestamp", "-"),
                    "实验动物": log.get("mouse_id", "-"),
                    "执行内容": log.get("command", "-"),
                    "建议来源": log.get("source", "-"),
                    "当前状态": log.get("status", "-"),
                }
                for log in st.session_state.control_logs[:5]
            ]
            st.dataframe(display_logs, width="stretch", hide_index=True)
    with side_col:
        render_section_title("行为无助造模进度", "当前实验队列阶段与完成度")
        if experiments:
            for experiment in experiments:
                render_experiment_progress(experiment)
        else:
            st.info("尚未建立造模队列。")

    render_section_title("实验动物队列", "当前阶段、关键体征与风险状态")
    render_animal_table(animals, limit=6)

    lower_left, lower_right = st.columns([1.04, 0.96])
    with lower_left:
        render_section_title("待复核风险", "由当前状态和最新辅助评估形成")
        if risk_events:
            render_alert_items(risk_events[:4], compact=True)
        else:
            st.info("当前没有需要人工复核的风险对象。")
    with lower_right:
        render_section_title("采集终端状态", "判断多模态数据采集链路是否完整")
        if device_groups:
            for device_group in device_groups:
                render_device_status(
                    str(device_group["name"]),
                    str(device_group["status"]),
                    device_group["current"],
                    device_group["total"],
                )
        else:
            st.info("尚未登记采集终端。")
