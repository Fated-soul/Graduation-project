from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import RLock
from typing import Any
from uuid import uuid4

from agent import config
from agent.analysis_service import (
    build_parameter_recommendation,
    build_rule_analysis,
)
from agent.data_client import load_mouse_context
from agent.llm_client import LLMConfigurationError, LLMRequestError, enhance_analysis
from agent.schemas import AnalyzeRequest, ConversationMessageRequest, CreateConversationRequest


class ConversationNotFoundError(KeyError):
    pass


_CONVERSATIONS: dict[str, dict[str, Any]] = {}
_LOCK = RLock()


def create_conversation(request: CreateConversationRequest) -> dict[str, Any]:
    session_id = uuid4().hex
    now = datetime.now().isoformat()
    conversation = {
        "session_id": session_id,
        "mouse_id": request.mouse_id,
        "vision": request.vision,
        "model": request.model or config.DASHSCOPE_MODEL,
        "llm_provider": "bailian",
        "use_llm": request.use_llm,
        "use_semantic_reasoning": request.use_semantic_reasoning,
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }
    with _LOCK:
        _CONVERSATIONS[session_id] = conversation
    return deepcopy(conversation)


def get_conversation(session_id: str) -> dict[str, Any]:
    with _LOCK:
        conversation = _CONVERSATIONS.get(session_id)
        if conversation is None:
            raise ConversationNotFoundError(session_id)
        return deepcopy(conversation)


def delete_conversation(session_id: str) -> None:
    with _LOCK:
        if session_id not in _CONVERSATIONS:
            raise ConversationNotFoundError(session_id)
        del _CONVERSATIONS[session_id]


def send_message(
    session_id: str,
    request: ConversationMessageRequest,
) -> dict[str, Any]:
    with _LOCK:
        conversation = _CONVERSATIONS.get(session_id)
        if conversation is None:
            raise ConversationNotFoundError(session_id)
        snapshot = deepcopy(conversation)

    mouse_id = request.mouse_id or snapshot.get("mouse_id")
    if not mouse_id:
        raise ValueError("conversation has no mouse_id")

    analyze_request = AnalyzeRequest(
        vision=request.vision or snapshot.get("vision"),
        vital_signs=request.vital_signs,
        use_llm=bool(snapshot.get("use_llm", True)),
        use_semantic_reasoning=bool(snapshot.get("use_semantic_reasoning", True)),
        llm_provider="bailian",
        model=snapshot.get("model") or config.DASHSCOPE_MODEL,
    )
    context = load_mouse_context(mouse_id, analyze_request)
    rule_analysis = build_rule_analysis(context)
    answer = _rule_answer(request.message, rule_analysis)
    analysis = rule_analysis

    if analyze_request.use_llm:
        try:
            answer, analysis = enhance_analysis(
                context=context,
                rule_analysis=rule_analysis,
                question=request.message,
                history=snapshot.get("messages") or [],
                model=analyze_request.model,
            )
        except (LLMConfigurationError, LLMRequestError):
            if not config.AGENT_ALLOW_RULE_FALLBACK:
                raise

    attachments: list[dict[str, Any]] = []
    if _wants_parameter_advice(request.message) or analysis.risk_level != "正常":
        attachments.append(
            {
                "type": "parameter_recommendation",
                "data": build_parameter_recommendation(context, analysis),
            }
        )
    if analysis.knowledge_sources:
        attachments.append(
            {
                "type": "knowledge_sources",
                "data": analysis.knowledge_sources,
            }
        )

    user_message = {"role": "user", "content": request.message, "attachments": []}
    assistant_message = {
        "role": "assistant",
        "content": answer,
        "attachments": attachments,
        "experiment_stage": analysis.experiment_stage,
    }
    with _LOCK:
        conversation = _CONVERSATIONS.get(session_id)
        if conversation is None:
            raise ConversationNotFoundError(session_id)
        conversation["mouse_id"] = mouse_id
        conversation["messages"].extend([user_message, assistant_message])
        conversation["updated_at"] = datetime.now().isoformat()

    return {
        "session_id": session_id,
        "mouse_id": mouse_id,
        "answer": answer,
        "attachments": attachments,
        "experiment_stage": analysis.experiment_stage,
        "analysis": analysis.model_dump(mode="json"),
    }


def _wants_parameter_advice(message: str) -> bool:
    keywords = ("刺激", "参数", "间隔", "持续", "电击", "爆闪", "噪声", "频繁")
    return any(keyword in message for keyword in keywords)


def _rule_answer(message: str, analysis) -> str:
    if "为什么" in message or "依据" in message:
        return (
            f"{analysis.risk_analysis}\n\n"
            f"从身体指标看，{analysis.vital_analysis}\n\n"
            f"从活动情况看，{analysis.behavior_analysis}"
        )
    if "报告" in message:
        return (
            f"## 目前情况\n{analysis.summary}\n\n"
            f"## 身体指标\n{analysis.vital_analysis}\n\n"
            f"## 活动情况\n{analysis.behavior_analysis}\n\n"
            f"## 实验进度\n{analysis.stage_analysis}\n\n"
            f"## 下一步建议\n{analysis.recommendation}"
        )
    return f"{analysis.summary}\n\n{analysis.recommendation}"

