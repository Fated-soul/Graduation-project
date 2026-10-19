from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.charts import PLOT_CONFIG
from components.metric_card import render_section_title
from data.public_dataset import format_datetime, get_sessions, get_subjects


STAGE_ORDER = ["基线适应", "恐惧条件化造模", "记忆回忆评估", "离线记忆巩固", "跨周随访"]


def render() -> None:
    subjects = get_subjects()
    if not subjects:
        st.info("尚未同步实验动物，请先在“数据来源”建立研究目录。")
        return

    selected = st.selectbox("选择实验动物", [str(item["subject_id"]) for item in subjects])
    subject = next(item for item in subjects if str(item["subject_id"]) == selected)
    sessions = get_sessions(selected, limit=100)
    metadata = subject.get("metadata") or {}

    with st.container(border=True):
        st.markdown(f"### 实验动物 {selected}")
        cols = st.columns(5)
        cols[0].metric("物种", str(subject.get("species") or "小鼠"))
        cols[1].metric("品系", str(metadata.get("strain") or "C57BL/6J"))
        cols[2].metric("基因型", "野生型" if metadata.get("genotype") == "wild-type" else str(metadata.get("genotype") or "未记录"))
        cols[3].metric("会话数量", int(subject.get("session_count") or 0))
        cols[4].metric("视频会话", int(subject.get("video_count") or 0))
        st.caption(
            f"纵向记录范围：{format_datetime(subject.get('first_session_at'))} 至 "
            f"{format_datetime(subject.get('last_session_at'))}"
        )

    render_section_title("纵向造模轨迹", "按时间观察基线、条件化、离线巩固和回忆评估")
    if sessions:
        frame = pd.DataFrame(
            {
                "会话时间": pd.to_datetime([item.get("session_started_at") for item in sessions], errors="coerce"),
                "研究阶段": [item.get("modeling_stage") or "未分类" for item in sessions],
                "会话": [item.get("session_id") for item in sessions],
                "记录状态": ["已载入" if item.get("import_status") == "ready" else "目录已建立" for item in sessions],
            }
        ).sort_values("会话时间")
        figure = px.scatter(
            frame,
            x="会话时间",
            y="研究阶段",
            color="研究阶段",
            symbol="记录状态",
            hover_data=["会话", "记录状态"],
            category_orders={"研究阶段": STAGE_ORDER},
            color_discrete_sequence=["#0ea5e9", "#e45756", "#8b5cf6", "#10b981", "#f59e0b"],
        )
        figure.update_traces(marker=dict(size=14))
        figure.update_layout(height=330, showlegend=False, margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG)

    render_section_title("会话与证据", "查看每个阶段实际记录的多模态信息")
    st.dataframe(
        [
            {
                "会话时间": format_datetime(item.get("session_started_at")),
                "研究阶段": item.get("modeling_stage") or "未分类",
                "行为视频": "有" if item.get("has_video") else "无",
                "冻结行为": "有" if item.get("has_freezing") else "无",
                "足底电击": "有" if item.get("has_shock") else "无",
                "钙成像": "有" if item.get("has_calcium") else "无",
                "EEG/EMG": "有" if item.get("has_eeg") or item.get("has_emg") else "无",
                "睡眠状态": "有" if item.get("has_sleep_states") else "无",
                "内容状态": "已载入" if item.get("import_status") == "ready" else "可按需载入",
            }
            for item in sessions
        ],
        hide_index=True,
        width="stretch",
    )
