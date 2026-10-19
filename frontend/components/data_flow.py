from __future__ import annotations

from html import escape

import streamlit as st


FLOW_NODES: list[tuple[str, str, bool]] = [
    ("生理表型", "体温 / 心率 / 血氧", False),
    ("视觉行为", "姿态 / 位移 / 活动", False),
    ("实验环境", "温湿度 / 明暗", False),
    ("刺激过程", "光 / 声 / 电击", False),
    ("多模态融合", "时间对齐与证据汇聚", False),
    ("Agent 辅助决策", "风险解释与参数建议", True),
]


def render_data_flow() -> None:
    nodes = ""
    for title, desc, is_agent in FLOW_NODES:
        agent_class = " agent" if is_agent else ""
        nodes += f"""
        <div class="flow-node{agent_class}">
            <div class="flow-title">{escape(title)}</div>
            <div class="flow-desc">{escape(desc)}</div>
        </div>
        """
    st.markdown(
        f"""
        <div class="soft-card">
            <div class="section-title">
                <div>
                    <h3>多模态辅助决策流程</h3>
                    <div class="section-subtitle">以实验对象为中心汇聚多源证据，并由研究人员确认造模决策</div>
                </div>
            <span class="pill">多模态融合 + Agent</span>
            </div>
            <div class="flow-grid">{nodes}</div>
            <div class="flow-caption">采集 → 对齐 → 融合 → 评估 → 建议 → 人工确认</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
