from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from components.animal_table import render_full_animal_table
from components.metric_card import render_kv_grid, render_metric_card, render_section_title
from components.stimulation_events import render_stimulation_metrics, render_stimulation_table
from data.backend_data import (
    create_animal_record,
    create_device_record,
    delete_animal_record,
    delete_device_record,
    get_agent_analysis,
    get_animals,
    get_devices,
    get_risk_events,
    get_status_history,
    get_stimulation_history,
    get_vision_summary,
    update_animal_device_binding,
    update_animal_stage,
)
from utils.constants import DEVICE_TYPE_LABELS, device_type_label

EXPERIMENT_STAGES = ["准备阶段", "适应阶段", "应激阶段", "行为测试阶段", "观察阶段", "完成"]
STATUS_OPTIONS = {
    "正常": "normal",
    "关注": "attention",
    "高风险": "high_risk",
    "离线": "offline",
}
DEVICE_TYPES = list(DEVICE_TYPE_LABELS)


def _safe_select_index(options: list[str], current: str) -> int:
    return options.index(current) if current in options else 0


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
        409: "编号已存在，或该记录仍有关联信息",
        422: "填写内容不完整或格式不正确",
        500: "数据保存失败，请稍后重试",
    }
    return messages.get(response.get("status_code"), "操作未完成，请稍后重试")


def _display_value(value: object, unit: str = "") -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{value}{unit}"


def _display_number(value: object, digits: int = 1, unit: str = "") -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        return f"{float(value):.{digits}f}{unit}"
    except (TypeError, ValueError):
        return str(value)


def _format_status_history(history: list[dict[str, object]]) -> pd.DataFrame:
    if not history:
        return pd.DataFrame()
    frame = pd.DataFrame(history)
    rename_map = {
        "mouse_id": "动物编号",
        "status": "状态",
        "reason": "原因",
        "recorded_at": "记录时间",
        "created_at": "保存时间",
    }
    frame = frame.rename(columns=rename_map)
    if "状态" in frame.columns:
        status_labels = {
            "normal": "正常",
            "attention": "关注",
            "high_risk": "高风险",
            "offline": "离线",
            "正常": "正常",
            "关注": "关注",
            "高风险": "高风险",
            "离线": "离线",
        }
        frame["状态"] = frame["状态"].map(lambda value: status_labels.get(str(value), "未知"))
    if "原因" in frame.columns:
        def display_reason(value: object) -> str:
            text = str(value or "").strip()
            if text.lower() == "mock initial status":
                return "系统初始化状态"
            if text.startswith("演示数据:") or text.startswith("演示数据："):
                return text[5:].strip()
            return text or "状态已更新"

        frame["原因"] = frame["原因"].map(display_reason)
    visible_columns = [column for column in rename_map.values() if column in frame.columns]
    return frame[visible_columns]


def _render_management_panel(animals: list[dict[str, object]]) -> None:
    devices = get_devices()
    mouse_ids = [str(animal.get("id")) for animal in animals if animal.get("id")]
    device_ids = [str(device.get("id")) for device in devices if device.get("id")]
    default_mouse_id = _next_code("MOUSE", mouse_ids)
    default_device_id = _next_code("ESP32", device_ids)

    render_section_title(
        "实验对象与采集终端配置",
        "维护实验动物、造模阶段和采集终端绑定关系，为多模态数据关联提供统一对象标识。",
    )

    add_mouse_col, add_device_col = st.columns(2)
    with add_mouse_col:
        with st.form("create_animal_form", clear_on_submit=True):
            st.markdown("**新增实验鼠**")
            mouse_id = st.text_input("动物编号", value=default_mouse_id, max_chars=50)
            experiment_stage = st.selectbox("造模阶段", EXPERIMENT_STAGES)
            status_label = st.selectbox("当前状态", list(STATUS_OPTIONS.keys()))
            submitted = st.form_submit_button("添加实验鼠", width="stretch")

        if submitted:
            clean_mouse_id = mouse_id.strip()
            if not clean_mouse_id:
                st.error("动物编号不能为空。")
            else:
                response = create_animal_record(
                    clean_mouse_id,
                    experiment_stage=experiment_stage,
                    current_status=STATUS_OPTIONS[status_label],
                )
                if _api_success(response):
                    st.success(f"已添加 {clean_mouse_id}。")
                    st.rerun()
                else:
                    st.error(f"添加失败：{_api_error_message(response)}")

    with add_device_col:
        bind_options = ["不绑定"] + mouse_ids
        with st.form("create_device_form", clear_on_submit=True):
            st.markdown("**新增设备**")
            device_id = st.text_input("设备编号", value=default_device_id, max_chars=50)
            device_type = st.selectbox(
                "设备类型",
                DEVICE_TYPES,
                format_func=device_type_label,
            )
            device_name = st.text_input("设备名称", value=f"{default_device_id} 实验箱 ESP32-S3", max_chars=100)
            bind_mouse = st.selectbox("绑定实验鼠", bind_options)
            submitted = st.form_submit_button("添加设备", width="stretch")

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

    with st.expander("调整造模阶段 / 切换绑定设备 / 删除实验鼠", expanded=False):
        if not animals:
            st.info("暂无实验鼠。")
        bind_options = ["未绑定"] + device_ids
        for animal in animals:
            mouse_id = str(animal.get("id") or "")
            current_stage = str(animal.get("stage") or "准备阶段")
            current_device = str(animal.get("device_id") or "未绑定")
            cols = st.columns([1.25, 1.35, 1.5, 1, 1.6, 1, 1])
            cols[0].markdown(f"**{mouse_id}**")
            cols[1].caption(f"状态：{animal.get('risk_level', '-')}")
            new_stage = cols[2].selectbox(
                "造模阶段",
                EXPERIMENT_STAGES,
                index=_safe_select_index(EXPERIMENT_STAGES, current_stage),
                key=f"stage_select_{mouse_id}",
                label_visibility="collapsed",
            )
            if cols[3].button("保存阶段", key=f"save_stage_{mouse_id}", width="stretch"):
                response = update_animal_stage(mouse_id, new_stage)
                if _api_success(response):
                    st.success(f"{mouse_id} 阶段已更新为 {new_stage}。")
                    st.rerun()
                else:
                    st.error(f"更新失败：{_api_error_message(response)}")
            new_device = cols[4].selectbox(
                "绑定设备",
                bind_options,
                index=_safe_select_index(bind_options, current_device),
                key=f"device_select_{mouse_id}",
                label_visibility="collapsed",
            )
            if cols[5].button("保存绑定", key=f"save_device_{mouse_id}", width="stretch"):
                response = update_animal_device_binding(
                    mouse_id,
                    None if new_device == "未绑定" else new_device,
                )
                if _api_success(response):
                    st.success(f"{mouse_id} 绑定设备已更新为 {new_device}。")
                    st.rerun()
                else:
                    st.error(f"绑定失败：{_api_error_message(response)}")
            if cols[6].button("删除", key=f"delete_animal_{mouse_id}", width="stretch"):
                response = delete_animal_record(mouse_id)
                if _api_success(response):
                    st.success(f"已删除 {mouse_id}。")
                    st.rerun()
                else:
                    st.error(f"删除失败：{_api_error_message(response)}")

    with st.expander("删除设备", expanded=False):
        if not devices:
            st.info("暂无设备。")
        for device in devices:
            device_id = str(device.get("id") or "")
            cols = st.columns([1.3, 1.2, 1.5, 1.1, 1])
            cols[0].markdown(f"**{device_id}**")
            cols[1].caption(f"类型：{device_type_label(device.get('type'))}")
            cols[2].caption(f"绑定：{device.get('target', '未绑定')}")
            cols[3].caption(f"状态：{device.get('status', '-')}")
            if cols[4].button("删除", key=f"delete_device_{device_id}", width="stretch"):
                response = delete_device_record(device_id)
                if _api_success(response):
                    st.success(f"已删除 {device_id}。")
                    st.rerun()
                else:
                    st.error(f"删除失败：{_api_error_message(response)}")


def render() -> None:
    animals = get_animals()

    df = pd.DataFrame(animals)
    if df.empty:
        st.info("尚未建立实验动物档案，请在下方完成首次登记。")
        _render_management_panel(animals)
        return

    total = len(df)
    normal = int((df["status_code"] == "normal").sum()) if "status_code" in df else 0
    attention = int((df["status_code"] == "attention").sum()) if "status_code" in df else 0
    high_risk = int((df["status_code"] == "high_risk").sum()) if "status_code" in df else 0
    offline = int((df["status_code"] == "offline").sum()) if "status_code" in df else int((~df["online"]).sum())

    metric_cols = st.columns(4)
    top_metrics = [
        ("实验动物总数", total, "只", "当前造模队列", "总", "正常"),
        ("正常动物", normal, "只", "多模态状态稳定", "稳", "正常"),
        ("重点关注", attention + high_risk, "只", f"高风险 {high_risk} 只", "关", "高风险" if high_risk else "关注"),
        ("离线", offline, "只", "等待设备恢复", "离", "离线" if offline else "正常"),
    ]
    for col, metric in zip(metric_cols, top_metrics, strict=True):
        with col:
            render_metric_card(*metric)

    filter_cols = st.columns(3)
    risk_options = ["全部"] + sorted(str(value) for value in df["risk_level"].dropna().unique())
    experiment_options = ["全部"] + sorted(str(value) for value in df["experiment"].dropna().unique())
    mouse_options = [str(value) for value in df["id"].tolist()]
    with filter_cols[0]:
        risk_filter = st.selectbox("风险等级筛选", risk_options)
    with filter_cols[1]:
        experiment_filter = st.selectbox("实验筛选", experiment_options)
    with filter_cols[2]:
        selected_mouse = st.selectbox(
            "查看动物详情",
            mouse_options,
            index=_safe_select_index(mouse_options, st.session_state.selected_mouse),
        )

    filtered = df.copy()
    if risk_filter != "全部":
        filtered = filtered[filtered["risk_level"] == risk_filter]
    if experiment_filter != "全部":
        filtered = filtered[filtered["experiment"] == experiment_filter]

    render_section_title("实验动物列表", f"当前筛选结果：{len(filtered)} 只")
    render_full_animal_table(filtered)

    animal = df[df["id"] == selected_mouse].iloc[0].to_dict()
    analysis = get_agent_analysis(selected_mouse)
    vision_summary = get_vision_summary(selected_mouse)
    related_alerts = get_risk_events([animal])
    status_history = get_status_history(selected_mouse)
    stimulation_history = get_stimulation_history(selected_mouse, hours=24, limit=100)

    render_section_title(
        "动物详情",
        "统一查看基础信息、生理表型、视觉行为、实验环境、刺激过程与风险评估",
    )
    detail_items = [
        ("动物编号", animal["id"]),
        ("绑定设备", animal.get("device_ids") or "未绑定"),
        ("当前实验", animal["experiment"]),
        ("造模阶段", animal["stage"]),
        ("入组时间", animal["group_time"]),
        ("小鼠体温", _display_number(animal.get("body_temperature"), 1, " ℃")),
        ("心率", _display_number(animal.get("heart_rate"), 0, " bpm")),
        ("血氧", _display_number(animal.get("blood_oxygen"), 1, " %")),
        ("环境温度", _display_number(animal.get("environment_temperature"), 1, " ℃")),
        ("环境湿度", _display_number(animal.get("humidity"), 1, " %")),
        ("黑暗环境", "是" if animal.get("is_dark") else "否"),
        ("有效观察画面", f"{int(vision_summary.get('feature_rows') or 0)} 帧"),
        ("累计活动距离", _display_number(vision_summary.get("total_movement_distance"), 2)),
        ("视觉识别可信度", _display_number(
            float(vision_summary["avg_frame_confidence"]) * 100
            if vision_summary.get("avg_frame_confidence") is not None
            else None,
            1,
            " %",
        )),
        ("在线状态", "在线" if animal["online"] else "离线"),
        ("设备电压", _display_number(animal.get("voltage"), 2, " V")),
        ("设备电流", _display_number(animal.get("current"), 2, " A")),
    ]
    if analysis:
        detail_items.extend(
            [
                ("Agent 风险评分", f"{analysis['risk_score']} / 100"),
                ("Agent 风险等级", analysis["risk_level"]),
            ]
        )
    render_kv_grid(detail_items)

    render_section_title(
        "刺激情况",
        f"显示 {selected_mouse} 最近 24 小时接受的光、声和电击刺激过程",
    )
    render_stimulation_metrics(stimulation_history, hours=24)
    render_stimulation_table(stimulation_history)

    left, right = st.columns(2)
    with left:
        render_section_title("状态历史", "记录实验人员或 Agent 辅助判断形成的状态变化")
        formatted_history = _format_status_history(status_history)
        if not formatted_history.empty:
            st.dataframe(formatted_history, width="stretch", hide_index=True)
        else:
            st.info("暂无状态历史。")
    with right:
        render_section_title("最近风险评估", "汇总异常描述与 Agent 辅助分析结论")
        st.markdown(
            f"""
            <div class="agent-card">
                <strong>异常描述</strong>
                <div style="margin-top:.45rem;color:#334155;line-height:1.75;">
                    {related_alerts[0]["description"] if related_alerts else "暂无异常记录"}
                </div>
                <strong>Agent 摘要</strong>
                <div style="margin-top:.35rem;color:#334155;line-height:1.75;">
                    {analysis["summary"] if analysis else "暂无 Agent 分析。"}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    _render_management_panel(animals)
