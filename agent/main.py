from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Response, status

from agent import config
from agent.analysis_service import build_rule_analysis
from agent.conversation_service import (
    ConversationNotFoundError,
    create_conversation,
    delete_conversation,
    get_conversation,
    send_message,
)
from agent.data_client import BackendAPIError, backend_health, load_dataset_session_context, load_mouse_context
from agent.llm_client import LLMConfigurationError, LLMRequestError, analyze_dataset_session, enhance_analysis
from agent.rag_service import get_rag_status, retrieve_knowledge
from agent.schemas import (
    APIResponse,
    AnalyzeRequest,
    ConversationMessageRequest,
    CreateConversationRequest,
    DatasetSessionAnalysisRequest,
    KnowledgeSearchRequest,
)


app = FastAPI(
    title=config.APP_NAME,
    description="实验动物公开多模态会话证据聚合与百炼大模型解释服务",
    version=config.APP_VERSION,
)


@app.get("/api/health", response_model=APIResponse)
def health() -> APIResponse:
    issues = config.validate_settings()
    backend = backend_health()
    return APIResponse(
        message="agent service running",
        data={
            "status": "ok" if not issues else "degraded",
            "backend_connected": backend is not None,
            "backend_api_url": config.BACKEND_API_URL,
            "llm_provider": "bailian",
            "model": config.DASHSCOPE_MODEL,
            "api_key_configured": bool(config.DASHSCOPE_API_KEY),
            "rule_fallback_enabled": config.AGENT_ALLOW_RULE_FALLBACK,
            "rag": get_rag_status(),
            "configuration_issues": issues,
        },
    )


@app.post("/api/analyze/{mouse_id}", response_model=APIResponse)
def analyze(mouse_id: str, request: AnalyzeRequest) -> APIResponse:
    try:
        context = load_mouse_context(mouse_id, request)
        analysis = build_rule_analysis(context)
        if request.use_llm:
            try:
                _, analysis = enhance_analysis(
                    context=context,
                    rule_analysis=analysis,
                    question="请对当前实验鼠进行完整状态分析并给出建议。",
                    model=request.model or config.DASHSCOPE_MODEL,
                )
            except (LLMConfigurationError, LLMRequestError):
                if not config.AGENT_ALLOW_RULE_FALLBACK:
                    raise
    except BackendAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except (LLMConfigurationError, LLMRequestError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return APIResponse(
        message="analysis completed",
        data=analysis.model_dump(mode="json"),
    )


@app.post("/api/dataset-sessions/{session_id}/analyze", response_model=APIResponse)
def analyze_public_dataset_session(
    session_id: int,
    request: DatasetSessionAnalysisRequest,
) -> APIResponse:
    try:
        context = load_dataset_session_context(session_id)
        result = analyze_dataset_session(
            context=context,
            question=request.question,
            model=request.model or config.DASHSCOPE_MODEL,
        )
    except BackendAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except (LLMConfigurationError, LLMRequestError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return APIResponse(message="dataset session analyzed", data=result)


@app.post("/api/knowledge/search", response_model=APIResponse)
def search_knowledge(request: KnowledgeSearchRequest) -> APIResponse:
    result = retrieve_knowledge(request.query, top_k=request.top_k)
    return APIResponse(message="knowledge retrieved", data=result)


@app.post(
    "/api/conversations",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation_route(request: CreateConversationRequest) -> APIResponse:
    return APIResponse(
        message="conversation created",
        data=create_conversation(request),
    )


@app.get("/api/conversations/{session_id}", response_model=APIResponse)
def get_conversation_route(session_id: str) -> APIResponse:
    try:
        conversation = get_conversation(session_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="conversation not found") from exc
    return APIResponse(data=conversation)


@app.delete("/api/conversations/{session_id}")
def delete_conversation_route(session_id: str) -> APIResponse:
    try:
        delete_conversation(session_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="conversation not found") from exc
    return APIResponse(message="conversation deleted")


@app.post(
    "/api/conversations/{session_id}/messages",
    response_model=APIResponse,
)
def send_message_route(
    session_id: str,
    request: ConversationMessageRequest,
) -> APIResponse:
    try:
        result = send_message(session_id, request)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="conversation not found") from exc
    except BackendAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (LLMConfigurationError, LLMRequestError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return APIResponse(message="message completed", data=result)

