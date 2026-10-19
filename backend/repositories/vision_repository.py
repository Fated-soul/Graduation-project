from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from psycopg2.extras import execute_values

from backend.database.connection import get_dict_cursor

KEYPOINT_FIELDS = """
    id, mouse_id, source_animal_id, frame_index, keypoint_name,
    x, y, confidence, source_file, recorded_at, created_at
"""

FEATURE_FIELDS = """
    id, mouse_id, source_animal_id, frame_index, center_x, center_y,
    movement_distance, mean_confidence, keypoint_count,
    source_file, recorded_at, created_at
"""


def ensure_animals(mouse_ids: Sequence[str]) -> None:
    unique_mouse_ids = sorted({mouse_id for mouse_id in mouse_ids if mouse_id})
    if not unique_mouse_ids:
        return

    rows = [(mouse_id,) for mouse_id in unique_mouse_ids]
    with get_dict_cursor(commit=True) as cursor:
        execute_values(
            cursor,
            """
            INSERT INTO animals (
                mouse_id, current_status, experiment_name, experiment_stage
            )
            VALUES %s
            ON CONFLICT (mouse_id) DO NOTHING
            """,
            rows,
            template="(%s, 'normal', '行为无助造模', '准备阶段')",
        )


def bulk_upsert_keypoints(rows: Sequence[tuple[Any, ...]]) -> int:
    if not rows:
        return 0

    with get_dict_cursor(commit=True) as cursor:
        execute_values(
            cursor,
            """
            INSERT INTO vision_keypoints (
                mouse_id, source_animal_id, frame_index, keypoint_name,
                x, y, confidence, source_file, recorded_at
            )
            VALUES %s
            ON CONFLICT (
                source_file, frame_index, source_animal_id, keypoint_name
            )
            DO UPDATE SET
                mouse_id = EXCLUDED.mouse_id,
                x = EXCLUDED.x,
                y = EXCLUDED.y,
                confidence = EXCLUDED.confidence,
                recorded_at = EXCLUDED.recorded_at
            """,
            rows,
            page_size=1000,
        )
    return len(rows)


def bulk_upsert_frame_features(rows: Sequence[tuple[Any, ...]]) -> int:
    if not rows:
        return 0

    with get_dict_cursor(commit=True) as cursor:
        execute_values(
            cursor,
            """
            INSERT INTO behavior_frame_features (
                mouse_id, source_animal_id, frame_index, center_x, center_y,
                movement_distance, mean_confidence, keypoint_count,
                source_file, recorded_at
            )
            VALUES %s
            ON CONFLICT (
                source_file, frame_index, source_animal_id
            )
            DO UPDATE SET
                mouse_id = EXCLUDED.mouse_id,
                center_x = EXCLUDED.center_x,
                center_y = EXCLUDED.center_y,
                movement_distance = EXCLUDED.movement_distance,
                mean_confidence = EXCLUDED.mean_confidence,
                keypoint_count = EXCLUDED.keypoint_count,
                recorded_at = EXCLUDED.recorded_at
            """,
            rows,
            page_size=1000,
        )
    return len(rows)


def get_keypoints(
    mouse_id: str,
    limit: int = 1000,
    frame_start: int | None = None,
    frame_end: int | None = None,
    keypoint_name: str | None = None,
) -> list[dict[str, Any]]:
    sql = f"SELECT {KEYPOINT_FIELDS} FROM vision_keypoints WHERE mouse_id = %s"
    params: list[Any] = [mouse_id]

    if frame_start is not None:
        sql += " AND frame_index >= %s"
        params.append(frame_start)
    if frame_end is not None:
        sql += " AND frame_index <= %s"
        params.append(frame_end)
    if keypoint_name is not None:
        sql += " AND keypoint_name = %s"
        params.append(keypoint_name)

    sql += " ORDER BY frame_index ASC, keypoint_name ASC LIMIT %s"
    params.append(limit)

    with get_dict_cursor() as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def get_frame_features(
    mouse_id: str,
    limit: int = 1000,
    frame_start: int | None = None,
    frame_end: int | None = None,
) -> list[dict[str, Any]]:
    sql = f"SELECT {FEATURE_FIELDS} FROM behavior_frame_features WHERE mouse_id = %s"
    params: list[Any] = [mouse_id]

    if frame_start is not None:
        sql += " AND frame_index >= %s"
        params.append(frame_start)
    if frame_end is not None:
        sql += " AND frame_index <= %s"
        params.append(frame_end)

    sql += " ORDER BY frame_index ASC LIMIT %s"
    params.append(limit)

    with get_dict_cursor() as cursor:
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def get_summary(mouse_id: str) -> dict[str, Any]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                COUNT(*) AS keypoint_rows,
                COUNT(DISTINCT frame_index) AS frame_count,
                MIN(frame_index) AS first_frame_index,
                MAX(frame_index) AS last_frame_index,
                AVG(confidence) AS avg_keypoint_confidence,
                ARRAY_AGG(DISTINCT source_animal_id) AS source_animal_ids,
                ARRAY_AGG(DISTINCT source_file) AS source_files
            FROM vision_keypoints
            WHERE mouse_id = %s
            """,
            (mouse_id,),
        )
        keypoint_summary = dict(cursor.fetchone())

        cursor.execute(
            """
            SELECT
                COUNT(*) AS feature_rows,
                SUM(movement_distance) AS total_movement_distance,
                AVG(movement_distance) AS avg_movement_distance,
                AVG(mean_confidence) AS avg_frame_confidence
            FROM behavior_frame_features
            WHERE mouse_id = %s
            """,
            (mouse_id,),
        )
        feature_summary = dict(cursor.fetchone())

    return {**keypoint_summary, **feature_summary}
