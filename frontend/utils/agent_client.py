from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from utils.api_client import api_request


AGENT_MESSAGE_TIMEOUT_SECONDS = float(
    os.getenv("MINGCHA_AGENT_MESSAGE_TIMEOUT_SECONDS", "390")
)


def get_agent_health() -> dict[str, Any] | None:
    return api_request("/api/agent/health", timeout=3.0, return_errors=True)


def create_agent_conversation(
    *,
    mouse_id: str,
    llm_provider: str,
    model: str | None,
    use_semantic_reasoning: bool,
) -> dict[str, Any] | None:
    payload: dict[str, Any] = {
        "mouse_id": mouse_id,
        "llm_provider": llm_provider,
        "use_llm": True,
        "use_semantic_reasoning": use_semantic_reasoning,
    }
    if model:
        payload["model"] = model
    return api_request(
        "/api/agent/conversations",
        method="POST",
        payload=payload,
        timeout=30.0,
        return_errors=True,
    )


def get_agent_conversation(session_id: str) -> dict[str, Any] | None:
    safe_session_id = quote(session_id, safe="")
    return api_request(
        f"/api/agent/conversations/{safe_session_id}",
        timeout=15.0,
        return_errors=True,
    )


def delete_agent_conversation(session_id: str) -> dict[str, Any] | None:
    safe_session_id = quote(session_id, safe="")
    return api_request(
        f"/api/agent/conversations/{safe_session_id}",
        method="DELETE",
        timeout=15.0,
        return_errors=True,
    )


def send_agent_message(
    session_id: str,
    message: str,
    *,
    mouse_id: str | None = None,
) -> dict[str, Any] | None:
    safe_session_id = quote(session_id, safe="")
    payload: dict[str, Any] = {"message": message}
    if mouse_id:
        payload["mouse_id"] = mouse_id
    return api_request(
        f"/api/agent/conversations/{safe_session_id}/messages",
        method="POST",
        payload=payload,
        timeout=AGENT_MESSAGE_TIMEOUT_SECONDS,
        return_errors=True,
    )


def response_error(response: dict[str, Any] | None) -> str | None:
    if response is None:
        return "分析等待时间较长，请稍后重试。"
    if response.get("success") is not False:
        return None

    status_code = response.get("status_code")
    messages = {
        404: "当前会话已失效，请新建会话后重试。",
        422: "当前实验对象或提问内容不完整，请检查后重试。",
        502: "辅助决策暂时不可用，请稍后重试。",
        503: "智能分析暂时不可用，请稍后重试。",
    }
    return messages.get(
        status_code,
        "分析未完成，请稍后重试。",
    )
