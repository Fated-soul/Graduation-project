from __future__ import annotations

from typing import Any

from psycopg2.extras import Json

from backend.database.connection import get_dict_cursor

AGENT_ANALYSIS_FIELDS = """
    id, mouse_id, risk_score, risk_level, summary, vital_analysis,
    behavior_analysis, stage_analysis, risk_analysis, recommendation,
    control_strategy, factors, analysis_source, model_provider,
    model_name, decision_status, decided_at, analyzed_at, created_at
"""


def _to_dict(row: Any | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def get_latest_analysis(mouse_id: str) -> dict[str, Any] | None:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {AGENT_ANALYSIS_FIELDS}
            FROM agent_analysis_results
            WHERE mouse_id = %s
            ORDER BY analyzed_at DESC, id DESC
            LIMIT 1
            """,
            (mouse_id,),
        )
        return _to_dict(cursor.fetchone())


def get_analysis_history(mouse_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            f"""
            SELECT {AGENT_ANALYSIS_FIELDS}
            FROM agent_analysis_results
            WHERE mouse_id = %s
            ORDER BY analyzed_at DESC, id DESC
            LIMIT %s
            """,
            (mouse_id, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def create_analysis_result(data: dict[str, Any]) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            INSERT INTO agent_analysis_results (
                mouse_id, risk_score, risk_level, summary, vital_analysis,
                behavior_analysis, stage_analysis, risk_analysis, recommendation,
                control_strategy, factors, analysis_source, model_provider,
                model_name, analyzed_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, COALESCE(%s::timestamptz, CURRENT_TIMESTAMP)
            )
            RETURNING {AGENT_ANALYSIS_FIELDS}
            """,
            (
                data["mouse_id"],
                data["risk_score"],
                data["risk_level"],
                data["summary"],
                data.get("vital_analysis"),
                data.get("behavior_analysis"),
                data.get("stage_analysis"),
                data.get("risk_analysis"),
                data.get("recommendation"),
                data.get("control_strategy"),
                Json(data.get("factors") or []),
                data.get("analysis_source") or "bailian_llm+rules",
                data.get("model_provider") or "bailian",
                data.get("model_name"),
                data.get("analyzed_at"),
            ),
        )
        return dict(cursor.fetchone())


def confirm_analysis_result(analysis_id: int) -> dict[str, Any] | None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            f"""
            UPDATE agent_analysis_results
            SET decision_status = 'confirmed',
                decided_at = COALESCE(decided_at, CURRENT_TIMESTAMP)
            WHERE id = %s
            RETURNING {AGENT_ANALYSIS_FIELDS}
            """,
            (analysis_id,),
        )
        return _to_dict(cursor.fetchone())
