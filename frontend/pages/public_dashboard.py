from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.charts import PLOT_CONFIG
from components.metric_card import render_metric_card, render_section_title
from data.public_dataset import format_datetime, format_size, get_sessions, get_source, get_stats


STAGE_ORDER = ["基线适应", "恐惧条件化造模", "记忆回忆评估", "离线记忆巩固", "跨周随访"]


def render() -> None:
    source = get_source()
    stats = get_stats()
    sessions = get_sessions(limit=100)

    metrics = [
        ("实验动物", stats.get("subject_count", 0), "只", "纵向追踪对象", "鼠"),
        ("造模会话", stats.get("session_count", 0), "次", "覆盖完整研究阶段", "会"),
        ("已载入会话", stats.get("imported_session_count", 0), "次", "可开展证据复核", "证"),
        ("辅助分析", stats.get("analysis_count", 0), "份", "保留结论与依据", "析"),
    ]
    for column, metric in zip(st.columns(4), metrics, strict=True):
        with column:
            render_metric_card(*metric, status="正常")

    if source is None:
        st.info("尚未建立研究数据目录，请先前往“数据来源”同步 DANDI 000718。")
        return

    render_section_title("造模研究概况", "从基线、条件化造模到离线巩固与回忆评估的纵向证据链")
    with st.container(border=True):
        left, right = st.columns([1.55, 0.45])
        with left:
            st.markdown("### DANDI 000718 · 跨日记忆连接研究")
            st.write(
                "系统以同一实验动物的行为视频、足底电击、冻结行为、单光子钙成像、"
                "EEG、EMG 与睡眠状态为依据，组织多阶段智能造模评估。"
            )
            st.caption(
                f"固定版本 {source.get('version', '-')} · 最近同步 "
                f"{format_datetime(source.get('last_synced_at'))}"
            )
        with right:
            st.metric("公开资产", int(source.get("asset_count") or 0))
            st.metric("原始规模", format_size(source.get("total_size_bytes")))

    if sessions:
        stage_counts = (
            pd.DataFrame({"造模阶段": [item.get("modeling_stage") or "未分类" for item in sessions]})
            .value_counts("造模阶段")
            .rename("会话数")
            .reset_index()
        )
        stage_counts["顺序"] = stage_counts["造模阶段"].map(
            {name: index for index, name in enumerate(STAGE_ORDER)}
        ).fillna(99)
        stage_counts = stage_counts.sort_values("顺序")
        modality = pd.DataFrame(
            {
                "记录类型": ["行为视频", "冻结行为", "足底电击", "钙成像", "EEG", "EMG", "睡眠状态"],
                "会话数": [
                    stats.get("video_session_count", 0),
                    stats.get("freezing_session_count", 0),
                    stats.get("shock_session_count", 0),
                    stats.get("calcium_session_count", 0),
                    stats.get("eeg_session_count", 0),
                    stats.get("emg_session_count", 0),
                    stats.get("sleep_session_count", 0),
                ],
            }
        )
        left, right = st.columns([1, 1])
        with left:
            figure = px.bar(
                stage_counts,
                x="造模阶段",
                y="会话数",
                title="造模阶段覆盖",
                color="造模阶段",
                color_discrete_sequence=["#0ea5e9", "#e45756", "#8b5cf6", "#10b981", "#f59e0b"],
            )
            figure.update_layout(showlegend=False, height=350, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG)
        with right:
            figure = px.bar(
                modality,
                x="记录类型",
                y="会话数",
                title="多模态证据覆盖",
                color="记录类型",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            figure.update_layout(showlegend=False, height=350, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG)

    render_section_title("最近造模会话", "按实验动物和研究阶段查看记录就绪情况")
    if not sessions:
        st.info("当前还没有造模会话。")
        return
    st.dataframe(
        [
            {
                "实验动物": item.get("subject_code"),
                "研究阶段": item.get("modeling_stage") or "未分类",
                "会话时间": format_datetime(item.get("session_started_at")),
                "主要证据": _evidence_summary(item),
                "复核状态": "可复核" if item.get("import_status") == "ready" else "待载入",
            }
            for item in sessions[:12]
        ],
        hide_index=True,
        width="stretch",
    )


def _evidence_summary(item: dict) -> str:
    labels = [
        label
        for key, label in (
            ("has_video", "视频"),
            ("has_freezing", "冻结"),
            ("has_shock", "电击"),
            ("has_calcium", "钙成像"),
            ("has_eeg", "EEG"),
            ("has_emg", "EMG"),
            ("has_sleep_states", "睡眠"),
        )
        if item.get(key)
    ]
    return "、".join(labels) if labels else "会话元数据"
