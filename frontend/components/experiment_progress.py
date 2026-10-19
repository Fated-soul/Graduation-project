from __future__ import annotations

from html import escape

import streamlit as st

from components.metric_card import render_status_pill

EXPERIMENT_STAGES = ["准备", "适应", "应激", "行为测试", "观察", "完成"]


def render_stage_steps(current_stage: str) -> str:
    stage_short = current_stage.replace("阶段", "").replace("闃舵", "")
    current_index = EXPERIMENT_STAGES.index(stage_short) if stage_short in EXPERIMENT_STAGES else 0
    nodes: list[str] = []
    for index, stage in enumerate(EXPERIMENT_STAGES):
        css = "done" if index < current_index else "current" if index == current_index else ""
        nodes.append(f'<span class="step-node {css}">{escape(stage)}</span>')
        if index < len(EXPERIMENT_STAGES) - 1:
            nodes.append('<span class="step-arrow">→</span>')
    return f'<div class="step-line">{"".join(nodes)}</div>'


def render_experiment_progress(experiment: dict[str, object]) -> None:
    progress = int(experiment["progress"])
    stage = str(experiment["stage"])
    st.markdown(
        f"""
        <div class="soft-card">
            <div class="section-title">
                <div>
                    <h3>{escape(str(experiment["name"]))}</h3>
                    <div class="section-subtitle">
                        {escape(str(experiment["id"]))} · 动物数量 {escape(str(experiment["animal_count"]))} · 起始日期 {escape(str(experiment["start_date"]))}
                    </div>
                </div>
                {render_status_pill(str(experiment["status"]))}
            </div>
            <div>{render_stage_steps(stage)}</div>
            <div style="display:flex;justify-content:space-between;color:#64748b;font-size:.84rem;margin-top:.45rem;">
                <span>当前阶段：{escape(stage)}阶段</span>
                <strong>{progress}%</strong>
            </div>
            <div class="risk-bar">
                <div class="risk-bar-fill" style="width:{progress}%;"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
