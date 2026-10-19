from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
MOCK_FALLBACK_ENV = "MINGCHA_ENABLE_MOCK_FALLBACK"


def get_api_base_url() -> str:
    return os.getenv("MINGCHA_API_BASE_URL", DEFAULT_API_BASE_URL).rstrip("/")


def mock_fallback_enabled() -> bool:
    value = os.getenv(MOCK_FALLBACK_ENV, "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def api_request(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: float = 1.5,
    return_errors: bool = False,
) -> dict[str, Any] | None:
    url = f"{get_api_base_url()}{path}"
    data = None
    headers: dict[str, str] = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        if not return_errors:
            return None
        try:
            body = exc.read().decode("utf-8")
            error_body = json.loads(body) if body else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            error_body = {"detail": str(exc)}
        detail = error_body.get("detail", error_body)
        message = detail.get("message") if isinstance(detail, dict) else str(detail)
        return {
            "success": False,
            "status_code": exc.code,
            "message": message or str(exc),
            "detail": detail,
        }
    except (URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def api_data(path: str, *, timeout: float = 1.5) -> Any | None:
    response = api_request(path, timeout=timeout)
    if response is None:
        return None
    if "data" in response:
        return response["data"]
    return response


def backend_health() -> dict[str, Any] | None:
    return api_request("/api/health", timeout=1.0)
