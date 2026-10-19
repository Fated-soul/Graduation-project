from __future__ import annotations

from collections.abc import Iterator
from html import escape
import time
from typing import Any

import streamlit as st

from data.backend_data import get_animals
from utils.agent_client import (
    create_agent_conversation,
    delete_agent_conversation,
    get_agent_conversation,
    get_agent_health,
    response_error,
    send_agent_message,
)


WELCOME_MESSAGE = {
    "role": "assistant",
    "content": (
        "你好，我是实验动物造模辅助决策助手。我会综合生命体征、视觉行为、实验环境、"
        "刺激过程和当前造模阶段，帮助你解释风险、比较变化并提出可供人工确认的建议。"
    ),
    "attachments": [],
    "is_welcome": True,
}

SUGGESTED_PROMPTS = (
    "综合分析当前多模态状态",
    "哪些实验数据支持这个判断？",
    "当前刺激参数是否需要调整？",
    "生成本阶段辅助决策报告",
)


@st.cache_data(ttl=12, show_spinner=False)
def _cached_agent_health() -> dict[str, Any] | None:
    return get_agent_health()


def _agent_is_online(response: dict[str, Any] | None) -> bool:
    return bool(response and response.get("success") is not False)


def _clear_session_query() -> None:
    if "agent_session" in st.query_params:
        del st.query_params["agent_session"]


def _reset_local_conversation(*, keep_welcome: bool = True) -> None:
    st.session_state.agent_session_id = None
    st.session_state.agent_session_mouse = None
    st.session_state.agent_messages = [dict(WELCOME_MESSAGE)] if keep_welcome else []
    st.session_state.agent_pending_prompt = None
    st.session_state.agent_confirmed_recommendations = set()
    _clear_session_query()


def _normalise_history_message(raw: dict[str, Any]) -> dict[str, Any] | None:
    role = str(raw.get("role") or raw.get("sender") or "").lower()
    if role in {"agent", "ai", "model"}:
        role = "assistant"
    if role not in {"user", "assistant"}:
        return None

    content = raw.get("content")
    if content is None:
        content = raw.get("message") if role == "user" else raw.get("answer")
    if not isinstance(content, str) or not content.strip():
        return None

    return {
        "role": role,
        "content": content,
        "attachments": raw.get("attachments") or [],
    }


def _restore_conversation_once() -> None:
    if st.session_state.agent_history_restored:
        return
    st.session_state.agent_history_restored = True

    session_id = st.session_state.agent_session_id or st.query_params.get("agent_session")
    if not session_id:
        if not st.session_state.agent_messages:
            st.session_state.agent_messages = [dict(WELCOME_MESSAGE)]
        return

    response = get_agent_conversation(str(session_id))
    if response_error(response):
        _reset_local_conversation()
        return

    data = response.get("data", {}) if response else {}
    messages = [
        message
        for raw in data.get("messages", [])
        if isinstance(raw, dict)
        if (message := _normalise_history_message(raw)) is not None
    ]
    st.session_state.agent_session_id = str(session_id)
    st.session_state.agent_session_mouse = data.get("mouse_id")
    st.session_state.agent_messages = messages or [dict(WELCOME_MESSAGE)]
    if data.get("mouse_id"):
        st.session_state.agent_selected_mouse = str(data["mouse_id"])
        st.session_state.agent_context_mouse = str(data["mouse_id"])


def _create_conversation(mouse_id: str) -> tuple[str | None, str | None]:
    response = create_agent_conversation(
        mouse_id=mouse_id,
        llm_provider=st.session_state.agent_llm_provider,
        model=st.session_state.agent_model.strip() or None,
        use_semantic_reasoning=st.session_state.agent_semantic_reasoning,
    )
    error = response_error(response)
    if error:
        return None, error

    data = response.get("data", {}) if response else {}
    session_id = data.get("session_id")
    if not session_id:
        return None, "对话创建失败，请稍后重试。"

    st.session_state.agent_session_id = str(session_id)
    st.session_state.agent_session_mouse = mouse_id
    st.query_params["agent_session"] = str(session_id)
    return str(session_id), None


def _typewriter(text: str) -> Iterator[str]:
    for character in text:
        yield character
        time.sleep(0.006)


def _render_thinking() -> None:
    st.markdown(
        """
        <div class="agent-thinking" role="status" aria-label="Agent 正在思考">
            <span class="thinking-orb"><i></i><i></i><i></i></span>
            <span><strong>正在思考</strong><small>正在读取实验数据并组织回答</small></span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _recommendation_lines(recommendation: dict[str, Any]) -> tuple[list[str], list[str]]:
    actions = recommendation.get("action") or []
    reasons = recommendation.get("reason") or []
    if isinstance(actions, str):
        actions = [actions]
    if isinstance(reasons, str):
        reasons = [reasons]
    return [str(item) for item in actions], [str(item) for item in reasons]


def _parameter_value(name: str, value: Any) -> str:
    if value is None:
        return "暂无数据"
    if name in {"duration_ms", "interval_ms"}:
        seconds = float(value) / 1000
        text = f"{seconds:g} 秒"
        if name == "interval_ms" and seconds > 0:
            text += f"（约 {60 / seconds:.1f} 次/分钟）"
        return text
    if name == "intensity":
        return f"{float(value):g}%"
    return str(value)


def _render_parameter_comparison(parameters: dict[str, Any]) -> None:
    current = parameters.get("latest_stimulation_event")
    proposed = parameters.get("proposed")
    if not isinstance(current, dict) or not isinstance(proposed, dict) or not proposed:
        return
    labels = {
        "duration_ms": "单次持续时间",
        "interval_ms": "刺激间隔",
        "intensity": "刺激强度",
    }
    rows = []
    for name, label in labels.items():
        before = current.get(name)
        after = proposed.get(name)
        if before is None and after is None:
            continue
        rows.append(
            {
                "参数": label,
                "当前值": _parameter_value(name, before),
                "建议值": _parameter_value(name, after),
            }
        )
    if rows:
        st.markdown("**最近一次刺激 → 候选方案**")
        st.dataframe(rows, hide_index=True, use_container_width=True)
    confidence = parameters.get("confidence")
    if confidence is not None:
        st.caption(
            f"建议置信度：{float(confidence):.0%} · 候选值已通过设备约束校验，"
            "仍需实验人员结合实验方案确认"
        )


def _render_recommendation(recommendation: Any, message_index: int) -> None:
    if not isinstance(recommendation, dict) or not recommendation:
        return

    actions, reasons = _recommendation_lines(recommendation)
    parameters = recommendation.get("parameters")
    parameters = parameters if isinstance(parameters, dict) else {}
    guidance = parameters.get("guidance")
    confirmed = message_index in st.session_state.agent_confirmed_recommendations

    with st.container(border=True):
        st.markdown(
            '<div class="recommendation-title"><span>✦</span><div>'
            "<strong>参数调整建议</strong><small>仅供实验人员决策，不会自动控制设备</small>"
            "</div></div>",
            unsafe_allow_html=True,
        )
        if actions:
            st.markdown("**建议动作**  \n" + "  \n".join(f"· {escape(item)}" for item in actions))
        _render_parameter_comparison(parameters)
        if guidance:
            st.markdown(f"**调整说明**  \n{escape(str(guidance))}")
        if reasons:
            st.markdown("**判断依据**  \n" + "  \n".join(f"· {escape(item)}" for item in reasons))

        if confirmed:
            st.success("已记录：实验人员确认收到该建议。")
        elif st.button(
            "确认收到建议",
            key=f"confirm_recommendation_{message_index}",
            type="primary",
        ):
            st.session_state.agent_confirmed_recommendations.add(message_index)
            st.rerun()


def _render_attachments(attachments: Any, message_index: int) -> None:
    if not isinstance(attachments, list):
        return
    for attachment_index, attachment in enumerate(attachments):
        if not isinstance(attachment, dict):
            continue
        if attachment.get("type") == "parameter_recommendation":
            _render_recommendation(
                attachment.get("data"),
                message_index * 1000 + attachment_index,
            )


def _render_message(message: dict[str, Any], index: int) -> None:
    role = message.get("role", "assistant")
    avatar = "🧑‍🔬" if role == "user" else "✨"
    with st.chat_message(role, avatar=avatar):
        content = str(message.get("content") or "")
        st.markdown(content)
        if role == "assistant":
            _render_attachments(message.get("attachments"), index)
        if message.get("is_error"):
            if st.button("重新发送", key=f"retry_agent_message_{index}"):
                st.session_state.agent_messages.pop(index)
                st.session_state.agent_pending_prompt = {
                    "text": message.get("retry_prompt"),
                    "append_user": False,
                }
                st.rerun()


def _append_error(error: str, prompt: str) -> None:
    st.session_state.agent_messages.append(
        {
            "role": "assistant",
            "content": f"⚠️ {error}",
            "is_error": True,
            "retry_prompt": prompt,
            "attachments": [],
        }
    )


def _process_prompt(prompt: str, mouse_id: str, *, append_user: bool = True) -> None:
    prompt = prompt.strip()
    if not prompt:
        return

    if append_user:
        user_message = {"role": "user", "content": prompt}
        st.session_state.agent_messages.append(user_message)
        with st.chat_message("user", avatar="🧑‍🔬"):
            st.markdown(prompt)

    with st.chat_message("assistant", avatar="✨"):
        thinking = st.empty()
        with thinking.container():
            _render_thinking()

        session_id = st.session_state.agent_session_id
        if not session_id:
            session_id, error = _create_conversation(mouse_id)
            if error:
                thinking.empty()
                st.error(error)
                _append_error(error, prompt)
                st.rerun()

        response = send_agent_message(str(session_id), prompt, mouse_id=mouse_id)
        error = response_error(response)
        thinking.empty()
        if error:
            st.error(error)
            _append_error(error, prompt)
            st.rerun()

        data = response.get("data", {}) if response else {}
        answer = str(data.get("answer") or "Agent 已完成分析，但没有返回可显示的回答。")
        streamed_answer = st.write_stream(_typewriter(answer))
        assistant_message = {
            "role": "assistant",
            "content": streamed_answer or answer,
            "attachments": data.get("attachments") or [],
            "experiment_stage": data.get("experiment_stage"),
        }
        st.session_state.agent_messages.append(assistant_message)
        # 流式消息是在历史循环之后动态创建的。立即快速重绘一次，使它进入
        # 稳定的历史渲染路径，避免下一轮长请求期间出现灰色的旧 DOM 副本。
        st.rerun()


def _render_status_header(
    online: bool,
    mouse_id: str,
    experiment_stage: str | None,
) -> None:
    status_class = "online" if online else "offline"
    status_text = "Agent 已连接" if online else "Agent 不可用"
    stage = experiment_stage or "等待分析"
    st.markdown(
        f"""
        <div class="agent-chat-header">
            <div class="agent-brand-mark">✦</div>
            <div class="agent-chat-title">
                <strong>Agent 辅助决策助手</strong>
                <span>融合生理、行为、环境、刺激与造模阶段证据进行综合研判</span>
            </div>
            <div class="agent-header-meta">
                <span class="agent-live {status_class}"><i></i>{status_text}</span>
                <span>{escape(mouse_id)}</span>
                <span>{escape(stage)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _handle_mouse_change(selected_mouse: str) -> None:
    if selected_mouse == st.session_state.agent_context_mouse:
        return
    st.session_state.agent_context_mouse = selected_mouse
    _reset_local_conversation()


def _new_conversation(mouse_id: str) -> None:
    _reset_local_conversation()
    _, error = _create_conversation(mouse_id)
    if error:
        st.session_state.agent_messages.append(
            {
                "role": "assistant",
                "content": f"⚠️ {error}",
                "attachments": [],
            }
        )


def render() -> None:
    _restore_conversation_once()

    animals = get_animals()
    mouse_ids = [str(animal["id"]) for animal in animals]
    if not mouse_ids:
        mouse_ids = [st.session_state.agent_selected_mouse or "MOUSE-001"]
    if st.session_state.agent_selected_mouse not in mouse_ids:
        st.session_state.agent_selected_mouse = mouse_ids[0]

    health = _cached_agent_health()
    online = _agent_is_online(health)

    side, chat = st.columns([0.24, 0.76], gap="large")
    with side:
        st.markdown(
            """
            <div class="agent-side-intro">
                <span>多模态决策上下文</span>
                <strong>选择研究对象</strong>
                <p>Agent 将自动汇聚该实验鼠的多模态记录，并保留人工确认环节。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        selected_mouse = st.selectbox(
            "当前实验鼠",
            mouse_ids,
            key="agent_selected_mouse",
        )
        _handle_mouse_change(selected_mouse)

        button_left, button_right = st.columns(2)
        with button_left:
            if st.button("＋ 新会话", width="stretch", type="primary"):
                _new_conversation(selected_mouse)
                st.rerun()
        with button_right:
            delete_disabled = not bool(st.session_state.agent_session_id)
            if st.button("清空", width="stretch", disabled=delete_disabled):
                session_id = st.session_state.agent_session_id
                if session_id:
                    delete_agent_conversation(str(session_id))
                _reset_local_conversation()
                st.rerun()

        with st.expander("辅助决策设置"):
            st.toggle("结合历史趋势与造模阶段", key="agent_semantic_reasoning")
            st.caption("分析范围：风险解释、阶段评估、刺激参数建议。所有建议均需实验人员确认。")

        st.markdown('<div class="suggestion-label">快捷提问</div>', unsafe_allow_html=True)
        for index, suggestion in enumerate(SUGGESTED_PROMPTS):
            if st.button(suggestion, key=f"agent_suggestion_{index}", width="stretch"):
                st.session_state.agent_messages.append(
                    {"role": "user", "content": suggestion}
                )
                st.session_state.agent_pending_prompt = {
                    "text": suggestion,
                    "append_user": False,
                }
                st.rerun()

        session_id = st.session_state.agent_session_id
        st.caption("当前对话：已建立" if session_id else "当前对话：首次提问时建立")

    with chat:
        latest_stage = next(
            (
                message.get("experiment_stage")
                for message in reversed(st.session_state.agent_messages)
                if message.get("experiment_stage")
            ),
            None,
        )
        _render_status_header(online, selected_mouse, latest_stage)

        pending_prompt = st.session_state.agent_pending_prompt
        st.session_state.agent_pending_prompt = None
        with st.container(
            height=420,
            border=True,
            key="agent_conversation_scroll",
        ):
            st.markdown(
                f"""
                <div class="agent-conversation-toolbar">
                    <span><i></i>对话记录</span>
                    <small>{len(st.session_state.agent_messages)} 条消息</small>
                </div>
                """,
                unsafe_allow_html=True,
            )
            for index, message in enumerate(st.session_state.agent_messages):
                _render_message(message, index)

            if pending_prompt and online:
                if isinstance(pending_prompt, dict):
                    pending_text = str(pending_prompt.get("text") or "")
                    append_user = bool(pending_prompt.get("append_user", False))
                else:
                    pending_text = str(pending_prompt)
                    append_user = True
                _process_prompt(
                    pending_text,
                    selected_mouse,
                    append_user=append_user,
                )

        prompt = st.chat_input(
            f"询问 {selected_mouse} 的多模态状态或造模建议…",
            disabled=not online,
            key="agent_chat_input",
        )
        if prompt:
            st.session_state.agent_messages.append(
                {"role": "user", "content": prompt}
            )
            st.session_state.agent_pending_prompt = {
                "text": prompt,
                "append_user": False,
            }
            st.rerun()

        if not online:
            error = response_error(health)
            st.caption(f"当前无法发送消息。{error or '辅助决策暂时不可用。'}")
