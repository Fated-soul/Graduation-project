from __future__ import annotations

import json

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

    if selected.get("import_status") != "ready":
        st.warning("该会话尚未载入多模态证据，请先在“造模会话”中完成载入。")
        return

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
    render_section_title("决策记录", "每条建议均保留问题、依据、可信程度和形成时间")
    if not analyses:
        st.info("本次会话还没有辅助决策记录。")
        return
    for analysis in analyses:
        with st.container(border=True):
            confidence = analysis.get("confidence")
            confidence_text = f"{float(confidence):.0%}" if confidence is not None else "未评定"
            record_name = "追问答复" if analysis.get("parent_analysis_id") else "辅助决策"
            st.markdown(
                f"#### {record_name} · {format_datetime(analysis.get('created_at'))}"
                f" · 证据充分度 {confidence_text}"
            )
            st.markdown("**评估问题**")
            st.markdown(f"> {analysis.get('question') or '综合评估本次造模会话'}")
            if analysis.get("parent_question"):
                st.caption(f"承接上一条问题：{analysis['parent_question']}")
            st.markdown("**评估结论**")
            st.write(analysis.get("summary") or "")
            evidence = analysis.get("evidence") or []
            if evidence:
                st.markdown("**判断依据**")
                for item in evidence:
                    st.markdown(f"- {item}")
            if analysis.get("recommendation"):
                st.markdown(f"**建议：** {analysis['recommendation']}")
            sources = analysis.get("knowledge_sources") or []
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


def _analysis_markdown(analysis: dict) -> str:
    confidence = analysis.get("confidence")
    confidence_text = f"{float(confidence):.0%}" if confidence is not None else "未评定"
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
        f"## 评估问题\n\n{analysis.get('question') or '综合评估本次造模会话'}\n\n"
        f"## 评估结论\n\n{analysis.get('summary') or ''}\n\n"
        f"## 判断依据\n\n{evidence}\n\n"
        f"## 后续建议\n\n{analysis.get('recommendation') or '暂无'}\n"
        f"\n## 参考资料\n\n{source_text}\n"
    )


def _set_question(question: str) -> None:
    st.session_state.dataset_agent_question = question
