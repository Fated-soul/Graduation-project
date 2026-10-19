from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

from components.metric_card import render_status_pill
from data.backend_data import confirm_agent_recommendation, get_agent_analysis


def _analysis_html(mouse_id: str, analysis: dict[str, object]) -> str:
    factors = "".join(
        f'<span class="status-pill status-agent">{escape(str(factor))}</span>'
        for factor in analysis["factors"]
    )
    score = int(analysis["risk_score"])
    return f"""
    <div>
        <div class="kv-grid">
            <div class="kv-item"><div class="kv-label">分析对象</div><div class="kv-value">{escape(mouse_id)}</div></div>
            <div class="kv-item"><div class="kv-label">分析时间</div><div class="kv-value">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div></div>
            <div class="kv-item"><div class="kv-label">风险评分</div><div class="kv-value">{score} / 100</div></div>
            <div class="kv-item"><div class="kv-label">风险等级</div><div class="kv-value">{escape(str(analysis["risk_level"]))}</div></div>
        </div>
        <div class="risk-bar"><div class="risk-bar-fill" style="width:{score}%;"></div></div>
        <div class="factor-list">{factors}</div>
    </div>
    """


def _render_dialog_body(mouse_id: str, analysis: dict[str, object]) -> None:
    st.markdown(_analysis_html(mouse_id, analysis), unsafe_allow_html=True)
    modules = [
        ("生命体征分析", analysis["vital_analysis"]),
        ("行为分析", analysis["behavior_analysis"]),
        ("造模阶段分析", analysis["stage_analysis"]),
        ("多模态综合风险", analysis["risk_analysis"]),
    ]
    for title, content in modules:
        st.markdown(
            f"""
            <div class="soft-card" style="margin-top:.7rem;margin-bottom:.2rem;">
                <strong style="color:#17324d;">{escape(str(title))}</strong>
                <div style="color:#475569;margin-top:.35rem;line-height:1.7;">{escape(str(content))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown(
        f"""
        <div class="agent-card">
            <strong>Agent 建议</strong>
            <div style="margin-top:.35rem;line-height:1.75;color:#334155;">{escape(str(analysis["recommendation"]))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _show_analysis_dialog(mouse_id: str, analysis: dict[str, object]) -> None:
    if hasattr(st, "dialog"):
        @st.dialog("Agent 综合分析报告")
        def dialog() -> None:
            _render_dialog_body(mouse_id, analysis)

        dialog()
    else:
        st.info("当前窗口模式不支持弹窗，已在页面内展开完整分析。")
        _render_dialog_body(mouse_id, analysis)


def _show_control_dialog(mouse_id: str, analysis: dict[str, object]) -> None:
    def render_control_body() -> None:
        st.markdown(
            f"""
            <div class="agent-card">
                <strong>确认采用 Agent 建议作为本次造模操作依据？</strong>
                <div class="kv-grid" style="margin-top:.75rem;">
                    <div class="kv-item"><div class="kv-label">当前对象</div><div class="kv-value">{escape(mouse_id)}</div></div>
                    <div class="kv-item"><div class="kv-label">建议来源</div><div class="kv-value">Agent</div></div>
                </div>
                <div style="margin-top:.75rem;line-height:1.75;color:#334155;">
                    {escape(str(analysis["control_strategy"]))}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        col_cancel, col_confirm = st.columns(2)
        with col_cancel:
            if st.button("取消", key=f"cancel_control_{mouse_id}", width="stretch"):
                st.rerun()
        with col_confirm:
            if st.button("确认采用", key=f"confirm_control_{mouse_id}", width="stretch", type="primary"):
                analysis_id = analysis.get("id")
                if not isinstance(analysis_id, int):
                    st.error("当前分析记录缺少有效编号，暂时无法保存确认结果。")
                    return
                response = confirm_agent_recommendation(analysis_id)
                if response.get("success"):
                    st.session_state.agent_decision_feedback = {
                        "mouse_id": mouse_id,
                        "message": "Agent 建议已确认，并已记录到本次分析结果。",
                    }
                    st.rerun()
                else:
                    st.error(str(response.get("message") or "确认结果保存失败，请稍后重试。"))

    if hasattr(st, "dialog"):
        @st.dialog("确认采用 Agent 建议")
        def dialog() -> None:
            render_control_body()

        dialog()
    else:
        render_control_body()


def render_agent_card(mouse_id: str) -> None:
    analysis = get_agent_analysis(mouse_id)
    if analysis is None:
        st.info("暂无 Agent 分析数据。")
        return

    feedback = st.session_state.pop("agent_decision_feedback", None)
    if isinstance(feedback, dict) and feedback.get("mouse_id") == mouse_id:
        st.success(str(feedback.get("message")))

    score = int(analysis["risk_score"])
    is_confirmed = analysis.get("decision_status") == "confirmed"
    factors = "".join(
        f'<span class="status-pill status-agent">{escape(str(factor))}</span>'
        for factor in analysis["factors"]
    )
    st.markdown(
        f"""
        <div class="agent-card">
            <div class="agent-head">
                <div>
                    <p class="agent-title">Agent 辅助决策</p>
                    <div class="section-subtitle"><span class="dot"></span> 已融合生理、行为、环境、刺激和阶段证据</div>
                </div>
                <div style="text-align:right;">
                    {render_status_pill(str(analysis["risk_level"]))}
                    <div class="risk-score">{score}</div>
                    <div class="section-subtitle">/ 100 风险评分</div>
                </div>
            </div>
            <div class="kv-grid">
                <div class="kv-item"><div class="kv-label">当前分析对象</div><div class="kv-value">{escape(mouse_id)}</div></div>
                <div class="kv-item"><div class="kv-label">风险等级</div><div class="kv-value">{escape(str(analysis["risk_level"]))}</div></div>
            </div>
            <div class="risk-bar"><div class="risk-bar-fill" style="width:{score}%;"></div></div>
            <div style="color:#334155;line-height:1.75;">{escape(str(analysis["summary"]))}</div>
            <div class="factor-list">{factors}</div>
            <div style="margin-top:.85rem;color:#334155;line-height:1.75;"><strong>Agent 建议：</strong>{escape(str(analysis["recommendation"]))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("查看完整分析", key=f"agent_full_{mouse_id}", width="stretch"):
            _show_analysis_dialog(mouse_id, analysis)
    with col_b:
        button_label = "建议已确认" if is_confirmed else "确认采用建议"
        if st.button(
            button_label,
            key=f"agent_control_{mouse_id}",
            width="stretch",
            type="primary",
            disabled=is_confirmed,
        ):
            _show_control_dialog(mouse_id, analysis)

    if is_confirmed:
        decided_at = str(analysis.get("decided_at") or "")[:19].replace("T", " ")
        suffix = f"，确认时间：{decided_at}" if decided_at else ""
        st.caption(f"该建议已由实验人员确认采用{suffix}。")
