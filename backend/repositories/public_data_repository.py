from __future__ import annotations

from typing import Any

from psycopg2.extras import Json, execute_values

from backend.database.connection import get_dict_cursor


def _dict(row: Any | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def upsert_source(data: dict[str, Any]) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO public_data_sources (
                source_key, provider, external_id, version, title, description,
                license, landing_url, api_url, asset_count, total_size_bytes,
                status, metadata, last_synced_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (source_key) DO UPDATE SET
                title = EXCLUDED.title,
                description = EXCLUDED.description,
                license = EXCLUDED.license,
                landing_url = EXCLUDED.landing_url,
                api_url = EXCLUDED.api_url,
                asset_count = EXCLUDED.asset_count,
                total_size_bytes = EXCLUDED.total_size_bytes,
                status = EXCLUDED.status,
                metadata = EXCLUDED.metadata,
                last_synced_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (
                data["source_key"], data["provider"], data["external_id"],
                data["version"], data["title"], data.get("description"),
                data.get("license"), data.get("landing_url"), data.get("api_url"),
                data.get("asset_count"), data.get("total_size_bytes"),
                data.get("status", "available"), Json(data.get("metadata") or {}),
            ),
        )
        return dict(cursor.fetchone())


def set_source_status(source_key: str, status: str, error: str | None = None) -> None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            """
            UPDATE public_data_sources
            SET status = %s,
                metadata = CASE
                    WHEN %s IS NULL THEN metadata
                    ELSE jsonb_set(metadata, '{last_error}', to_jsonb(%s::text), true)
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE source_key = %s
            """,
            (status, error, error, source_key),
        )


def upsert_subject(source_id: int, data: dict[str, Any]) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO dataset_subjects (
                source_id, subject_id, species, sex, age, description, metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source_id, subject_id) DO UPDATE SET
                species = COALESCE(EXCLUDED.species, dataset_subjects.species),
                sex = COALESCE(EXCLUDED.sex, dataset_subjects.sex),
                age = COALESCE(EXCLUDED.age, dataset_subjects.age),
                description = COALESCE(EXCLUDED.description, dataset_subjects.description),
                metadata = dataset_subjects.metadata || EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (
                source_id, data["subject_id"], data.get("species"), data.get("sex"),
                data.get("age"), data.get("description"), Json(data.get("metadata") or {}),
            ),
        )
        return dict(cursor.fetchone())


def upsert_session(source_id: int, subject_pk: int, data: dict[str, Any]) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO experiment_sessions (
                source_id, subject_id, session_id, session_started_at,
                timestamps_reference_at, time_reference, description,
                session_type, modeling_stage,
                has_video, has_behavior, has_neural, has_calcium, has_freezing,
                has_shock, has_eeg, has_emg, has_sleep_states, import_status,
                nwb_asset_id, nwb_path, nwb_url, nwb_size_bytes,
                video_asset_id, video_path, video_url, video_size_bytes,
                duration_seconds, metadata, synced_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, CURRENT_TIMESTAMP
            )
            ON CONFLICT (source_id, session_id) DO UPDATE SET
                subject_id = EXCLUDED.subject_id,
                session_started_at = COALESCE(EXCLUDED.session_started_at, experiment_sessions.session_started_at),
                timestamps_reference_at = COALESCE(
                    EXCLUDED.timestamps_reference_at,
                    experiment_sessions.timestamps_reference_at,
                    EXCLUDED.session_started_at
                ),
                time_reference = EXCLUDED.time_reference,
                description = EXCLUDED.description,
                session_type = EXCLUDED.session_type,
                modeling_stage = EXCLUDED.modeling_stage,
                has_video = EXCLUDED.has_video,
                has_behavior = EXCLUDED.has_behavior,
                has_neural = EXCLUDED.has_neural,
                has_calcium = EXCLUDED.has_calcium,
                has_freezing = EXCLUDED.has_freezing,
                has_shock = EXCLUDED.has_shock,
                has_eeg = EXCLUDED.has_eeg,
                has_emg = EXCLUDED.has_emg,
                has_sleep_states = EXCLUDED.has_sleep_states,
                nwb_asset_id = EXCLUDED.nwb_asset_id,
                nwb_path = EXCLUDED.nwb_path,
                nwb_url = EXCLUDED.nwb_url,
                nwb_size_bytes = EXCLUDED.nwb_size_bytes,
                video_asset_id = EXCLUDED.video_asset_id,
                video_path = EXCLUDED.video_path,
                video_url = EXCLUDED.video_url,
                video_size_bytes = EXCLUDED.video_size_bytes,
                metadata = experiment_sessions.metadata || EXCLUDED.metadata,
                synced_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            (
                source_id, subject_pk, data["session_id"], data.get("session_started_at"),
                data.get("timestamps_reference_at") or data.get("session_started_at"),
                data.get("time_reference", "session_start"), data.get("description"),
                data.get("session_type"), data.get("modeling_stage"),
                data.get("has_video", False), data.get("has_behavior", False),
                data.get("has_neural", False), data.get("has_calcium", False),
                data.get("has_freezing", False), data.get("has_shock", False),
                data.get("has_eeg", False), data.get("has_emg", False),
                data.get("has_sleep_states", False),
                data.get("import_status", "catalogued"), data["nwb_asset_id"],
                data["nwb_path"], data["nwb_url"], data.get("nwb_size_bytes"),
                data.get("video_asset_id"), data.get("video_path"), data.get("video_url"),
                data.get("video_size_bytes"), data.get("duration_seconds"),
                Json(data.get("metadata") or {}),
            ),
        )
        return dict(cursor.fetchone())


def upsert_session_asset(session_pk: int, data: dict[str, Any]) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO session_assets (
                session_id, asset_id, asset_role, path, content_url,
                size_bytes, media_type, metadata
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (session_id, asset_id) DO UPDATE SET
                asset_role = EXCLUDED.asset_role,
                path = EXCLUDED.path,
                content_url = EXCLUDED.content_url,
                size_bytes = EXCLUDED.size_bytes,
                media_type = EXCLUDED.media_type,
                metadata = session_assets.metadata || EXCLUDED.metadata
            RETURNING *
            """,
            (
                session_pk, data["asset_id"], data["asset_role"], data["path"],
                data.get("content_url"), data.get("size_bytes"), data.get("media_type"),
                Json(data.get("metadata") or {}),
            ),
        )
        return dict(cursor.fetchone())


def normalize_session_modalities(source_id: int) -> None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            """
            UPDATE experiment_sessions
            SET has_neural = (
                    LOWER(nwb_path) LIKE '%%ecephys%%'
                    OR COALESCE(metadata -> 'variables', '[]'::jsonb) ?| ARRAY['ElectricalSeries', 'Units']
                ),
                updated_at = CURRENT_TIMESTAMP
            WHERE source_id = %s
            """,
            (source_id,),
        )


def get_source() -> dict[str, Any] | None:
    with get_dict_cursor() as cursor:
        cursor.execute("SELECT * FROM public_data_sources ORDER BY updated_at DESC LIMIT 1")
        return _dict(cursor.fetchone())


def get_stats() -> dict[str, Any]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM dataset_subjects) AS subject_count,
                (SELECT COUNT(*) FROM experiment_sessions) AS session_count,
                (SELECT COUNT(*) FROM experiment_sessions WHERE has_video) AS video_session_count,
                (SELECT COUNT(*) FROM experiment_sessions WHERE has_calcium) AS calcium_session_count,
                (SELECT COUNT(*) FROM experiment_sessions WHERE has_freezing) AS freezing_session_count,
                (SELECT COUNT(*) FROM experiment_sessions WHERE has_shock) AS shock_session_count,
                (SELECT COUNT(*) FROM experiment_sessions WHERE has_eeg) AS eeg_session_count,
                (SELECT COUNT(*) FROM experiment_sessions WHERE has_emg) AS emg_session_count,
                (SELECT COUNT(*) FROM experiment_sessions WHERE has_sleep_states) AS sleep_session_count,
                (SELECT COUNT(*) FROM experiment_sessions WHERE import_status = 'ready') AS imported_session_count,
                (SELECT COUNT(*) FROM modeling_events) AS modeling_event_count,
                (SELECT COUNT(*) FROM multimodal_signal_windows) AS signal_window_count,
                (SELECT COUNT(*) FROM calcium_roi_metrics) AS calcium_roi_count,
                (SELECT COUNT(*) FROM session_annotations) AS annotation_count,
                (SELECT COUNT(*) FROM session_agent_analyses) AS analysis_count
            """
        )
        return dict(cursor.fetchone())


def get_subjects() -> list[dict[str, Any]]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            """
            SELECT ds.*, COUNT(es.id)::integer AS session_count,
                   COUNT(es.id) FILTER (WHERE es.has_video)::integer AS video_count,
                   MIN(es.session_started_at) AS first_session_at,
                   MAX(es.session_started_at) AS last_session_at
            FROM dataset_subjects ds
            LEFT JOIN experiment_sessions es ON es.subject_id = ds.id
            GROUP BY ds.id
            ORDER BY ds.subject_id
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def get_sessions(subject_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = """
        SELECT es.*, ds.subject_id AS subject_code, ds.species, ds.sex, ds.age,
               pds.title AS source_title, pds.version AS source_version,
               (SELECT COUNT(*) FROM modeling_events me WHERE me.session_id = es.id)::integer AS modeling_event_count,
               (SELECT COUNT(*) FROM multimodal_signal_windows sw WHERE sw.session_id = es.id)::integer AS signal_window_count,
               (SELECT COUNT(*) FROM calcium_roi_metrics cr WHERE cr.session_id = es.id)::integer AS calcium_roi_count,
               (SELECT COUNT(*) FROM session_assets sa2 WHERE sa2.session_id = es.id)::integer AS asset_count,
               (SELECT COUNT(*) FROM session_annotations sa WHERE sa.session_id = es.id)::integer AS annotation_count
        FROM experiment_sessions es
        JOIN dataset_subjects ds ON ds.id = es.subject_id
        JOIN public_data_sources pds ON pds.id = es.source_id
    """
    params: list[Any] = []
    if subject_id:
        query += " WHERE ds.subject_id = %s"
        params.append(subject_id)
    query += " ORDER BY es.session_started_at DESC NULLS LAST, es.id DESC LIMIT %s"
    params.append(limit)
    with get_dict_cursor() as cursor:
        cursor.execute(query, tuple(params))
        return [dict(row) for row in cursor.fetchall()]


def get_session(session_pk: int) -> dict[str, Any] | None:
    with get_dict_cursor() as cursor:
        cursor.execute(
            """
            SELECT es.*, ds.subject_id AS subject_code, ds.species, ds.sex, ds.age,
                   pds.title AS source_title, pds.version AS source_version,
                   pds.landing_url AS source_url,
                   (SELECT COUNT(*) FROM session_assets sa WHERE sa.session_id = es.id)::integer AS asset_count
            FROM experiment_sessions es
            JOIN dataset_subjects ds ON ds.id = es.subject_id
            JOIN public_data_sources pds ON pds.id = es.source_id
            WHERE es.id = %s
            """,
            (session_pk,),
        )
        return _dict(cursor.fetchone())


def get_timeline(session_pk: int) -> dict[str, list[dict[str, Any]]]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            """SELECT * FROM modeling_events WHERE session_id = %s
               ORDER BY start_time_seconds, id""",
            (session_pk,),
        )
        events = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """SELECT * FROM multimodal_signal_windows WHERE session_id = %s
               ORDER BY window_start_seconds, modality, signal_name, id""",
            (session_pk,),
        )
        signals = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """SELECT * FROM calcium_roi_metrics WHERE session_id = %s
               ORDER BY roi_index, id""",
            (session_pk,),
        )
        roi_metrics = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """SELECT * FROM session_annotations WHERE session_id = %s
               ORDER BY timestamp_seconds NULLS LAST, created_at""",
            (session_pk,),
        )
        annotations = [dict(row) for row in cursor.fetchall()]
    return {
        "modeling_events": events,
        "signal_windows": signals,
        "roi_metrics": roi_metrics,
        "annotations": annotations,
    }


def create_annotation(session_pk: int, data: dict[str, Any]) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO session_annotations (
                session_id, timestamp_seconds, category, note, created_by
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                session_pk, data.get("timestamp_seconds"), data["category"],
                data["note"], data.get("created_by", "researcher"),
            ),
        )
        return dict(cursor.fetchone())


def delete_annotation(session_pk: int, annotation_id: int) -> dict[str, Any] | None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            """
            DELETE FROM session_annotations
            WHERE id = %s AND session_id = %s
            RETURNING *
            """,
            (annotation_id, session_pk),
        )
        return _dict(cursor.fetchone())


def create_analysis(session_pk: int, data: dict[str, Any]) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            """
            INSERT INTO session_agent_analyses (
                session_id, parent_analysis_id, question, summary, evidence, recommendation,
                confidence, analysis_source, model_name, knowledge_sources,
                retrieval_mode
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                session_pk, data.get("parent_analysis_id"),
                data.get("question"), data["summary"],
                Json(data.get("evidence") or []), data.get("recommendation"),
                data.get("confidence"), data.get("analysis_source", "evidence_rules"),
                data.get("model_name"),
                Json(data.get("knowledge_sources") or []),
                data.get("retrieval_mode"),
            ),
        )
        return dict(cursor.fetchone())


def get_analysis(session_pk: int, analysis_id: int) -> dict[str, Any] | None:
    with get_dict_cursor() as cursor:
        cursor.execute(
            """
            SELECT *
            FROM session_agent_analyses
            WHERE id = %s AND session_id = %s
            """,
            (analysis_id, session_pk),
        )
        return _dict(cursor.fetchone())


def get_analyses(session_pk: int, limit: int = 20) -> list[dict[str, Any]]:
    with get_dict_cursor() as cursor:
        cursor.execute(
            """
            SELECT analysis.*,
                   parent.question AS parent_question,
                   parent.created_at AS parent_created_at
            FROM session_agent_analyses AS analysis
            LEFT JOIN session_agent_analyses AS parent
              ON parent.id = analysis.parent_analysis_id
            WHERE analysis.session_id = %s
            ORDER BY analysis.created_at DESC, analysis.id DESC
            LIMIT %s
            """,
            (session_pk, limit),
        )
        return [dict(row) for row in cursor.fetchall()]


def set_import_status(
    session_pk: int,
    status: str,
    *,
    error: str | None = None,
) -> None:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute(
            """
            UPDATE experiment_sessions
            SET import_status = %s,
                last_error = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (status, error, session_pk),
        )


def replace_multimodal_content(
    session_pk: int,
    *,
    modeling_events: list[dict[str, Any]],
    signal_windows: list[dict[str, Any]],
    roi_metrics: list[dict[str, Any]],
    duration_seconds: float | None,
    timestamps_reference_at: Any | None = None,
) -> dict[str, Any]:
    with get_dict_cursor(commit=True) as cursor:
        cursor.execute("DELETE FROM modeling_events WHERE session_id = %s", (session_pk,))
        cursor.execute("DELETE FROM multimodal_signal_windows WHERE session_id = %s", (session_pk,))
        cursor.execute("DELETE FROM calcium_roi_metrics WHERE session_id = %s", (session_pk,))
        if modeling_events:
            execute_values(
                cursor,
                """
                INSERT INTO modeling_events (
                    session_id, event_type, event_label, start_time_seconds,
                    stop_time_seconds, event_started_at, event_stopped_at,
                    numeric_value, unit, metadata, source_path
                ) VALUES %s
                """,
                [
                    (
                        session_pk,
                        item["event_type"],
                        item.get("event_label"),
                        item["start_time_seconds"],
                        item.get("stop_time_seconds"),
                        item.get("event_started_at"),
                        item.get("event_stopped_at"),
                        item.get("numeric_value"),
                        item.get("unit"),
                        Json(item.get("metadata") or {}),
                        item.get("source_path"),
                    )
                    for item in modeling_events
                ],
            )
        if signal_windows:
            execute_values(
                cursor,
                """
                INSERT INTO multimodal_signal_windows (
                    session_id, modality, signal_name, channel_name,
                    window_start_seconds, window_end_seconds,
                    window_started_at, window_ended_at, mean_value,
                    min_value, max_value, std_value, unit, sample_count,
                    metadata, source_path
                ) VALUES %s
                """,
                [
                    (
                        session_pk,
                        item["modality"],
                        item["signal_name"],
                        item.get("channel_name"),
                        item["window_start_seconds"],
                        item["window_end_seconds"],
                        item.get("window_started_at"),
                        item.get("window_ended_at"),
                        item.get("mean_value"),
                        item.get("min_value"),
                        item.get("max_value"),
                        item.get("std_value"),
                        item.get("unit"),
                        item.get("sample_count"),
                        Json(item.get("metadata") or {}),
                        item.get("source_path"),
                    )
                    for item in signal_windows
                ],
            )
        if roi_metrics:
            execute_values(
                cursor,
                """
                INSERT INTO calcium_roi_metrics (
                    session_id, roi_index, mean_activity, peak_activity,
                    activity_std, active_fraction, sample_count, metadata, source_path
                ) VALUES %s
                """,
                [
                    (
                        session_pk, item["roi_index"], item.get("mean_activity"),
                        item.get("peak_activity"), item.get("activity_std"),
                        item.get("active_fraction"), item.get("sample_count"),
                        Json(item.get("metadata") or {}), item.get("source_path"),
                    )
                    for item in roi_metrics
                ],
            )
        event_types = {item["event_type"] for item in modeling_events}
        modalities = {item["modality"] for item in signal_windows}
        cursor.execute(
            """
            UPDATE experiment_sessions
            SET import_status = 'ready',
                duration_seconds = %s,
                timestamps_reference_at = COALESCE(%s, timestamps_reference_at, session_started_at),
                time_reference = 'session_start',
                has_behavior = %s,
                has_neural = %s,
                has_calcium = %s,
                has_freezing = %s,
                has_shock = %s,
                has_eeg = %s,
                has_emg = %s,
                has_sleep_states = %s,
                last_error = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *
            """,
            (
                duration_seconds,
                timestamps_reference_at,
                bool(event_types & {"freezing", "sleep_state", "behavior_state"})
                or "motion" in modalities,
                bool(modalities & {"calcium", "eeg", "emg"}),
                "calcium" in modalities,
                "freezing" in event_types,
                "electric_shock" in event_types,
                "eeg" in modalities,
                "emg" in modalities,
                "sleep_state" in event_types,
                session_pk,
            ),
        )
        return dict(cursor.fetchone())


def get_aligned_subject_timeline(subject_code: str) -> dict[str, Any] | None:
    """Return every session for one subject on an absolute acquisition-time axis."""
    with get_dict_cursor() as cursor:
        cursor.execute(
            """
            SELECT ds.id, ds.subject_id, ds.species, ds.sex, ds.age
            FROM dataset_subjects ds
            WHERE ds.subject_id = %s
            """,
            (subject_code,),
        )
        subject = cursor.fetchone()
        if subject is None:
            return None

        cursor.execute(
            """
            SELECT es.*,
                   COALESCE(es.timestamps_reference_at, es.session_started_at) AS timeline_origin_at,
                   CASE
                       WHEN es.duration_seconds IS NULL THEN NULL
                       ELSE COALESCE(es.timestamps_reference_at, es.session_started_at)
                            + make_interval(secs => es.duration_seconds)
                   END AS session_ended_at
            FROM experiment_sessions es
            WHERE es.subject_id = %s
            ORDER BY COALESCE(es.timestamps_reference_at, es.session_started_at), es.id
            """,
            (subject["id"],),
        )
        sessions = [dict(row) for row in cursor.fetchall()]
        session_ids = [int(item["id"]) for item in sessions]
        if not session_ids:
            return {
                "subject": dict(subject),
                "sessions": [],
                "modeling_events": [],
                "signal_windows": [],
                "annotations": [],
                "range_started_at": None,
                "range_ended_at": None,
            }

        cursor.execute(
            """
            SELECT me.*, es.session_id AS session_code, es.session_type,
                   COALESCE(
                       me.event_started_at,
                       COALESCE(es.timestamps_reference_at, es.session_started_at)
                           + make_interval(secs => me.start_time_seconds)
                   ) AS aligned_started_at,
                   COALESCE(
                       me.event_stopped_at,
                       CASE WHEN me.stop_time_seconds IS NULL THEN NULL
                            ELSE COALESCE(es.timestamps_reference_at, es.session_started_at)
                                 + make_interval(secs => me.stop_time_seconds)
                       END
                   ) AS aligned_stopped_at
            FROM modeling_events me
            JOIN experiment_sessions es ON es.id = me.session_id
            WHERE me.session_id = ANY(%s)
            ORDER BY aligned_started_at, me.id
            """,
            (session_ids,),
        )
        events = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT sw.*, es.session_id AS session_code, es.session_type,
                   COALESCE(
                       sw.window_started_at,
                       COALESCE(es.timestamps_reference_at, es.session_started_at)
                           + make_interval(secs => sw.window_start_seconds)
                   ) AS aligned_started_at,
                   COALESCE(
                       sw.window_ended_at,
                       COALESCE(es.timestamps_reference_at, es.session_started_at)
                           + make_interval(secs => sw.window_end_seconds)
                   ) AS aligned_ended_at
            FROM multimodal_signal_windows sw
            JOIN experiment_sessions es ON es.id = sw.session_id
            WHERE sw.session_id = ANY(%s)
            ORDER BY aligned_started_at, sw.modality, sw.id
            """,
            (session_ids,),
        )
        signals = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT sa.*, es.session_id AS session_code, es.session_type,
                   CASE WHEN sa.timestamp_seconds IS NULL THEN NULL
                        ELSE COALESCE(es.timestamps_reference_at, es.session_started_at)
                             + make_interval(secs => sa.timestamp_seconds)
                   END AS aligned_at
            FROM session_annotations sa
            JOIN experiment_sessions es ON es.id = sa.session_id
            WHERE sa.session_id = ANY(%s)
            ORDER BY aligned_at NULLS LAST, sa.id
            """,
            (session_ids,),
        )
        annotations = [dict(row) for row in cursor.fetchall()]

    starts = [item.get("timeline_origin_at") for item in sessions if item.get("timeline_origin_at")]
    ends = [
        item.get("session_ended_at") or item.get("timeline_origin_at")
        for item in sessions
        if item.get("session_ended_at") or item.get("timeline_origin_at")
    ]
    return {
        "subject": dict(subject),
        "sessions": sessions,
        "modeling_events": events,
        "signal_windows": signals,
        "annotations": annotations,
        "range_started_at": min(starts) if starts else None,
        "range_ended_at": max(ends) if ends else None,
        "alignment_basis": "nwb_session_start_plus_relative_timestamp",
    }

