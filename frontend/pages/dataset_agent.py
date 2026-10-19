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
from utils.analysis_report_pdf import build_analysis_report_pdf


QUESTION_PRESETS = (
    (
        "评估造模反应",
        "本次会话的造模反应是否充分？请结合刺激、冻结行为和钙活动说明。",
    ),
    (
        "检查证据一致性",
        "不同模态之间是否相互支持？哪些结论仍需人工复核？",
    ),
    (
        "规划后续观察",
        "根据当前证据，下一阶段应重点观察哪些变化？",
    ),
)
LEGACY_QUESTION_TRANSLATIONS = {
    (
        "Assess whether this FC session supports fear-memory formation by jointly "
        "considering foot shocks, freezing behavior, and calcium activity. State "
        "the limits of the conclusion."
    ): "请结合足底电击、冻结行为和钙活动，评估本次 FC 会话是否支持恐惧记忆形成，并说明结论的局限。",
}
DEFAULT_ANALYSIS_QUESTION = "请综合评估本次造模会话的多模态证据，并说明结论的局限。"


def render() -> None:
    if st.session_state.pop("dataset_agent_clear_question", False):
        st.session_state.dataset_agent_question = ""
    clear_follow_up_key = st.session_state.pop(
        "dataset_agent_clear_follow_up_input", None
    )
    if clear_follow_up_key:
        st.session_state.pop(str(clear_follow_up_key), None)
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

    selector, state = st.columns([4.5, 1])
    with selector:
        selected_id = st.selectbox(
            "当前造模会话",
            list(labels),
            index=list(labels).index(preferred) if preferred in labels else 0,
            format_func=lambda value: labels[value],
        )
    selected = next(item for item in sessions if int(item["id"]) == int(selected_id))
    ready = selected.get("import_status") == "ready"
    with state:
        st.markdown("**会话状态**")
        if ready:
            st.success("证据已就绪")
        else:
            st.warning("等待载入")

    st.session_state.selected_dataset_session = int(selected_id)
    _clear_stale_follow_up(int(selected_id))

    if notice:
        st.success(str(notice))

    _render_session_context(selected)
    if not ready:
        st.warning("该会话尚未载入多模态证据，请先在“造模会话”中完成载入。")
        return

    analyses = get_session_analyses(int(selected_id))
    _render_composer(int(selected_id))
    _render_conversation(selected, analyses)


def _render_session_context(session: dict) -> None:
    with st.container(border=True):
        title, detail = st.columns([2.1, 3])
        with title:
            st.markdown("### Agent 造模辅助决策")
            st.caption("围绕当前会话开展可追溯的分析与追问")
        with detail:
            columns = st.columns(4)
            columns[0].metric("实验动物", session.get("subject_code") or "-")
            columns[1].metric("研究阶段", session.get("modeling_stage") or "未分类")
            columns[2].metric("实验事件", int(session.get("modeling_event_count") or 0))
            columns[3].metric("信号片段", int(session.get("signal_window_count") or 0))
        st.caption(
            "Agent 将综合行为、刺激、钙成像、神经与生理记录，并结合研究资料形成辅助意见；"
            "最终判断仍由实验人员确认。"
        )


def _render_composer(session_id: int) -> None:
    render_section_title("向 Agent 提问", "选择关注方向或输入具体研究问题")

    with st.container(border=True):
        st.markdown("**开始一轮新的辅助分析**")
        st.caption("问题越具体，Agent 越容易给出可核验的判断依据。")

        preset_columns = st.columns(len(QUESTION_PRESETS))
        for index, (column, (label, prompt)) in enumerate(
            zip(preset_columns, QUESTION_PRESETS, strict=True)
        ):
            with column:
                st.button(
                    label,
                    key=f"agent_question_{index}",
                    on_click=_set_question,
                    args=(prompt,),
                    width="stretch",
                )

        if "dataset_agent_question" not in st.session_state:
            st.session_state.dataset_agent_question = ""
        question = st.text_area(
            "本次希望重点评估什么？",
            key="dataset_agent_question",
            placeholder="例如：刺激后冻结行为与钙活动是否共同支持恐惧记忆形成？",
            height=112,
        )
        if st.button(
            "发送问题",
            type="primary",
            width="stretch",
            disabled=not question.strip(),
        ):
            _submit_question(session_id, question.strip())


def _render_conversation(session: dict, analyses: list[dict]) -> None:
    render_section_title(
        "决策对话",
        "每次初始分析及其后续追问作为一条完整对话连续保留",
    )
    if not analyses:
        with st.container(border=True):
            st.markdown("### 尚未开始本次会话的辅助分析")
            st.write("可从上方选择一个关注方向，或直接输入与本次造模相关的问题。")
        return

    for thread in _group_analysis_threads(analyses):
        root = thread[0]
        follow_up_count = max(0, len(thread) - 1)
        with st.container(border=True):
            heading, metadata = st.columns([4, 1.4])
            with heading:
                st.markdown("#### 辅助决策对话")
            with metadata:
                st.caption(
                    f"{format_datetime(root.get('created_at'))} · "
                    f"{follow_up_count} 次追问"
                )

            for index, analysis in enumerate(thread):
                if index:
                    st.divider()
                _render_analysis_exchange(
                    session,
                    analysis,
                    allow_follow_up=index == len(thread) - 1,
                )


def _group_analysis_threads(analyses: list[dict]) -> list[list[dict]]:
    ordered = sorted(
        analyses,
        key=lambda item: (
            str(item.get("created_at") or ""),
            int(item.get("id") or 0),
        ),
    )
    records_by_id = {
        int(item["id"]): item for item in ordered if item.get("id") is not None
    }
    threads: dict[int | str, list[dict]] = {}

    for index, analysis in enumerate(ordered):
        root = analysis
        visited: set[int] = set()
        parent_id = root.get("parent_analysis_id")
        while parent_id is not None and int(parent_id) in records_by_id:
            numeric_parent_id = int(parent_id)
            if numeric_parent_id in visited:
                break
            visited.add(numeric_parent_id)
            root = records_by_id[numeric_parent_id]
            parent_id = root.get("parent_analysis_id")

        root_id = root.get("id")
        thread_key: int | str = (
            int(root_id) if root_id is not None else f"record-{index}"
        )
        threads.setdefault(thread_key, []).append(analysis)

    return list(threads.values())


def _render_analysis_exchange(
    session: dict,
    analysis: dict,
    *,
    allow_follow_up: bool,
) -> None:
    is_follow_up = bool(analysis.get("parent_analysis_id"))
    with st.chat_message("user", avatar=":material/science:"):
        st.caption("实验人员追问" if is_follow_up else "实验人员提问")
        st.markdown(_display_question(analysis.get("question")))
        if analysis.get("parent_question"):
            st.caption(
                f"承接问题：{_truncate(_display_question(analysis['parent_question']), 80)}"
            )

    with st.chat_message("assistant", avatar=":material/neurology:"):
        confidence = analysis.get("confidence")
        confidence_text = (
            f"{_normalise_confidence(confidence):.0%}"
            if confidence is not None
            else "未评定"
        )
        response_name = "追问答复" if is_follow_up else "Agent 辅助结论"
        st.markdown(f"**{response_name}**")
        st.caption(
            f"形成于 {format_datetime(analysis.get('created_at'))} · "
            f"证据充分度 {confidence_text}"
        )
        if confidence is not None:
            st.progress(_normalise_confidence(confidence))

        st.write(analysis.get("summary") or "本次分析未返回可显示的结论。")
        if analysis.get("recommendation"):
            st.markdown("**后续建议**")
            st.info(str(analysis["recommendation"]))

        evidence = analysis.get("evidence") or []
        sources = analysis.get("knowledge_sources") or []
        with st.expander(
            f"查看判断依据与参考资料（{len(evidence)} 项依据，{len(sources)} 项资料）"
        ):
            _render_evidence_and_sources(evidence, sources)

        analysis_id = analysis.get("id")
        if allow_follow_up and analysis_id is not None:
            follow_up, report, record = st.columns([1.35, 1, 1])
            with follow_up:
                st.button(
                    "围绕此结论追问",
                    key=f"start_follow_up_{analysis_id}",
                    on_click=_start_follow_up,
                    args=(
                        int(analysis_id),
                        int(session["id"]),
                    ),
                    width="stretch",
                )
        else:
            report, record = st.columns(2)

        with report:
            st.download_button(
                "下载 PDF 报告",
                data=_analysis_pdf(session, analysis),
                file_name=(
                    f"{session.get('subject_code', 'animal')}_辅助决策_{analysis_id}.pdf"
                ),
                mime="application/pdf",
                key=f"analysis_pdf_{analysis_id}",
                width="stretch",
            )
        with record:
            st.download_button(
                "下载完整记录",
                data=json.dumps(analysis, ensure_ascii=False, indent=2, default=str),
                file_name=f"{session.get('subject_code', 'animal')}_造模评估.json",
                mime="application/json",
                key=f"analysis_json_{analysis_id}",
                width="stretch",
            )

        target = st.session_state.get("dataset_agent_follow_up_target")
        if (
            allow_follow_up
            and analysis_id is not None
            and target
            and int(target.get("analysis_id") or -1) == int(analysis_id)
        ):
            _render_inline_follow_up(int(session["id"]), int(analysis_id))


def _render_inline_follow_up(session_id: int, analysis_id: int) -> None:
    input_key = f"dataset_follow_up_input_{analysis_id}"
    with st.container(border=True):
        st.markdown("**继续追问这条结论**")
        st.caption("Agent 会结合原问题、原结论和当前会话证据继续回答。")
        follow_up = st.text_area(
            "追问内容",
            key=input_key,
            placeholder="例如：哪些证据仍需人工复核，结论的适用范围是什么？",
            height=96,
        )
        cancel, submit = st.columns([1, 2])
        with cancel:
            st.button(
                "取消",
                key=f"cancel_follow_up_{analysis_id}",
                on_click=_cancel_follow_up,
                args=(input_key,),
                width="stretch",
            )
        with submit:
            if st.button(
                "发送追问",
                key=f"submit_follow_up_{analysis_id}",
                type="primary",
                width="stretch",
                disabled=not follow_up.strip(),
            ):
                _submit_follow_up(
                    session_id,
                    analysis_id,
                    follow_up.strip(),
                    input_key,
                )


def _render_evidence_and_sources(evidence: list, sources: list) -> None:
    if evidence:
        st.markdown("**判断依据**")
        for item in evidence:
            st.markdown(f"- {item}")
    else:
        st.caption("本条结论未附带独立判断依据。")

    if sources:
        st.markdown("**参考资料**")
        for source in sources:
            title = str(source.get("title") or "研究资料")
            section = str(source.get("section") or "").strip()
            label = f"{title} · {section}" if section else title
            url = str(source.get("source_url") or "").strip()
            if url.startswith(("https://", "http://")):
                st.link_button(label, url, width="content")
            else:
                st.markdown(f"- {label}")
    else:
        st.caption("本条结论未引用外部研究资料。")


def _submit_question(session_id: int, question: str) -> None:
    with st.spinner("正在汇总当前会话的多模态证据与研究资料……"):
        response = analyze_session(session_id, question)

    if response.get("success") is False:
        st.error(str(response.get("message") or "分析失败。"))
        return

    st.session_state.dataset_agent_notice = "辅助决策已形成并保存。"
    st.session_state.dataset_agent_clear_question = True
    st.rerun()


def _submit_follow_up(
    session_id: int,
    analysis_id: int,
    question: str,
    input_key: str,
) -> None:
    with st.spinner("正在结合原结论与当前证据形成答复……"):
        response = follow_up_session_analysis(session_id, analysis_id, question)

    if response.get("success") is False:
        st.error(str(response.get("message") or "追问失败。"))
        return

    st.session_state.dataset_agent_notice = "追问答复已形成并保存。"
    st.session_state.dataset_agent_clear_follow_up_input = input_key
    st.session_state.pop("dataset_agent_follow_up_target", None)
    st.rerun()


@st.cache_data(show_spinner=False)
def _analysis_pdf(session: dict, analysis: dict) -> bytes:
    return build_analysis_report_pdf(session, analysis)


def _set_question(question: str) -> None:
    st.session_state.dataset_agent_question = question


def _start_follow_up(analysis_id: int, session_id: int) -> None:
    st.session_state.dataset_agent_follow_up_target = {
        "analysis_id": analysis_id,
        "session_id": session_id,
    }


def _cancel_follow_up(input_key: str) -> None:
    st.session_state.pop("dataset_agent_follow_up_target", None)
    st.session_state.pop(input_key, None)


def _clear_stale_follow_up(session_id: int) -> None:
    target = st.session_state.get("dataset_agent_follow_up_target")
    if target and int(target.get("session_id") or -1) != session_id:
        st.session_state.pop("dataset_agent_follow_up_target", None)


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


def _normalise_confidence(value: object) -> float:
    confidence = float(value or 0)
    if confidence > 1:
        confidence /= 100
    return min(1.0, max(0.0, confidence))


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else f"{value[: limit - 1]}…"
