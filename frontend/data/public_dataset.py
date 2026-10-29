from __future__ import annotations

from typing import Any
from urllib.parse import quote

from utils.api_client import api_data, api_request, get_api_base_url


def get_source() -> dict[str, Any] | None:
    value = api_data("/api/public-data/source", timeout=3.0)
    return value if isinstance(value, dict) else None


def get_stats() -> dict[str, int]:
    value = api_data("/api/public-data/stats", timeout=3.0)
    return value if isinstance(value, dict) else {}


def sync_catalog(limit: int = 20) -> dict[str, Any]:
    response = api_request(
        f"/api/public-data/sync?limit={limit}",
        method="POST",
        timeout=180.0,
        return_errors=True,
    )
    return response or {"success": False, "message": "公开数据目录同步失败。"}


def get_subjects() -> list[dict[str, Any]]:
    value = api_data("/api/public-data/subjects", timeout=5.0)
    return value if isinstance(value, list) else []


def get_aligned_subject_timeline(subject_id: str) -> dict[str, Any]:
    value = api_data(
        f"/api/public-data/subjects/{quote(subject_id, safe='')}/aligned-timeline",
        timeout=10.0,
    )
    if not isinstance(value, dict):
        return {
            "subject": {},
            "sessions": [],
            "modeling_events": [],
            "signal_windows": [],
            "annotations": [],
        }
    return value


def get_sessions(subject_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    suffix = f"&subject_id={quote(subject_id)}" if subject_id else ""
    value = api_data(
        f"/api/public-data/sessions?limit={limit}{suffix}",
        timeout=8.0,
    )
    return value if isinstance(value, list) else []


def get_session(session_id: int) -> dict[str, Any] | None:
    value = api_data(f"/api/public-data/sessions/{session_id}", timeout=5.0)
    return value if isinstance(value, dict) else None


def get_timeline(session_id: int) -> dict[str, list[dict[str, Any]]]:
    value = api_data(
        f"/api/public-data/sessions/{session_id}/timeline",
        timeout=8.0,
    )
    if not isinstance(value, dict):
        return {
            "modeling_events": [],
            "signal_windows": [],
            "roi_metrics": [],
            "annotations": [],
        }
    return {
        "modeling_events": value.get("modeling_events") or [],
        "signal_windows": value.get("signal_windows") or [],
        "roi_metrics": value.get("roi_metrics") or [],
        "annotations": value.get("annotations") or [],
    }


def import_session_content(session_id: int) -> dict[str, Any]:
    response = api_request(
        f"/api/public-data/sessions/{session_id}/import",
        method="POST",
        timeout=600.0,
        return_errors=True,
    )
    return response or {
        "success": False,
        "message": "会话内容载入超时，请稍后重试。",
    }


def add_annotation(
    session_id: int,
    *,
    timestamp_seconds: float | None,
    category: str,
    note: str,
) -> dict[str, Any]:
    response = api_request(
        f"/api/public-data/sessions/{session_id}/annotations",
        method="POST",
        payload={
            "timestamp_seconds": timestamp_seconds,
            "category": category,
            "note": note,
            "created_by": "实验人员",
        },
        timeout=5.0,
        return_errors=True,
    )
    return response or {"success": False, "message": "注释保存失败。"}


def delete_annotation(session_id: int, annotation_id: int) -> dict[str, Any]:
    response = api_request(
        f"/api/public-data/sessions/{session_id}/annotations/{annotation_id}",
        method="DELETE",
        timeout=5.0,
        return_errors=True,
    )
    return response or {"success": False, "message": "注释删除失败。"}


def analyze_session(session_id: int, question: str) -> dict[str, Any]:
    response = api_request(
        f"/api/public-data/sessions/{session_id}/analysis",
        method="POST",
        payload={"question": question},
        timeout=180.0,
        return_errors=True,
    )
    return response or {"success": False, "message": "分析服务暂时不可用。"}


def follow_up_session_analysis(
    session_id: int,
    analysis_id: int,
    question: str,
) -> dict[str, Any]:
    response = api_request(
        f"/api/public-data/sessions/{session_id}/analyses/{analysis_id}/follow-up",
        method="POST",
        payload={"question": question},
        timeout=180.0,
        return_errors=True,
    )
    return response or {"success": False, "message": "追问服务暂时不可用。"}


def get_session_analyses(session_id: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    before_id: int | None = None
    while True:
        suffix = f"&before_id={before_id}" if before_id is not None else ""
        value = api_data(
            f"/api/public-data/sessions/{session_id}/analyses?limit=200{suffix}",
            timeout=5.0,
        )
        if not isinstance(value, list):
            raise RuntimeError("暂时无法完整读取决策对话，请稍后重试。")
        records.extend(value)
        if len(value) < 200:
            return records
        next_id = min(int(item["id"]) for item in value)
        if before_id is not None and next_id >= before_id:
            raise RuntimeError("决策对话读取中断，请刷新后重试。")
        before_id = next_id


def session_video_url(session_id: int) -> str:
    return f"{get_api_base_url()}/api/public-data/sessions/{session_id}/video"


def format_size(value: Any) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return "未记录"
    units = ("B", "KB", "MB", "GB", "TB")
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.1f} {units[index]}"


def format_datetime(value: Any) -> str:
    if not value:
        return "未记录"
    return str(value).replace("T", " ")[:19]

