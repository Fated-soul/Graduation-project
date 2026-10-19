from __future__ import annotations

from html import escape

import streamlit as st

from components.metric_card import render_status_pill


def _alert_class(level: str) -> str:
    return "high" if level == "高风险" else ""


def _show_alert_detail(alert: dict[str, str]) -> None:
    def render_body() -> None:
        st.markdown(
            f"""
            <div class="soft-card">
                <div class="kv-grid">
                    <div class="kv-item"><div class="kv-label">预警时间</div><div class="kv-value">{escape(alert["time"])}</div></div>
                    <div class="kv-item"><div class="kv-label">对象</div><div class="kv-value">{escape(alert["target"])}</div></div>
                    <div class="kv-item"><div class="kv-label">风险等级</div><div class="kv-value">{escape(alert["level"])}</div></div>
                    <div class="kv-item"><div class="kv-label">复核状态</div><div class="kv-value">{escape(alert["status"])}</div></div>
                </div>
                <div style="margin-top:.75rem;line-height:1.75;color:#334155;">
                    <strong>异常数据：</strong>{escape(alert["abnormal_data"])}<br>
                    <strong>Agent 分析：</strong>{escape(alert["agent_judgement"])}<br>
                    <strong>Agent 建议：</strong>{escape(alert["advice"])}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_animal, col_agent = st.columns(2)
        with col_animal:
            if st.button("查看动物档案", key=f"animal_{alert['id']}", width="stretch"):
                st.session_state.selected_mouse = alert["target"]
                st.session_state.current_page = "实验动物"
                st.rerun()
        with col_agent:
            if st.button("进入辅助决策", key=f"agent_{alert['id']}", width="stretch", type="primary"):
                st.session_state.agent_selected_mouse = alert["target"]
                st.session_state.current_page = "Agent 辅助决策"
                st.rerun()

    if hasattr(st, "dialog"):
        @st.dialog("预警详情")
        def dialog() -> None:
            render_body()

        dialog()
    else:
        render_body()


def render_alert_items(alerts: list[dict[str, str]], compact: bool = False) -> None:
    for alert in alerts:
        st.markdown(
            f"""
            <div class="alert-item {_alert_class(alert["level"])}">
                <div style="display:flex;justify-content:space-between;gap:.7rem;align-items:flex-start;">
                    <div>
                        {render_status_pill(alert["level"])}
                        <strong style="margin-left:.45rem;color:#17324d;">{escape(alert["target"])}</strong>
                        <div style="margin-top:.35rem;color:#334155;">{escape(alert["description"])}</div>
                        <div class="section-subtitle">{escape(alert["ago"])} · Agent：{escape(alert["agent_judgement"])}</div>
                    </div>
                    <span class="pill">{escape(alert["status"])}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not compact:
            if st.button("查看详情", key=f"alert_detail_{alert['id']}", width="stretch"):
                _show_alert_detail(alert)
