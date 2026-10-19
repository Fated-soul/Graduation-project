from __future__ import annotations

import json

import plotly.graph_objects as go
import streamlit as st

from components.metric_card import render_section_title
from data.public_dataset import (
    analyze_session,
    follow_up_session_analysis,
    format_datetime,
    get_session_analyses,
    get_sessions,
)


QUESTIONS = (
    "本次会话的造模反应是否充分？请结合刺激、冻结行为和钙活动说明。",
    "不同模态之间是否相互支持？哪些结论仍需人工复核？",
    "根据当前证据，下一阶段应重点观察哪些变化？",
)
LEGACY_QUESTION_TRANSLATIONS = {
    (
        "Assess whether this FC session supports fear-memory formation by jointly "
        "considering foot shocks, freezing behavior, and calcium activity. State "
        "the limits of the conclusion."
    ): "请结合足底电击、冻结行为和钙活动，评估本次 FC 会话是否支持恐惧记忆形成，并说明结论的局限。",
}
DEFAULT_ANALYSIS_QUESTION = "请综合评估本次造模会话的多模态证据，并说明结论的局限。"
PLOT_CONFIG = {
    "displayModeBar": False,
    "scrollZoom": False,
    "responsive": True,
    "doubleClick": False,
}
EVIDENCE_MODALITIES = (
    ("行为影像", "has_video"),
    ("行为标注", "has_behavior"),
    ("刺激事件", "has_shock"),
    ("钙成像", "has_calcium"),
    ("脑电", "has_eeg"),
    ("肌电", "has_emg"),
    ("睡眠分期", "has_sleep_states"),
)


def render() -> None:
    clear_key = st.session_state.pop("dataset_agent_clear_follow_up", None)
    if clear_key:
        st.session_state.pop(str(clear_key), None)
    notice = st.session_state.pop("dataset_agent_notice", None)

    sessions = get_sessions(limit=300)
    if not sessions:
        st.info("尚未同步造模会话，暂时无法开展辅助决策。")
        return

    labels = {
        int(item["id"]): (
            f"{item.get('subject_code')} · {item.get('modeling_stage') or '未分类'} · "
            f"{format_datetime(item.get('session_started_at'))[:10]}"
        )
        for item in sessions
    }
    default_id = next(
        (int(item["id"]) for item in sessions if item.get("import_status") == "ready"),
        list(labels)[0],
    )
    preferred = int(st.session_state.get("selected_dataset_session") or default_id)
    selected_id = st.selectbox(
        "分析会话",
        list(labels),
        index=list(labels).index(preferred) if preferred in labels else 0,
        format_func=lambda value: labels[value],
    )
    st.session_state.selected_dataset_session = int(selected_id)
    selected = next(item for item in sessions if int(item["id"]) == int(selected_id))

    if notice:
        st.success(str(notice))

    with st.container(border=True):
        st.markdown("### Agent 造模辅助决策")
        st.write(
            "Agent 综合当前阶段的刺激记录、冻结行为、钙成像、运动、生理信号、睡眠状态和人工复核记录，"
            "并检索数据集官方说明与相关原始论文，给出可追溯的造模评估。"
            "结论用于辅助实验人员判断，不替代人工复核。"
        )
        cols = st.columns(4)
        cols[0].metric("实验动物", selected.get("subject_code") or "-")
        cols[1].metric("研究阶段", selected.get("modeling_stage") or "未分类")
        cols[2].metric("事件记录", int(selected.get("modeling_event_count") or 0))
        cols[3].metric("信号时间窗", int(selected.get("signal_window_count") or 0))

    _render_session_evidence_dashboard(selected)

    if selected.get("import_status") != "ready":
        st.warning("该会话尚未载入多模态证据，请先在“造模会话”中完成载入。")
        return

    render_section_title("提出评估问题", "选择常用问题，或结合当前研究目标填写具体问题")
    if "dataset_agent_question" not in st.session_state:
        st.session_state.dataset_agent_question = QUESTIONS[0]
    for index, (column, prompt) in enumerate(zip(st.columns(3), QUESTIONS, strict=True)):
        with column:
            st.button(
                prompt,
                key=f"agent_question_{index}",
                on_click=_set_question,
                args=(prompt,),
                width="stretch",
            )
    question = st.text_area("本次希望重点评估什么？", key="dataset_agent_question", height=88)
    if st.button("形成辅助决策", type="primary", width="stretch"):
        if not question.strip():
            st.warning("请先填写希望评估的问题。")
        else:
            with st.spinner("正在汇总当前造模阶段的多模态证据……"):
                response = analyze_session(int(selected_id), question.strip())
            if response.get("success") is False:
                st.error(str(response.get("message") or "分析失败。"))
            else:
                st.session_state.dataset_agent_notice = "辅助决策已形成并保存。"
                st.rerun()

    analyses = get_session_analyses(int(selected_id))
    if analyses:
        _render_decision_dashboard(analyses)
    render_section_title("决策记录", "每条建议均保留问题、依据、可信程度和形成时间")
    if not analyses:
        st.info("本次会话还没有辅助决策记录。")
        return
    for analysis in analyses:
        with st.container(border=True):
            confidence = analysis.get("confidence")
            confidence_text = (
                f"{_normalise_confidence(confidence):.0%}"
                if confidence is not None
                else "未评定"
            )
            record_name = "追问答复" if analysis.get("parent_analysis_id") else "辅助决策"
            evidence = analysis.get("evidence") or []
            sources = analysis.get("knowledge_sources") or []
            heading, evidence_metric, source_metric = st.columns([4.8, 1, 1])
            with heading:
                st.markdown(
                    f"#### {record_name} · {format_datetime(analysis.get('created_at'))}"
                )
            evidence_metric.metric("判断依据", len(evidence))
            source_metric.metric("参考资料", len(sources))
            if confidence is not None:
                st.progress(
                    _normalise_confidence(confidence),
                    text=f"证据充分度 {confidence_text}",
                )
            else:
                st.caption("证据充分度尚未评定")
            st.markdown("**评估问题**")
            st.markdown(f"> {_display_question(analysis.get('question'))}")
            if analysis.get("parent_question"):
                st.caption(
                    f"承接上一条问题：{_display_question(analysis['parent_question'])}"
                )
            st.markdown("**评估结论**")
            st.write(analysis.get("summary") or "")
            if evidence:
                st.markdown("**判断依据**")
                for item in evidence:
                    st.markdown(f"- {item}")
            if analysis.get("recommendation"):
                st.markdown(f"**建议：** {analysis['recommendation']}")
            if sources:
                st.markdown("**参考资料**")
                for source in sources:
                    title = str(source.get("title") or "研究资料")
                    section = str(source.get("section") or "").strip()
                    label = f"{title} · {section}" if section else title
                    url = str(source.get("source_url") or "").strip()
                    if url.startswith(("https://", "http://")):
                        st.markdown(f"- [{label}]({url})")
                    else:
                        st.markdown(f"- {label}")
            analysis_id = analysis.get("id")
            if analysis_id is not None:
                follow_up_key = f"dataset_follow_up_{analysis_id}"
                with st.expander("继续追问"):
                    follow_up = st.text_area(
                        "针对这条决策继续提问",
                        key=follow_up_key,
                        placeholder="例如：哪些证据仍需要人工复核？",
                        height=88,
                    )
                    if st.button(
                        "提交追问",
                        key=f"submit_follow_up_{analysis_id}",
                        type="primary",
                        width="stretch",
                    ):
                        if not follow_up.strip():
                            st.warning("请先填写追问内容。")
                        else:
                            with st.spinner("正在结合原决策与当前证据形成答复……"):
                                response = follow_up_session_analysis(
                                    int(selected_id),
                                    int(analysis_id),
                                    follow_up.strip(),
                                )
                            if response.get("success") is False:
                                st.error(str(response.get("message") or "追问失败。"))
                            else:
                                st.session_state.dataset_agent_notice = "追问答复已形成并保存。"
                                st.session_state.dataset_agent_clear_follow_up = follow_up_key
                                st.rerun()
            left, right = st.columns(2)
            with left:
                st.download_button(
                    "下载评估报告",
                    data=_analysis_markdown(analysis),
                    file_name=f"{selected.get('subject_code', 'animal')}_造模评估.md",
                    mime="text/markdown",
                    key=f"analysis_md_{analysis.get('id')}",
                    width="stretch",
                )
            with right:
                st.download_button(
                    "下载完整记录",
                    data=json.dumps(analysis, ensure_ascii=False, indent=2, default=str),
                    file_name=f"{selected.get('subject_code', 'animal')}_造模评估.json",
                    mime="application/json",
                    key=f"analysis_json_{analysis.get('id')}",
                    width="stretch",
                )


def _render_session_evidence_dashboard(session: dict) -> None:
    render_section_title(
        "会话证据画像",
        "查看本次研究会话已具备的证据类型与可用于判断的记录规模",
    )
    coverage, scale = st.columns([1.25, 1])
    with coverage:
        st.markdown("**多模态证据覆盖**")
        st.plotly_chart(
            _build_coverage_figure(session),
            width="stretch",
            config=PLOT_CONFIG,
            key=f"agent_coverage_{session.get('id')}",
        )
        available = sum(bool(session.get(key)) for _, key in EVIDENCE_MODALITIES)
        st.caption(f"本次会话已覆盖 {available}/{len(EVIDENCE_MODALITIES)} 类研究证据。")
    with scale:
        st.markdown("**证据记录规模**")
        st.plotly_chart(
            _build_record_scale_figure(session),
            width="stretch",
            config=PLOT_CONFIG,
            key=f"agent_scale_{session.get('id')}",
        )


def _render_decision_dashboard(analyses: list[dict]) -> None:
    ordered = list(reversed(analyses))
    latest = analyses[0]
    latest_confidence = latest.get("confidence")
    latest_confidence_text = (
        f"{_normalise_confidence(latest_confidence):.0%}"
        if latest_confidence is not None
        else "未评定"
    )
    source_keys = {
        (
            str(source.get("title") or ""),
            str(source.get("section") or ""),
            str(source.get("source_url") or ""),
        )
        for analysis in analyses
        for source in analysis.get("knowledge_sources") or []
    }

    render_section_title(
        "决策概览",
        "按形成时间比较证据充分度、判断依据和参考资料使用情况",
    )
    metrics = st.columns(4)
    metrics[0].metric("决策记录", len(analyses))
    metrics[1].metric("最新充分度", latest_confidence_text)
    metrics[2].metric("引用资料", len(source_keys))
    metrics[3].metric(
        "追问答复",
        sum(bool(item.get("parent_analysis_id")) for item in analyses),
    )

    confidence_chart, basis_chart = st.columns([1.2, 1])
    with confidence_chart:
        st.markdown("**历次判断充分度**")
        st.plotly_chart(
            _build_confidence_figure(ordered),
            width="stretch",
            config=PLOT_CONFIG,
            key="agent_confidence_history",
        )
    with basis_chart:
        st.markdown("**判断依据与资料引用**")
        st.plotly_chart(
            _build_basis_figure(ordered),
            width="stretch",
            config=PLOT_CONFIG,
            key="agent_basis_history",
        )


def _build_coverage_figure(session: dict) -> go.Figure:
    labels = [label for label, _ in EVIDENCE_MODALITIES]
    values = [1 if session.get(key) else 0 for _, key in EVIDENCE_MODALITIES]
    statuses = ["已载入" if value else "未记录" for value in values]
    figure = go.Figure(
        go.Heatmap(
            z=[values],
            x=labels,
            y=["证据状态"],
            text=[statuses],
            texttemplate="%{text}",
            hovertemplate="%{x}<br>%{text}<extra></extra>",
            colorscale=[
                [0, "#e6edf2"],
                [0.499, "#e6edf2"],
                [0.5, "#17a79b"],
                [1, "#17a79b"],
            ],
            showscale=False,
            xgap=7,
            ygap=4,
        )
    )
    figure.update_layout(
        height=180,
        margin=dict(l=10, r=10, t=18, b=42),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        dragmode=False,
        font=dict(color="#17324d"),
    )
    figure.update_xaxes(fixedrange=True, tickfont=dict(size=12))
    figure.update_yaxes(fixedrange=True, visible=False)
    return figure


def _build_record_scale_figure(session: dict) -> go.Figure:
    labels = ["实验事件", "信号时间窗", "钙成像区域", "资源文件", "人工复核"]
    values = [
        int(session.get("modeling_event_count") or 0),
        int(session.get("signal_window_count") or 0),
        int(session.get("calcium_roi_count") or 0),
        int(session.get("asset_count") or 0),
        int(session.get("annotation_count") or 0),
    ]
    maximum = max(values, default=0)
    figure = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=["#1489bd", "#17a79b", "#536fca", "#de8b20", "#78909c"],
            text=[f"{value:,}" for value in values],
            textposition="outside",
            cliponaxis=False,
            hovertemplate="%{y}<br>%{x:,} 条<extra></extra>",
        )
    )
    figure.update_layout(
        height=250,
        margin=dict(l=8, r=36, t=8, b=36),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        dragmode=False,
        bargap=0.38,
        showlegend=False,
        font=dict(color="#17324d"),
    )
    figure.update_xaxes(
        title="记录数量",
        range=[0, max(1, maximum * 1.2)],
        fixedrange=True,
        showgrid=True,
        gridcolor="#dce6ed",
        zeroline=False,
    )
    figure.update_yaxes(fixedrange=True, autorange="reversed")
    return figure


def _build_confidence_figure(analyses: list[dict]) -> go.Figure:
    labels = [f"第{index}次" for index in range(1, len(analyses) + 1)]
    values = [
        _normalise_confidence(item.get("confidence"))
        if item.get("confidence") is not None
        else None
        for item in analyses
    ]
    details = [
        [
            format_datetime(item.get("created_at")),
            _truncate(_display_question(item.get("question")), 40),
        ]
        for item in analyses
    ]
    figure = go.Figure(
        go.Scatter(
            x=labels,
            y=values,
            mode="lines+markers",
            line=dict(color="#1489bd", width=3),
            marker=dict(color="#17a79b", size=9, line=dict(color="white", width=2)),
            customdata=details,
            hovertemplate=(
                "%{x} · %{customdata[0]}<br>证据充分度 %{y:.0%}"
                "<br>%{customdata[1]}<extra></extra>"
            ),
            connectgaps=False,
        )
    )
    figure.update_layout(
        height=300,
        margin=dict(l=8, r=20, t=12, b=36),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        dragmode=False,
        showlegend=False,
        font=dict(color="#17324d"),
    )
    figure.update_xaxes(fixedrange=True, showgrid=False)
    figure.update_yaxes(
        title="证据充分度",
        range=[0, 1],
        tickformat=".0%",
        dtick=0.2,
        fixedrange=True,
        gridcolor="#dce6ed",
        zeroline=False,
    )
    return figure


def _build_basis_figure(analyses: list[dict]) -> go.Figure:
    labels = [f"第{index}次" for index in range(1, len(analyses) + 1)]
    evidence_counts = [len(item.get("evidence") or []) for item in analyses]
    source_counts = [len(item.get("knowledge_sources") or []) for item in analyses]
    figure = go.Figure()
    figure.add_bar(
        name="判断依据",
        x=labels,
        y=evidence_counts,
        marker_color="#17a79b",
        hovertemplate="%{x}<br>判断依据 %{y} 项<extra></extra>",
    )
    figure.add_bar(
        name="参考资料",
        x=labels,
        y=source_counts,
        marker_color="#de8b20",
        hovertemplate="%{x}<br>参考资料 %{y} 项<extra></extra>",
    )
    figure.update_layout(
        height=300,
        margin=dict(l=8, r=12, t=12, b=36),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        dragmode=False,
        barmode="group",
        bargap=0.28,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        font=dict(color="#17324d"),
    )
    maximum = max(evidence_counts + source_counts, default=0)
    figure.update_xaxes(fixedrange=True, showgrid=False)
    figure.update_yaxes(
        title="数量",
        range=[0, max(1, maximum * 1.25)],
        dtick=1,
        fixedrange=True,
        gridcolor="#dce6ed",
        zeroline=False,
    )
    return figure


def _normalise_confidence(value: object) -> float:
    confidence = float(value or 0)
    if confidence > 1:
        confidence /= 100
    return min(1.0, max(0.0, confidence))


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else f"{value[: limit - 1]}…"


def _analysis_markdown(analysis: dict) -> str:
    confidence = analysis.get("confidence")
    confidence_text = (
        f"{_normalise_confidence(confidence):.0%}"
        if confidence is not None
        else "未评定"
    )
    evidence = "\n".join(f"- {item}" for item in analysis.get("evidence") or []) or "- 暂无"
    sources = analysis.get("knowledge_sources") or []
    source_lines = []
    for source in sources:
        title = str(source.get("title") or "研究资料")
        section = str(source.get("section") or "").strip()
        label = f"{title} · {section}" if section else title
        url = str(source.get("source_url") or "").strip()
        source_lines.append(f"- [{label}]({url})" if url else f"- {label}")
    source_text = "\n".join(source_lines) or "- 本次未使用外部研究资料"
    return (
        "# 实验动物多模态智能造模评估报告\n\n"
        f"形成时间：{format_datetime(analysis.get('created_at'))}\n\n"
        f"证据充分度：{confidence_text}\n\n"
        f"## 评估问题\n\n{_display_question(analysis.get('question'))}\n\n"
        f"## 评估结论\n\n{analysis.get('summary') or ''}\n\n"
        f"## 判断依据\n\n{evidence}\n\n"
        f"## 后续建议\n\n{analysis.get('recommendation') or '暂无'}\n"
        f"\n## 参考资料\n\n{source_text}\n"
    )


def _set_question(question: str) -> None:
    st.session_state.dataset_agent_question = question


def _display_question(value: object) -> str:
    question = str(value or "").strip()
    if not question:
        return DEFAULT_ANALYSIS_QUESTION
    translated = LEGACY_QUESTION_TRANSLATIONS.get(question)
    if translated:
        return translated
    question_mark_count = question.count("?") + question.count("？")
    if question_mark_count >= max(3, len(question) // 2):
        return DEFAULT_ANALYSIS_QUESTION
    return question
