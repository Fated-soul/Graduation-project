from __future__ import annotations

import sys

from backend.config import DB_NAME
from backend.database.connection import DatabaseConnectionError, get_connection


TABLE_SQL = [
    """
    CREATE TABLE IF NOT EXISTS animals (
        id BIGSERIAL PRIMARY KEY,
        mouse_id VARCHAR(50) UNIQUE NOT NULL,
        current_status VARCHAR(50) NOT NULL DEFAULT 'normal'
            CHECK (current_status IN ('normal', 'attention', 'high_risk', 'offline')),
        experiment_name VARCHAR(100) DEFAULT '行为无助造模'
            CHECK (experiment_name IS NULL OR experiment_name = '行为无助造模'),
        experiment_stage VARCHAR(100),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS devices (
        id BIGSERIAL PRIMARY KEY,
        device_id VARCHAR(50) UNIQUE NOT NULL,
        device_type VARCHAR(50) NOT NULL,
        device_name VARCHAR(100) NOT NULL,
        mouse_id VARCHAR(50) REFERENCES animals(mouse_id)
            ON UPDATE CASCADE ON DELETE SET NULL,
        online BOOLEAN NOT NULL DEFAULT FALSE,
        voltage DOUBLE PRECISION CHECK (voltage IS NULL OR voltage >= 0),
        current DOUBLE PRECISION CHECK (current IS NULL OR current >= 0),
        last_seen TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS vision_keypoints (
        id BIGSERIAL PRIMARY KEY,
        mouse_id VARCHAR(50) NOT NULL REFERENCES animals(mouse_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        source_animal_id VARCHAR(50) NOT NULL,
        frame_index INTEGER NOT NULL CHECK (frame_index >= 0),
        keypoint_name VARCHAR(100) NOT NULL,
        x DOUBLE PRECISION,
        y DOUBLE PRECISION,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        source_file VARCHAR(255) NOT NULL,
        recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_vision_keypoint_source UNIQUE (
            source_file, frame_index, source_animal_id, keypoint_name
        )
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS behavior_frame_features (
        id BIGSERIAL PRIMARY KEY,
        mouse_id VARCHAR(50) NOT NULL REFERENCES animals(mouse_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        source_animal_id VARCHAR(50) NOT NULL,
        frame_index INTEGER NOT NULL CHECK (frame_index >= 0),
        center_x DOUBLE PRECISION,
        center_y DOUBLE PRECISION,
        movement_distance DOUBLE PRECISION CHECK (
            movement_distance IS NULL OR movement_distance >= 0
        ),
        mean_confidence DOUBLE PRECISION CHECK (
            mean_confidence IS NULL OR mean_confidence BETWEEN 0 AND 1
        ),
        keypoint_count INTEGER NOT NULL CHECK (keypoint_count >= 0),
        source_file VARCHAR(255) NOT NULL,
        recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_behavior_feature_source UNIQUE (
            source_file, frame_index, source_animal_id
        )
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS telemetry (
        id BIGSERIAL PRIMARY KEY,
        mouse_id VARCHAR(50) REFERENCES animals(mouse_id)
            ON UPDATE CASCADE ON DELETE SET NULL,
        device_id VARCHAR(50) NOT NULL REFERENCES devices(device_id)
            ON UPDATE CASCADE ON DELETE RESTRICT,
        temperature DOUBLE PRECISION CHECK (temperature IS NULL OR temperature BETWEEN -50 AND 100),
        humidity DOUBLE PRECISION CHECK (humidity IS NULL OR humidity BETWEEN 0 AND 100),
        is_dark BOOLEAN,
        voltage DOUBLE PRECISION CHECK (voltage IS NULL OR voltage >= 0),
        current DOUBLE PRECISION CHECK (current IS NULL OR current >= 0),
        recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_telemetry_source_time UNIQUE (mouse_id, device_id, recorded_at)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS vital_signs (
        id BIGSERIAL PRIMARY KEY,
        mouse_id VARCHAR(50) NOT NULL REFERENCES animals(mouse_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        device_id VARCHAR(50) NOT NULL REFERENCES devices(device_id)
            ON UPDATE CASCADE ON DELETE RESTRICT,
        body_temperature DOUBLE PRECISION CHECK (body_temperature IS NULL OR body_temperature BETWEEN 20 AND 45),
        heart_rate DOUBLE PRECISION CHECK (heart_rate IS NULL OR heart_rate BETWEEN 0 AND 1000),
        blood_oxygen DOUBLE PRECISION CHECK (blood_oxygen IS NULL OR blood_oxygen BETWEEN 0 AND 100),
        recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_vital_signs_source_time UNIQUE (mouse_id, device_id, recorded_at)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS stimulation_events (
        id BIGSERIAL PRIMARY KEY,
        mouse_id VARCHAR(50) NOT NULL REFERENCES animals(mouse_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        device_id VARCHAR(50) NOT NULL REFERENCES devices(device_id)
            ON UPDATE CASCADE ON DELETE RESTRICT,
        event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('electric_shock', 'flash', 'noise')),
        duration_ms INTEGER NOT NULL CHECK (duration_ms > 0),
        intensity DOUBLE PRECISION CHECK (intensity IS NULL OR intensity >= 0),
        is_active BOOLEAN NOT NULL DEFAULT FALSE,
        next_interval_ms INTEGER CHECK (next_interval_ms IS NULL OR next_interval_ms >= 0),
        next_trigger_at TIMESTAMP WITH TIME ZONE,
        started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ended_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT stimulation_time_check CHECK (ended_at IS NULL OR ended_at >= started_at),
        CONSTRAINT uq_stimulation_source_time UNIQUE (mouse_id, device_id, event_type, started_at)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS stimulation_settings (
        id BIGSERIAL PRIMARY KEY,
        mouse_id VARCHAR(50) REFERENCES animals(mouse_id)
            ON UPDATE CASCADE ON DELETE SET NULL,
        device_id VARCHAR(50) NOT NULL REFERENCES devices(device_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('electric_shock', 'flash', 'noise')),
        enabled BOOLEAN NOT NULL DEFAULT TRUE,
        min_interval_ms INTEGER NOT NULL CHECK (min_interval_ms >= 0),
        max_interval_ms INTEGER NOT NULL CHECK (max_interval_ms >= min_interval_ms),
        min_duration_ms INTEGER NOT NULL CHECK (min_duration_ms > 0),
        max_duration_ms INTEGER NOT NULL CHECK (max_duration_ms >= min_duration_ms),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_stimulation_settings_device_event UNIQUE (device_id, event_type)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS control_commands (
        id BIGSERIAL PRIMARY KEY,
        command_id VARCHAR(64) UNIQUE NOT NULL,
        mouse_id VARCHAR(50) NOT NULL REFERENCES animals(mouse_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        device_id VARCHAR(50) NOT NULL REFERENCES devices(device_id)
            ON UPDATE CASCADE ON DELETE RESTRICT,
        command_type VARCHAR(50) NOT NULL CHECK (command_type IN ('electric_shock', 'flash', 'noise')),
        duration_ms INTEGER NOT NULL CHECK (duration_ms > 0),
        intensity DOUBLE PRECISION CHECK (intensity IS NULL OR intensity >= 0),
        status VARCHAR(50) NOT NULL DEFAULT 'pending'
            CHECK (status IN ('pending', 'sent', 'completed', 'failed', 'expired')),
        requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        dispatched_at TIMESTAMP WITH TIME ZONE,
        acknowledged_at TIMESTAMP WITH TIME ZONE,
        error_message TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_analysis_results (
        id BIGSERIAL PRIMARY KEY,
        mouse_id VARCHAR(50) NOT NULL REFERENCES animals(mouse_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        risk_score INTEGER NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
        risk_level VARCHAR(50) NOT NULL,
        summary TEXT NOT NULL,
        vital_analysis TEXT,
        behavior_analysis TEXT,
        stage_analysis TEXT,
        risk_analysis TEXT,
        recommendation TEXT,
        control_strategy TEXT,
        factors JSONB NOT NULL DEFAULT '[]'::jsonb,
        analysis_source VARCHAR(50) NOT NULL DEFAULT 'system',
        model_provider VARCHAR(50),
        model_name VARCHAR(100),
        decision_status VARCHAR(20) NOT NULL DEFAULT 'pending'
            CHECK (decision_status IN ('pending', 'confirmed', 'rejected')),
        decided_at TIMESTAMP WITH TIME ZONE,
        analyzed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS animal_status_history (
        id BIGSERIAL PRIMARY KEY,
        mouse_id VARCHAR(50) NOT NULL REFERENCES animals(mouse_id)
            ON UPDATE CASCADE ON DELETE CASCADE,
        status VARCHAR(50) NOT NULL CHECK (status IN ('normal', 'attention', 'high_risk', 'offline')),
        reason TEXT,
        recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS public_data_sources (
        id BIGSERIAL PRIMARY KEY,
        source_key VARCHAR(120) UNIQUE NOT NULL,
        provider VARCHAR(50) NOT NULL,
        external_id VARCHAR(100) NOT NULL,
        version VARCHAR(100) NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        license VARCHAR(100),
        landing_url TEXT,
        api_url TEXT,
        asset_count INTEGER CHECK (asset_count IS NULL OR asset_count >= 0),
        total_size_bytes BIGINT CHECK (total_size_bytes IS NULL OR total_size_bytes >= 0),
        status VARCHAR(30) NOT NULL DEFAULT 'available'
            CHECK (status IN ('available', 'syncing', 'error', 'archived')),
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        last_synced_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS dataset_subjects (
        id BIGSERIAL PRIMARY KEY,
        source_id BIGINT NOT NULL REFERENCES public_data_sources(id) ON DELETE CASCADE,
        subject_id VARCHAR(100) NOT NULL,
        species VARCHAR(150),
        sex VARCHAR(30),
        age VARCHAR(100),
        description TEXT,
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_dataset_subject UNIQUE (source_id, subject_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS experiment_sessions (
        id BIGSERIAL PRIMARY KEY,
        source_id BIGINT NOT NULL REFERENCES public_data_sources(id) ON DELETE CASCADE,
        subject_id BIGINT NOT NULL REFERENCES dataset_subjects(id) ON DELETE CASCADE,
        session_id VARCHAR(160) NOT NULL,
        session_started_at TIMESTAMP WITH TIME ZONE,
        timestamps_reference_at TIMESTAMP WITH TIME ZONE,
        time_reference VARCHAR(40) NOT NULL DEFAULT 'session_start',
        description TEXT,
        has_video BOOLEAN NOT NULL DEFAULT FALSE,
        has_behavior BOOLEAN NOT NULL DEFAULT FALSE,
        has_neural BOOLEAN NOT NULL DEFAULT FALSE,
        session_type VARCHAR(50),
        modeling_stage VARCHAR(80),
        has_calcium BOOLEAN NOT NULL DEFAULT FALSE,
        has_freezing BOOLEAN NOT NULL DEFAULT FALSE,
        has_shock BOOLEAN NOT NULL DEFAULT FALSE,
        has_eeg BOOLEAN NOT NULL DEFAULT FALSE,
        has_emg BOOLEAN NOT NULL DEFAULT FALSE,
        has_sleep_states BOOLEAN NOT NULL DEFAULT FALSE,
        import_status VARCHAR(30) NOT NULL DEFAULT 'catalogued'
            CHECK (import_status IN ('catalogued', 'importing', 'ready', 'error')),
        nwb_asset_id VARCHAR(80) NOT NULL,
        nwb_path TEXT NOT NULL,
        nwb_url TEXT NOT NULL,
        nwb_size_bytes BIGINT CHECK (nwb_size_bytes IS NULL OR nwb_size_bytes >= 0),
        video_asset_id VARCHAR(80),
        video_path TEXT,
        video_url TEXT,
        video_size_bytes BIGINT CHECK (video_size_bytes IS NULL OR video_size_bytes >= 0),
        duration_seconds DOUBLE PRECISION CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        last_error TEXT,
        synced_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_experiment_session UNIQUE (source_id, session_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS session_assets (
        id BIGSERIAL PRIMARY KEY,
        session_id BIGINT NOT NULL REFERENCES experiment_sessions(id) ON DELETE CASCADE,
        asset_id VARCHAR(80) NOT NULL,
        asset_role VARCHAR(40) NOT NULL
            CHECK (asset_role IN ('nwb', 'behavior_video', 'calcium_video', 'other')),
        path TEXT NOT NULL,
        content_url TEXT NOT NULL,
        size_bytes BIGINT CHECK (size_bytes IS NULL OR size_bytes >= 0),
        media_type VARCHAR(100),
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_session_asset UNIQUE (session_id, asset_id)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS modeling_events (
        id BIGSERIAL PRIMARY KEY,
        session_id BIGINT NOT NULL REFERENCES experiment_sessions(id) ON DELETE CASCADE,
        event_type VARCHAR(50) NOT NULL
            CHECK (event_type IN ('freezing', 'electric_shock', 'sleep_state', 'behavior_state', 'experiment_phase')),
        event_label VARCHAR(160),
        start_time_seconds DOUBLE PRECISION NOT NULL CHECK (start_time_seconds >= 0),
        stop_time_seconds DOUBLE PRECISION CHECK (
            stop_time_seconds IS NULL OR stop_time_seconds >= start_time_seconds
        ),
        event_started_at TIMESTAMP WITH TIME ZONE,
        event_stopped_at TIMESTAMP WITH TIME ZONE,
        numeric_value DOUBLE PRECISION,
        unit VARCHAR(50),
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        source_path TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS multimodal_signal_windows (
        id BIGSERIAL PRIMARY KEY,
        session_id BIGINT NOT NULL REFERENCES experiment_sessions(id) ON DELETE CASCADE,
        modality VARCHAR(30) NOT NULL
            CHECK (modality IN ('calcium', 'eeg', 'emg', 'motion')),
        signal_name VARCHAR(160) NOT NULL,
        channel_name VARCHAR(160),
        window_start_seconds DOUBLE PRECISION NOT NULL CHECK (window_start_seconds >= 0),
        window_end_seconds DOUBLE PRECISION NOT NULL CHECK (window_end_seconds >= window_start_seconds),
        window_started_at TIMESTAMP WITH TIME ZONE,
        window_ended_at TIMESTAMP WITH TIME ZONE,
        mean_value DOUBLE PRECISION NOT NULL,
        min_value DOUBLE PRECISION,
        max_value DOUBLE PRECISION,
        std_value DOUBLE PRECISION,
        unit VARCHAR(50),
        sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        source_path TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS calcium_roi_metrics (
        id BIGSERIAL PRIMARY KEY,
        session_id BIGINT NOT NULL REFERENCES experiment_sessions(id) ON DELETE CASCADE,
        roi_index INTEGER NOT NULL CHECK (roi_index >= 0),
        mean_activity DOUBLE PRECISION,
        peak_activity DOUBLE PRECISION,
        activity_std DOUBLE PRECISION,
        active_fraction DOUBLE PRECISION CHECK (active_fraction IS NULL OR active_fraction BETWEEN 0 AND 1),
        sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
        metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
        source_path TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
        CONSTRAINT uq_calcium_roi_session UNIQUE (session_id, roi_index)
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS behavioral_events (
        id BIGSERIAL PRIMARY KEY,
        session_id BIGINT NOT NULL REFERENCES experiment_sessions(id) ON DELETE CASCADE,
        event_type VARCHAR(100) NOT NULL,
        event_name VARCHAR(160),
        start_time_seconds DOUBLE PRECISION NOT NULL CHECK (start_time_seconds >= 0),
        stop_time_seconds DOUBLE PRECISION CHECK (
            stop_time_seconds IS NULL OR stop_time_seconds >= start_time_seconds
        ),
        numeric_value DOUBLE PRECISION,
        text_value TEXT,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        source_path TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS neural_signal_summaries (
        id BIGSERIAL PRIMARY KEY,
        session_id BIGINT NOT NULL REFERENCES experiment_sessions(id) ON DELETE CASCADE,
        timestamp_seconds DOUBLE PRECISION NOT NULL CHECK (timestamp_seconds >= 0),
        signal_name VARCHAR(160) NOT NULL,
        channel_name VARCHAR(160),
        value DOUBLE PRECISION NOT NULL,
        unit VARCHAR(50),
        sample_count INTEGER CHECK (sample_count IS NULL OR sample_count >= 0),
        source_path TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS session_annotations (
        id BIGSERIAL PRIMARY KEY,
        session_id BIGINT NOT NULL REFERENCES experiment_sessions(id) ON DELETE CASCADE,
        timestamp_seconds DOUBLE PRECISION CHECK (timestamp_seconds IS NULL OR timestamp_seconds >= 0),
        category VARCHAR(80) NOT NULL,
        note TEXT NOT NULL,
        created_by VARCHAR(100) NOT NULL DEFAULT 'researcher',
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS session_agent_analyses (
        id BIGSERIAL PRIMARY KEY,
        session_id BIGINT NOT NULL REFERENCES experiment_sessions(id) ON DELETE CASCADE,
        parent_analysis_id BIGINT REFERENCES session_agent_analyses(id) ON DELETE SET NULL,
        question TEXT,
        summary TEXT NOT NULL,
        evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
        recommendation TEXT,
        confidence DOUBLE PRECISION CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
        analysis_source VARCHAR(50) NOT NULL DEFAULT 'evidence_rules',
        model_name VARCHAR(100),
        knowledge_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
        retrieval_mode VARCHAR(30),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
]

MIGRATION_SQL = [
    "DELETE FROM public_data_sources WHERE external_id = '000231';",
    "ALTER TABLE experiment_sessions ADD COLUMN IF NOT EXISTS session_type VARCHAR(50);",
    "ALTER TABLE experiment_sessions ADD COLUMN IF NOT EXISTS modeling_stage VARCHAR(80);",
    "ALTER TABLE experiment_sessions ADD COLUMN IF NOT EXISTS has_calcium BOOLEAN NOT NULL DEFAULT FALSE;",
    "ALTER TABLE experiment_sessions ADD COLUMN IF NOT EXISTS has_freezing BOOLEAN NOT NULL DEFAULT FALSE;",
    "ALTER TABLE experiment_sessions ADD COLUMN IF NOT EXISTS has_shock BOOLEAN NOT NULL DEFAULT FALSE;",
    "ALTER TABLE experiment_sessions ADD COLUMN IF NOT EXISTS has_eeg BOOLEAN NOT NULL DEFAULT FALSE;",
    "ALTER TABLE experiment_sessions ADD COLUMN IF NOT EXISTS has_emg BOOLEAN NOT NULL DEFAULT FALSE;",
    "ALTER TABLE experiment_sessions ADD COLUMN IF NOT EXISTS has_sleep_states BOOLEAN NOT NULL DEFAULT FALSE;",
    "ALTER TABLE experiment_sessions ADD COLUMN IF NOT EXISTS timestamps_reference_at TIMESTAMP WITH TIME ZONE;",
    "ALTER TABLE experiment_sessions ADD COLUMN IF NOT EXISTS time_reference VARCHAR(40) NOT NULL DEFAULT 'session_start';",
    "ALTER TABLE modeling_events ADD COLUMN IF NOT EXISTS event_started_at TIMESTAMP WITH TIME ZONE;",
    "ALTER TABLE modeling_events ADD COLUMN IF NOT EXISTS event_stopped_at TIMESTAMP WITH TIME ZONE;",
    "ALTER TABLE multimodal_signal_windows ADD COLUMN IF NOT EXISTS window_started_at TIMESTAMP WITH TIME ZONE;",
    "ALTER TABLE multimodal_signal_windows ADD COLUMN IF NOT EXISTS window_ended_at TIMESTAMP WITH TIME ZONE;",
    "ALTER TABLE session_agent_analyses ADD COLUMN IF NOT EXISTS knowledge_sources JSONB NOT NULL DEFAULT '[]'::jsonb;",
    "ALTER TABLE session_agent_analyses ADD COLUMN IF NOT EXISTS retrieval_mode VARCHAR(30);",
    "ALTER TABLE session_agent_analyses ADD COLUMN IF NOT EXISTS parent_analysis_id BIGINT;",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'session_agent_analyses'::regclass
              AND conname = 'session_agent_analyses_parent_analysis_id_fkey'
        ) THEN
            ALTER TABLE session_agent_analyses
            ADD CONSTRAINT session_agent_analyses_parent_analysis_id_fkey
            FOREIGN KEY (parent_analysis_id)
            REFERENCES session_agent_analyses(id)
            ON DELETE SET NULL;
        END IF;
    END $$;
    """,
    """
    UPDATE experiment_sessions
    SET timestamps_reference_at = session_started_at
    WHERE timestamps_reference_at IS NULL
      AND session_started_at IS NOT NULL;
    """,
    """
    UPDATE modeling_events me
    SET event_started_at = COALESCE(es.timestamps_reference_at, es.session_started_at)
            + make_interval(secs => me.start_time_seconds),
        event_stopped_at = CASE
            WHEN me.stop_time_seconds IS NULL THEN NULL
            ELSE COALESCE(es.timestamps_reference_at, es.session_started_at)
                 + make_interval(secs => me.stop_time_seconds)
        END
    FROM experiment_sessions es
    WHERE me.session_id = es.id
      AND COALESCE(es.timestamps_reference_at, es.session_started_at) IS NOT NULL
      AND me.event_started_at IS NULL;
    """,
    """
    UPDATE multimodal_signal_windows sw
    SET window_started_at = COALESCE(es.timestamps_reference_at, es.session_started_at)
            + make_interval(secs => sw.window_start_seconds),
        window_ended_at = COALESCE(es.timestamps_reference_at, es.session_started_at)
            + make_interval(secs => sw.window_end_seconds)
    FROM experiment_sessions es
    WHERE sw.session_id = es.id
      AND COALESCE(es.timestamps_reference_at, es.session_started_at) IS NOT NULL
      AND sw.window_started_at IS NULL;
    """,
    "ALTER TABLE neural_signal_summaries DROP CONSTRAINT IF EXISTS neural_signal_summaries_sample_count_check;",
    """
    ALTER TABLE neural_signal_summaries
    ADD CONSTRAINT neural_signal_summaries_sample_count_check
    CHECK (sample_count IS NULL OR sample_count >= 0);
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = 'telemetry'
              AND column_name = 'body_temperature'
        ) THEN
            EXECUTE $migrate$
                INSERT INTO vital_signs (
                    mouse_id, device_id, body_temperature,
                    heart_rate, blood_oxygen, recorded_at, created_at
                )
                SELECT
                    mouse_id, device_id, body_temperature,
                    heart_rate, blood_oxygen, recorded_at, created_at
                FROM telemetry
                WHERE mouse_id IS NOT NULL
                  AND (
                      body_temperature IS NOT NULL
                      OR heart_rate IS NOT NULL
                      OR blood_oxygen IS NOT NULL
                  )
                ON CONFLICT (mouse_id, device_id, recorded_at) DO NOTHING
            $migrate$;
        END IF;
    END $$;
    """,
    "ALTER TABLE telemetry DROP COLUMN IF EXISTS body_temperature;",
    "ALTER TABLE telemetry DROP COLUMN IF EXISTS heart_rate;",
    "ALTER TABLE telemetry DROP COLUMN IF EXISTS blood_oxygen;",
    "ALTER TABLE agent_analysis_results ALTER COLUMN analysis_source SET DEFAULT 'system';",
    "ALTER TABLE agent_analysis_results ADD COLUMN IF NOT EXISTS decision_status VARCHAR(20) NOT NULL DEFAULT 'pending';",
    "ALTER TABLE agent_analysis_results ADD COLUMN IF NOT EXISTS decided_at TIMESTAMP WITH TIME ZONE;",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'agent_analysis_results'::regclass
              AND conname = 'agent_analysis_results_decision_status_check'
        ) THEN
            ALTER TABLE agent_analysis_results
            ADD CONSTRAINT agent_analysis_results_decision_status_check
            CHECK (decision_status IN ('pending', 'confirmed', 'rejected'));
        END IF;
    END $$;
    """,
    "ALTER TABLE stimulation_events ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT FALSE;",
    "ALTER TABLE stimulation_events ADD COLUMN IF NOT EXISTS next_interval_ms INTEGER;",
    "ALTER TABLE stimulation_events ADD COLUMN IF NOT EXISTS next_trigger_at TIMESTAMP WITH TIME ZONE;",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'stimulation_events'::regclass
              AND conname = 'stimulation_events_next_interval_ms_check'
        ) THEN
            ALTER TABLE stimulation_events
            ADD CONSTRAINT stimulation_events_next_interval_ms_check
            CHECK (next_interval_ms IS NULL OR next_interval_ms >= 0);
        END IF;
    END $$;
    """,
    """
    UPDATE animals
    SET experiment_name = '行为无助造模',
        experiment_stage = CASE
            WHEN experiment_stage IN ('给药阶段', '诱导阶段') THEN '应激阶段'
            WHEN experiment_stage IS NULL THEN '准备阶段'
            ELSE experiment_stage
        END,
        updated_at = CURRENT_TIMESTAMP
    WHERE experiment_name IS DISTINCT FROM '行为无助造模'
       OR experiment_stage IN ('给药阶段', '诱导阶段')
       OR experiment_stage IS NULL;
    """,
    "ALTER TABLE animals ALTER COLUMN experiment_name SET DEFAULT '行为无助造模';",
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'animals'::regclass
              AND conname = 'animals_experiment_name_check'
        ) THEN
            ALTER TABLE animals
            ADD CONSTRAINT animals_experiment_name_check
            CHECK (experiment_name IS NULL OR experiment_name = '行为无助造模');
        END IF;
    END $$;
    """,
    """
    DO $$
    DECLARE
        check_name text;
    BEGIN
        FOR check_name IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = 'public'
              AND rel.relname = 'stimulation_events'
              AND con.contype = 'c'
              AND pg_get_constraintdef(con.oid) LIKE '%event_type%'
        LOOP
            EXECUTE format('ALTER TABLE stimulation_events DROP CONSTRAINT IF EXISTS %I', check_name);
        END LOOP;
    END $$;
    """,
    """
    ALTER TABLE stimulation_events
    ADD CONSTRAINT stimulation_events_event_type_check
    CHECK (event_type IN ('electric_shock', 'flash', 'noise'));
    """,
    """
    DO $$
    DECLARE
        check_name text;
    BEGIN
        IF to_regclass('public.control_commands') IS NULL THEN
            RETURN;
        END IF;

        FOR check_name IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = 'public'
              AND rel.relname = 'control_commands'
              AND con.contype = 'c'
              AND pg_get_constraintdef(con.oid) LIKE '%command_type%'
        LOOP
            EXECUTE format('ALTER TABLE control_commands DROP CONSTRAINT IF EXISTS %I', check_name);
        END LOOP;
    END $$;
    """,
    """
    ALTER TABLE control_commands
    ADD CONSTRAINT control_commands_command_type_check
    CHECK (command_type IN ('electric_shock', 'flash', 'noise'));
    """,
]

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_telemetry_mouse_id ON telemetry(mouse_id);",
    "CREATE INDEX IF NOT EXISTS idx_vision_keypoints_mouse_id ON vision_keypoints(mouse_id);",
    "CREATE INDEX IF NOT EXISTS idx_vision_keypoints_frame_index ON vision_keypoints(frame_index);",
    "CREATE INDEX IF NOT EXISTS idx_vision_keypoints_keypoint_name ON vision_keypoints(keypoint_name);",
    "CREATE INDEX IF NOT EXISTS idx_vision_keypoints_recorded_at ON vision_keypoints(recorded_at);",
    "CREATE INDEX IF NOT EXISTS idx_vision_keypoints_mouse_frame ON vision_keypoints(mouse_id, frame_index);",
    "CREATE INDEX IF NOT EXISTS idx_behavior_features_mouse_id ON behavior_frame_features(mouse_id);",
    "CREATE INDEX IF NOT EXISTS idx_behavior_features_frame_index ON behavior_frame_features(frame_index);",
    "CREATE INDEX IF NOT EXISTS idx_behavior_features_recorded_at ON behavior_frame_features(recorded_at);",
    "CREATE INDEX IF NOT EXISTS idx_behavior_features_mouse_frame ON behavior_frame_features(mouse_id, frame_index);",
    "CREATE INDEX IF NOT EXISTS idx_telemetry_device_id ON telemetry(device_id);",
    "CREATE INDEX IF NOT EXISTS idx_telemetry_recorded_at ON telemetry(recorded_at);",
    "CREATE INDEX IF NOT EXISTS idx_telemetry_mouse_recorded_at ON telemetry(mouse_id, recorded_at);",
    "CREATE INDEX IF NOT EXISTS idx_vital_signs_mouse_id ON vital_signs(mouse_id);",
    "CREATE INDEX IF NOT EXISTS idx_vital_signs_device_id ON vital_signs(device_id);",
    "CREATE INDEX IF NOT EXISTS idx_vital_signs_recorded_at ON vital_signs(recorded_at);",
    "CREATE INDEX IF NOT EXISTS idx_vital_signs_mouse_recorded_at ON vital_signs(mouse_id, recorded_at);",
    "CREATE INDEX IF NOT EXISTS idx_stimulation_mouse_id ON stimulation_events(mouse_id);",
    "CREATE INDEX IF NOT EXISTS idx_stimulation_started_at ON stimulation_events(started_at);",
    "CREATE INDEX IF NOT EXISTS idx_stimulation_next_trigger_at ON stimulation_events(next_trigger_at);",
    "CREATE INDEX IF NOT EXISTS idx_stimulation_settings_device_id ON stimulation_settings(device_id);",
    "CREATE INDEX IF NOT EXISTS idx_stimulation_settings_mouse_id ON stimulation_settings(mouse_id);",
    "CREATE INDEX IF NOT EXISTS idx_control_commands_device_id ON control_commands(device_id);",
    "CREATE INDEX IF NOT EXISTS idx_control_commands_status ON control_commands(status);",
    "CREATE INDEX IF NOT EXISTS idx_control_commands_requested_at ON control_commands(requested_at);",
    "CREATE INDEX IF NOT EXISTS idx_control_commands_command_id ON control_commands(command_id);",
    "CREATE INDEX IF NOT EXISTS idx_agent_analysis_mouse_id ON agent_analysis_results(mouse_id);",
    "CREATE INDEX IF NOT EXISTS idx_agent_analysis_analyzed_at ON agent_analysis_results(analyzed_at);",
    "CREATE INDEX IF NOT EXISTS idx_status_history_mouse_id ON animal_status_history(mouse_id);",
    "CREATE INDEX IF NOT EXISTS idx_status_history_recorded_at ON animal_status_history(recorded_at);",
    "CREATE INDEX IF NOT EXISTS idx_dataset_subjects_source ON dataset_subjects(source_id);",
    "CREATE INDEX IF NOT EXISTS idx_experiment_sessions_source ON experiment_sessions(source_id);",
    "CREATE INDEX IF NOT EXISTS idx_experiment_sessions_subject ON experiment_sessions(subject_id);",
    "CREATE INDEX IF NOT EXISTS idx_experiment_sessions_started ON experiment_sessions(session_started_at);",
    "CREATE INDEX IF NOT EXISTS idx_experiment_sessions_stage ON experiment_sessions(modeling_stage);",
    "CREATE INDEX IF NOT EXISTS idx_session_assets_session ON session_assets(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_modeling_events_session_time ON modeling_events(session_id, start_time_seconds);",
    "CREATE INDEX IF NOT EXISTS idx_modeling_events_type ON modeling_events(event_type);",
    "CREATE INDEX IF NOT EXISTS idx_modeling_events_absolute_time ON modeling_events(event_started_at);",
    "CREATE INDEX IF NOT EXISTS idx_multimodal_windows_session_time ON multimodal_signal_windows(session_id, window_start_seconds);",
    "CREATE INDEX IF NOT EXISTS idx_multimodal_windows_modality ON multimodal_signal_windows(modality);",
    "CREATE INDEX IF NOT EXISTS idx_multimodal_windows_absolute_time ON multimodal_signal_windows(window_started_at);",
    "CREATE INDEX IF NOT EXISTS idx_calcium_roi_session ON calcium_roi_metrics(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_behavioral_events_session_time ON behavioral_events(session_id, start_time_seconds);",
    "CREATE INDEX IF NOT EXISTS idx_neural_summaries_session_time ON neural_signal_summaries(session_id, timestamp_seconds);",
    "CREATE INDEX IF NOT EXISTS idx_session_annotations_session ON session_annotations(session_id);",
    "CREATE INDEX IF NOT EXISTS idx_session_agent_analyses_session ON session_agent_analyses(session_id, created_at DESC);",
    "CREATE INDEX IF NOT EXISTS idx_session_agent_analyses_parent ON session_agent_analyses(parent_analysis_id);",
]


def _print_database_hint(exc: Exception) -> None:
    message = str(exc)
    if "does not exist" in message and DB_NAME in message:
        print(f'PostgreSQL database "{DB_NAME}" does not exist.')
        print("Please create it first:")
        print(f'CREATE DATABASE "{DB_NAME}";')
        return

    print("PostgreSQL connection failed.")
    print("Please check that PostgreSQL is running and the database settings are correct.")
    print("error:", message)


def init_database() -> bool:
    connection = None
    cursor = None
    try:
        connection = get_connection(raise_errors=True)
        cursor = connection.cursor()
        for sql in TABLE_SQL:
            cursor.execute(sql)
        for sql in MIGRATION_SQL:
            cursor.execute(sql)
        for sql in INDEX_SQL:
            cursor.execute(sql)
        connection.commit()
        print("database initialized successfully")
        return True
    except DatabaseConnectionError as exc:
        _print_database_hint(exc)
        return False
    except Exception as exc:
        if connection is not None:
            connection.rollback()
        print("database init error:", exc)
        return False
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    sys.exit(0 if init_database() else 1)
