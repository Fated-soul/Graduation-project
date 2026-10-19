from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from fastapi import Query

from backend.api.errors import raise_database_http_exception
from backend.schemas.agent import (
    AgentAnalyzeRequest,
    AgentConversationMessageRequest,
    AgentCreateConversationRequest,
)
from backend.schemas.common import APIResponse
from backend.services import agent_analysis_result_service, agent_service

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/analysis-results/{mouse_id}/latest", response_model=APIResponse)
def get_latest_analysis_result(mouse_id: str) -> APIResponse:
    try:
        result = agent_analysis_result_service.get_latest(mouse_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if result is None:
        raise HTTPException(status_code=404, detail="agent analysis result not found")
    return APIResponse(data=result)


@router.get("/analysis-results/{mouse_id}", response_model=APIResponse)
def get_analysis_result_history(
    mouse_id: str,
    limit: int = Query(default=20, ge=1, le=200),
) -> APIResponse:
    try:
        results = agent_analysis_result_service.get_history(mouse_id, limit)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(data=results)


@router.post("/analysis-results/{analysis_id}/confirm", response_model=APIResponse)
def confirm_analysis_result(analysis_id: int) -> APIResponse:
    try:
        result = agent_analysis_result_service.confirm(analysis_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    if result is None:
        raise HTTPException(status_code=404, detail="agent analysis result not found")
    return APIResponse(message="agent recommendation confirmed", data=result)


@router.get("/health", response_model=APIResponse)
def get_agent_health() -> APIResponse:
    try:
        upstream = agent_service.get_agent_health()
    except agent_service.AgentAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return APIResponse(data=upstream.get("data"), message="agent service reachable")


@router.post("/analyze/{mouse_id}", response_model=APIResponse)
def analyze_mouse(mouse_id: str, request: AgentAnalyzeRequest) -> APIResponse:
    try:
        upstream = agent_service.analyze_mouse(mouse_id, request)
    except agent_service.AgentInputDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except agent_service.AgentAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:
        raise_database_http_exception(exc)
    data = upstream.get("data")
    try:
        stored = _persist_analysis(data, mouse_id)
    except Exception as exc:
        raise_database_http_exception(exc)
    return APIResponse(message="agent analysis completed", data=stored or data)


@router.post(
    "/conversations",
    response_model=APIResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    request: AgentCreateConversationRequest,
) -> APIResponse:
    upstream = _call_agent(agent_service.create_conversation, request)
    return APIResponse(message="conversation created", data=upstream.get("data"))


@router.get("/conversations/{session_id}", response_model=APIResponse)
def get_conversation(session_id: str) -> APIResponse:
    upstream = _call_agent(agent_service.get_conversation, session_id)
    return APIResponse(data=upstream.get("data"))


@router.delete(
    "/conversations/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_conversation(session_id: str) -> Response:
    _call_agent(agent_service.delete_conversation, session_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/conversations/{session_id}/messages",
    response_model=APIResponse,
)
def send_conversation_message(
    session_id: str,
    request: AgentConversationMessageRequest,
) -> APIResponse:
    upstream = _call_agent(
        agent_service.send_conversation_message,
        session_id,
        request,
    )
    data = upstream.get("data")
    if isinstance(data, dict) and isinstance(data.get("analysis"), dict):
        try:
            _persist_analysis(data["analysis"], request.mouse_id)
        except Exception as exc:
            raise_database_http_exception(exc)
    return APIResponse(message="message completed", data=upstream.get("data"))


def _call_agent(function, *args):
    try:
        return function(*args)
    except agent_service.AgentAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _persist_analysis(
    analysis: Any,
    fallback_mouse_id: str | None,
) -> dict[str, Any] | None:
    if not isinstance(analysis, dict):
        return None
    payload = dict(analysis)
    if not payload.get("mouse_id"):
        payload["mouse_id"] = fallback_mouse_id
    required = {"mouse_id", "risk_score", "risk_level", "summary"}
    if any(not payload.get(field) and payload.get(field) != 0 for field in required):
        return None
    return agent_analysis_result_service.create(payload)
