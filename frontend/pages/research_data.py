from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.charts import PLOT_CONFIG
from components.metric_card import render_metric_card, render_section_title
from data.public_dataset import get_sessions, get_stats


def render() -> None:
    stats = get_stats()
    sessions = get_sessions(limit=500)
    metrics = [
        ("造模事件", stats.get("modeling_event_count", 0), "条", "刺激、冻结与睡眠区间", "事"),
        ("信号时间窗", stats.get("signal_window_count", 0), "个", "跨模态统计摘要", "窗"),
        ("钙成像 ROI", stats.get("calcium_roi_count", 0), "个", "细胞活动指标", "钙"),
        ("人工复核", stats.get("annotation_count", 0), "条", "保留观察依据", "注"),
    ]
    for column, metric in zip(st.columns(4), metrics, strict=True):
        with column:
            render_metric_card(*metric, status="正常")

    render_section_title("多模态数据构成", "查看各证据类型在造模会话中的覆盖情况")
    modality = pd.DataFrame(
        {
            "证据类型": ["视频", "冻结", "电击", "钙成像", "EEG", "EMG", "睡眠状态"],
            "会话数": [
                stats.get("video_session_count", 0), stats.get("freezing_session_count", 0),
                stats.get("shock_session_count", 0), stats.get("calcium_session_count", 0),
                stats.get("eeg_session_count", 0), stats.get("emg_session_count", 0),
                stats.get("sleep_session_count", 0),
            ],
        }
    )
    stages = pd.DataFrame(
        {"研究阶段": [item.get("modeling_stage") or "未分类" for item in sessions]}
    ).value_counts("研究阶段").rename("会话数").reset_index() if sessions else pd.DataFrame()
    left, right = st.columns(2)
    with left:
        figure = px.bar(modality, x="证据类型", y="会话数", color="证据类型", title="证据覆盖")
        figure.update_layout(showlegend=False, height=350, margin=dict(l=10, r=10, t=50, b=10))
        st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG)
    with right:
        if not stages.empty:
            figure = px.pie(stages, names="研究阶段", values="会话数", hole=0.5, title="研究阶段构成")
            figure.update_layout(height=350, margin=dict(l=10, r=10, t=50, b=10))
            st.plotly_chart(figure, width="stretch", config=PLOT_CONFIG)

    render_section_title("研究数据治理", "来源、版本、会话、证据与结论保持可追溯关联")
    st.dataframe(
        [
            {"检查内容": "公开来源与固定版本", "当前状态": "DANDI 000718 / 0.260825.1902"},
            {"检查内容": "实验动物与纵向会话", "当前状态": f"{stats.get('subject_count', 0)} 只动物 / {stats.get('session_count', 0)} 次会话"},
            {"检查内容": "会话证据载入", "当前状态": f"已完成 {stats.get('imported_session_count', 0)} 次会话"},
            {"检查内容": "人工复核与 Agent 留痕", "当前状态": f"{stats.get('annotation_count', 0)} 条复核 / {stats.get('analysis_count', 0)} 份分析"},
        ],
        hide_index=True,
        width="stretch",
    )
