from __future__ import annotations

import pandas as pd
import streamlit as st

from components.animal_table import render_full_animal_table
from components.experiment_progress import render_experiment_progress
from components.metric_card import render_kv_grid, render_section_title
from data.backend_data import get_animals, get_experiments, get_research_activity


def render() -> None:
    animals = get_animals()
    experiments = get_experiments(animals)
    render_section_title("智能造模方案与队列", "围绕行为无助造模组织实验阶段、多模态观测与辅助决策")
    render_kv_grid(
        [
            ("造模目标", "行为无助表型形成与过程评估"),
            ("刺激范式", "光刺激、声音刺激与电击刺激"),
            ("观测模态", "生理、视觉行为、环境与刺激过程"),
            ("决策方式", "Agent 提出建议，实验人员确认执行"),
        ]
    )

    if not experiments:
        st.info("暂无行为无助造模队列。请先添加实验动物并设置造模阶段。")
        return

    columns = st.columns(max(1, min(3, len(experiments))))
    for col, experiment in zip(columns, experiments, strict=False):
        with col:
            render_experiment_progress(experiment)

    experiment_ids = [str(experiment["id"]) for experiment in experiments]
    current_experiment = st.session_state.selected_experiment
    index = experiment_ids.index(current_experiment) if current_experiment in experiment_ids else 0
    selected_experiment_id = st.selectbox(
        "选择实验查看详情",
        experiment_ids,
        index=index,
        key="selected_experiment",
    )
    experiment = next(item for item in experiments if item["id"] == selected_experiment_id)

    render_section_title("造模方案详情", "实验队列、当前阶段、完成度与研究摘要")
    render_kv_grid(
        [
            ("实验名称", experiment["name"]),
            ("队列编号", experiment["id"]),
            ("动物数量", experiment["animal_count"]),
            ("队列起始日期", experiment["start_date"]),
            ("当前阶段", f"{experiment['stage']}阶段"),
            ("实验进度", f"{experiment['progress']}%"),
            ("状态", experiment["status"]),
        ]
    )

    animal_df = pd.DataFrame([animal for animal in animals if animal["id"] in experiment["animals"]])
    render_section_title("实验动物队列", "纳入当前造模方案的研究对象")
    render_full_animal_table(animal_df)

    left, right = st.columns([1, 1])
    with left:
        render_section_title("最近实验记录", "汇总状态变化、刺激执行和辅助评估")
        activity = get_research_activity(
            [animal for animal in animals if animal["id"] in experiment["animals"]],
            limit=20,
        )
        if activity:
            st.dataframe(activity, width="stretch", hide_index=True)
        else:
            st.info("当前队列尚未产生实验记录。")
    with right:
        st.markdown(
            f"""
            <div class="agent-card">
                <strong>多模态研究摘要</strong>
                <div style="margin-top:.55rem;line-height:1.75;color:#334155;">{experiment["summary"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
