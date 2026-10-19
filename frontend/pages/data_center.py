from __future__ import annotations

from datetime import datetime

import streamlit as st

from components.charts import PLOT_CONFIG, create_bar_chart, create_data_trend_chart, create_donut_chart
from components.metric_card import render_metric_card, render_section_title
from data.backend_data import backend_summary, get_agent_analysis, get_animals, get_data_center_metrics


def render() -> None:
    animals = get_animals()
    summary = backend_summary()
    data = get_data_center_metrics(st.session_state.data_refresh_count)

    telemetry_total = int(data["trend"].iloc[:, 1].sum()) if not data["trend"].empty else 0
    type_name_col, type_value_col = data["type_share"].columns[:2]
    type_counts = {
        str(row[type_name_col]): int(row[type_value_col])
        for _, row in data["type_share"].iterrows()
    }
    available_modalities = sum(1 for value in type_counts.values() if value > 0)
    analysis_count = sum(1 for animal in animals if get_agent_analysis(str(animal["id"])))
    data_service = "已连接" if summary["connected"] else "未连接"

    metric_cols = st.columns(4)
    metrics = [
        ("24h 时序记录", telemetry_total, "条", "生理与环境连续采集", "数", "正常"),
        ("有效数据模态", available_modalities, "/ 4", "生理 · 行为 · 环境 · 刺激", "融", "正常" if available_modalities == 4 else "关注"),
        ("实验动物", len(animals), "只", "纳入当前造模队列", "鼠", "正常"),
        ("Agent 评估", analysis_count, "只", f"数据服务{data_service}", "智", "正常" if summary["connected"] else "关注"),
    ]
    for col, metric in zip(metric_cols, metrics, strict=True):
        with col:
            render_metric_card(*metric)

    render_section_title("多模态研究数据", "观察各类实验数据的采集规模、构成和覆盖情况")
    chart_cols = st.columns(2)
    with chart_cols[0]:
        st.plotly_chart(create_data_trend_chart(data["trend"]), width="stretch", config=PLOT_CONFIG)
    with chart_cols[1]:
        st.plotly_chart(create_donut_chart(data["type_share"]), width="stretch", config=PLOT_CONFIG)
    chart_cols_2 = st.columns(2)
    with chart_cols_2[0]:
        exp_x, exp_y = data["experiments"].columns[:2]
        st.plotly_chart(create_bar_chart(data["experiments"], exp_x, exp_y, "造模队列规模", "#06b6d4"), width="stretch", config=PLOT_CONFIG)
    with chart_cols_2[1]:
        dev_x, dev_y = data["devices"].columns[:2]
        st.plotly_chart(create_bar_chart(data["devices"], dev_x, dev_y, "采集终端可用状态", "#8b5cf6"), width="stretch", config=PLOT_CONFIG)

    st.markdown(
        f"""
        <div class="soft-card">
            <div class="section-title">
                <div><h3>数据治理与分析链路</h3><div class="section-subtitle">最近汇聚时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div></div>
                <span class="pill">采集 → 对齐 → 融合 → 决策</span>
            </div>
            <div class="kv-grid">
                <div class="kv-item"><div class="kv-label">生理表型</div><div class="kv-value">{type_counts.get("生命体征", 0)} 条记录</div></div>
                <div class="kv-item"><div class="kv-label">视觉行为</div><div class="kv-value">{type_counts.get("视觉行为", 0)} 帧特征</div></div>
                <div class="kv-item"><div class="kv-label">实验环境</div><div class="kv-value">{type_counts.get("实验环境", 0)} 条记录</div></div>
                <div class="kv-item"><div class="kv-label">刺激过程</div><div class="kv-value">{type_counts.get("刺激过程", 0)} 条事件</div></div>
                <div class="kv-item"><div class="kv-label">Agent 评估覆盖</div><div class="kv-value">{analysis_count} / {len(animals)} 只</div></div>
                <div class="kv-item"><div class="kv-label">研究数据服务</div><div class="kv-value">{data_service}</div></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
