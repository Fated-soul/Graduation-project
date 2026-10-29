"""HTTP proxy service for the standalone Mouse Agent API."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from backend.config import AGENT_API_TIMEOUT_SECONDS, AGENT_API_URL
from backend.schemas.agent import (
    AgentAnalyzeRequest,
    AgentConversationMessageRequest,
    AgentCreateConversationRequest,
)
from backend.services import vital_signs_service


class AgentAPIError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class AgentAPIUnavailable(AgentAPIError):
    def __init__(self, detail: str) -> None:
        super().__init__(502, detail)


class AgentInputDataError(RuntimeError):
    pass


def get_agent_health() -> dict[str, Any]:
    return _request("GET", "/api/health")


def analyze_mouse(mouse_id: str, request: AgentAnalyzeRequest) -> dict[str, Any]:
    payload = request.model_dump(exclude={"vital_signs"})
    payload["vital_signs"] = _resolve_vital_signs(mouse_id, request)
    return _request(
        "POST",
        f"/api/analyze/{quote(mouse_id, safe='')}",
        payload,
    )


def create_conversation(
    request: AgentCreateConversationRequest,
) -> dict[str, Any]:
    return _request("POST", "/api/conversations", request.model_dump(exclude_none=True))


def get_conversation(session_id: str) -> dict[str, Any]:
    return _request(
        "GET",
        f"/api/conversations/{quote(session_id, safe='')}",
    )


def delete_conversation(session_id: str) -> dict[str, Any]:
    return _request(
        "DELETE",
        f"/api/conversations/{quote(session_id, safe='')}",
    )


def send_conversation_message(
    session_id: str,
    request: AgentConversationMessageRequest,
) -> dict[str, Any]:
    return _request(
        "POST",
        f"/api/conversations/{quote(session_id, safe='')}/messages",
        request.model_dump(exclude_none=True),
    )


def analyze_dataset_session(
    session_id: int,
    *,
    question: str,
    model: str | None = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"question": question}
    if history:
        payload["history"] = history
    if model:
        payload["model"] = model
    return _request(
        "POST",
        f"/api/dataset-sessions/{session_id}/analyze",
        payload,
    )


def _resolve_vital_signs(
    mouse_id: str, request: AgentAnalyzeRequest
) -> dict[str, float | None]:
    if request.vital_signs is not None:
        return {
            "temperature": request.vital_signs.body_temperature,
            "heart_rate": request.vital_signs.heart_rate,
            "blood_oxygen": request.vital_signs.blood_oxygen,
        }

    latest = vital_signs_service.get_latest(mouse_id)
    if latest is None:
        raise AgentInputDataError(
            f"no vital signs found for {mouse_id}; upload vital signs or provide an override"
        )
    body_temperature = latest.get("body_temperature")
    if body_temperature is None:
        raise AgentInputDataError(
            f"latest vital signs for {mouse_id} have no body_temperature"
        )
    return {
        "temperature": float(body_temperature),
        "heart_rate": (
            float(latest["heart_rate"])
            if latest.get("heart_rate") is not None
            else None
        ),
        "blood_oxygen": (
            float(latest["blood_oxygen"])
            if latest.get("blood_oxygen") is not None
            else None
        ),
    }


def _request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    body = (
        json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if payload is not None
        else None
    )
    request = Request(
        f"{AGENT_API_URL}{path}",
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urlopen(request, timeout=AGENT_API_TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raw_detail = exc.read().decode("utf-8", errors="replace")
        detail = _upstream_error_detail(raw_detail) or (
            f"Agent API returned HTTP {exc.code}"
        )
        raise AgentAPIError(exc.code, detail) from exc
    except (URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise AgentAPIUnavailable(
            f"cannot connect to Agent API at {AGENT_API_URL}: {reason}"
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AgentAPIUnavailable("Agent API returned invalid JSON") from exc

    if not isinstance(result, dict):
        raise AgentAPIUnavailable("Agent API returned a non-object response")
    if result.get("success") is not True:
        raise AgentAPIError(
            502, str(result.get("message") or "Agent API request failed")
        )
    return result


def _upstream_error_detail(raw: str) -> str:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if isinstance(payload, dict):
        detail = payload.get("detail") or payload.get("message")
        return str(detail) if detail is not None else raw
    return raw
