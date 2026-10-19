from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from agent.config import (
    AGENT_MAX_VISION_FEATURES,
    BACKEND_API_TIMEOUT_SECONDS,
    BACKEND_API_URL,
)
from agent.schemas import AnalyzeRequest, VitalSignsOverride


class BackendAPIError(RuntimeError):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


_MISSING = object()


def backend_health() -> dict[str, Any] | None:
    return _get_data("/api/health", default=None)


def load_mouse_context(
    mouse_id: str,
    request: AnalyzeRequest,
) -> dict[str, Any]:
    safe_mouse_id = quote(mouse_id, safe="")
    animal = _get_data(f"/api/animals/{safe_mouse_id}")
    devices = _get_data("/api/devices", default=[])
    bound_devices = [
        device
        for device in devices
        if isinstance(device, dict) and device.get("mouse_id") == mouse_id
    ]

    vital_latest = _get_data(
        f"/api/vital-signs/latest/{safe_mouse_id}", default=None
    )
    if request.vital_signs is not None:
        vital_latest = _vital_override(request.vital_signs, vital_latest)

    vital_query = urlencode(
        {"hours": request.history_hours, "limit": request.history_limit}
    )
    telemetry_query = urlencode(
        {"hours": request.history_hours, "limit": request.history_limit}
    )
    stimulation_query = urlencode(
        {
            "hours": request.stimulation_hours,
            "limit": request.stimulation_limit,
        }
    )
    vision_query = urlencode({"limit": AGENT_MAX_VISION_FEATURES})

    primary_device = bound_devices[0] if bound_devices else None
    settings: list[dict[str, Any]] = []
    if primary_device and primary_device.get("device_id"):
        safe_device_id = quote(str(primary_device["device_id"]), safe="")
        settings = _get_data(
            f"/api/stimulation/settings/{safe_device_id}", default=[]
        )

    return {
        "mouse_id": mouse_id,
        "animal": animal,
        "devices": bound_devices,
        "vital_latest": vital_latest,
        "vital_history": _get_data(
            f"/api/vital-signs/history/{safe_mouse_id}?{vital_query}", default=[]
        ),
        "telemetry_history": _get_data(
            f"/api/telemetry/history/{safe_mouse_id}?{telemetry_query}", default=[]
        ),
        "stimulation_history": _get_data(
            f"/api/stimulation/{safe_mouse_id}?{stimulation_query}", default=[]
        ),
        "stimulation_settings": settings,
        "vision_summary": request.vision
        or _get_data(f"/api/vision/summary/{safe_mouse_id}", default={}),
        "vision_features": _get_data(
            f"/api/vision/features/{safe_mouse_id}?{vision_query}", default=[]
        ),
    }


def load_dataset_session_context(session_id: int) -> dict[str, Any]:
    session = _get_data(f"/api/public-data/sessions/{session_id}")
    timeline = _get_data(
        f"/api/public-data/sessions/{session_id}/timeline",
        default={
            "modeling_events": [], "signal_windows": [],
            "roi_metrics": [], "annotations": [],
        },
    )
    subject_id = str((session or {}).get("subject_code") or "")
    aligned = (
        _get_data(
            f"/api/public-data/subjects/{quote(subject_id, safe='')}/aligned-timeline",
            default={},
        )
        if subject_id
        else {}
    )
    return {
        "session": session,
        "modeling_events": timeline.get("modeling_events") or [],
        "signal_windows": timeline.get("signal_windows") or [],
        "roi_metrics": timeline.get("roi_metrics") or [],
        "annotations": timeline.get("annotations") or [],
        "related_sessions": aligned.get("sessions") or [],
        "cross_session_events": aligned.get("modeling_events") or [],
        "cross_session_signal_summary": _summarize_aligned_signals(
            aligned.get("signal_windows") or []
        ),
        "absolute_alignment": {
            "range_started_at": aligned.get("range_started_at"),
            "range_ended_at": aligned.get("range_ended_at"),
            "alignment_basis": aligned.get("alignment_basis"),
        },
    }


def _summarize_aligned_signals(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for item in rows:
        try:
            key = (int(item.get("session_id")), str(item.get("modality") or ""))
        except (TypeError, ValueError):
            continue
        if key[1]:
            groups.setdefault(key, []).append(item)

    summaries: list[dict[str, Any]] = []
    for (_session_id, modality), items in groups.items():
        values = [
            float(item["mean_value"])
            for item in items
            if item.get("mean_value") is not None
        ]
        if not values:
            continue
        first = min(items, key=lambda item: str(item.get("aligned_started_at") or ""))
        last = max(items, key=lambda item: str(item.get("aligned_ended_at") or ""))
        summaries.append(
            {
                "session_id": first.get("session_id"),
                "session_code": first.get("session_code"),
                "session_type": first.get("session_type"),
                "modality": modality,
                "window_count": len(items),
                "started_at": first.get("aligned_started_at"),
                "ended_at": last.get("aligned_ended_at"),
                "mean": sum(values) / len(values),
                "minimum": min(values),
                "maximum": max(values),
                "unit": first.get("unit"),
            }
        )
    return sorted(
        summaries,
        key=lambda item: (str(item.get("started_at") or ""), str(item.get("modality") or "")),
    )


def _vital_override(
    override: VitalSignsOverride,
    latest: dict[str, Any] | None,
) -> dict[str, Any]:
    result = dict(latest or {})
    temperature = override.body_temperature
    if temperature is None:
        temperature = override.temperature
    result.update(
        {
            "body_temperature": temperature,
            "heart_rate": override.heart_rate,
            "blood_oxygen": override.blood_oxygen,
        }
    )
    return result


def _get_data(path: str, *, default: Any = _MISSING) -> Any:
    request = Request(
        f"{BACKEND_API_URL}{path}",
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=BACKEND_API_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        if default is not _MISSING and exc.code == 404:
            return default
        detail = exc.read().decode("utf-8", errors="replace")
        raise BackendAPIError(exc.code, detail or str(exc)) from exc
    except (URLError, TimeoutError, OSError) as exc:
        if default is not _MISSING:
            return default
        raise BackendAPIError(502, f"cannot connect to Backend: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackendAPIError(502, "Backend returned invalid JSON") from exc

    if not isinstance(payload, dict):
        raise BackendAPIError(502, "Backend returned a non-object response")
    if payload.get("success") is False:
        if default is not _MISSING:
            return default
        raise BackendAPIError(502, str(payload.get("message") or "Backend request failed"))
    return payload.get("data", payload)

