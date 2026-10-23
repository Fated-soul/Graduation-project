from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta
import os
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import remfile

from backend.repositories import public_data_repository


class NWBImportError(RuntimeError):
    pass


_DEFAULT_CACHE_ROOT = Path(__file__).resolve().parents[1] / "cache"
NWB_CACHE_DIR = Path(
    os.getenv("MINGCHA_BACKEND_CACHE_DIR", str(_DEFAULT_CACHE_ROOT))
) / "nwb"


def import_session_content(
    session_pk: int,
    *,
    max_events: int = 2000,
    max_windows: int = 180,
    max_rois: int = 100,
) -> dict[str, Any]:
    """Import compact multimodal evidence from a DANDI 000718 NWB asset."""
    session = public_data_repository.get_session(session_pk)
    if session is None:
        raise LookupError("session not found")
    public_data_repository.set_import_status(session_pk, "importing")
    try:
        NWB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        remote_file = remfile.File(
            str(session["nwb_url"]),
            disk_cache=remfile.DiskCache(str(NWB_CACHE_DIR)),
            _min_chunk_size=512 * 1024,
            _bytes_per_thread=4 * 1024 * 1024,
            _max_threads=2,
            _max_cache_size=512 * 1024 * 1024,
            _size=int(session["nwb_size_bytes"]) if session.get("nwb_size_bytes") else None,
        )
        try:
            with h5py.File(remote_file, mode="r") as nwb:
                timestamps_reference_at = _timestamps_reference_at(nwb, session)
                session_type = str(session.get("session_type") or "")
                events = _read_modeling_events(nwb, max_events, session_type=session_type)
                signal_windows, roi_metrics = _read_signal_evidence(
                    nwb,
                    max_windows=max_windows,
                    max_rois=max_rois,
                    session_type=session_type,
                )
                _attach_absolute_times(
                    events,
                    signal_windows,
                    timestamps_reference_at=timestamps_reference_at,
                )
                duration = _duration(events, signal_windows)
        finally:
            remote_file.close()

        stored = public_data_repository.replace_multimodal_content(
            session_pk,
            modeling_events=events,
            signal_windows=signal_windows,
            roi_metrics=roi_metrics,
            duration_seconds=duration,
            timestamps_reference_at=timestamps_reference_at,
        )
        return {
            "session": stored,
            "modeling_event_count": len(events),
            "signal_window_count": len(signal_windows),
            "calcium_roi_count": len(roi_metrics),
            "duration_seconds": duration,
        }
    except Exception as exc:
        public_data_repository.set_import_status(session_pk, "error", error=str(exc))
        raise NWBImportError(f"NWB content import failed: {exc}") from exc


def _read_modeling_events(
    nwb: h5py.File,
    limit: int,
    *,
    session_type: str = "",
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    groups = _known_interval_groups(nwb, session_type)
    if not groups:
        groups = _groups_with_intervals(nwb)
    for group in groups:
        name = group.name.rsplit("/", 1)[-1]
        lowered = name.lower()
        if "shock" in lowered:
            event_type = "electric_shock"
            default_label = "足底电击"
            preferred_columns = ("shock_amplitude", "amplitude", "intensity")
            unit = "mA"
        elif "freez" in lowered:
            event_type = "freezing"
            default_label = "冻结行为"
            preferred_columns = ("freezing", "value", "confidence")
            unit = None
        elif "sleep" in lowered or "state" in lowered:
            event_type = "sleep_state"
            default_label = "睡眠状态"
            preferred_columns = ("sleep_state", "sleep_stage", "stage", "state", "label", "tags")
            unit = None
        else:
            continue
        remaining = max(0, limit - len(events))
        if remaining == 0:
            break
        events.extend(
            _interval_rows(
                group,
                event_type=event_type,
                default_label=default_label,
                preferred_columns=preferred_columns,
                unit=unit,
                limit=remaining,
            )
        )
    return sorted(events, key=lambda item: (item["start_time_seconds"], item["event_type"]))


def _known_interval_groups(nwb: h5py.File, session_type: str) -> list[h5py.Group]:
    paths = (
        ("processing/sleep/SleepIntervals",)
        if session_type == "offline_consolidation"
        else (
            "stimulus/ShockStimuli",
            "processing/behavior/FreezingIntervals",
        )
    )
    return [nwb[path] for path in paths if path in nwb and isinstance(nwb[path], h5py.Group)]


def _groups_with_intervals(nwb: h5py.File) -> list[h5py.Group]:
    groups: list[h5py.Group] = []

    def visitor(_name: str, value: h5py.Group | h5py.Dataset) -> None:
        if (
            isinstance(value, h5py.Group)
            and "start_time" in value
            and isinstance(value["start_time"], h5py.Dataset)
        ):
            groups.append(value)

    nwb.visititems(visitor)
    return groups


def _interval_rows(
    group: h5py.Group,
    *,
    event_type: str,
    default_label: str,
    preferred_columns: tuple[str, ...],
    unit: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    count = min(len(group["start_time"]), limit)
    if count <= 0:
        return []
    starts = np.asarray(group["start_time"][:count], dtype=float)
    stops = (
        np.asarray(group["stop_time"][:count], dtype=float)
        if "stop_time" in group
        else np.full(count, np.nan)
    )
    columns: dict[str, h5py.Dataset] = {}
    for name, value in group.items():
        dataset: h5py.Dataset | None = None
        if isinstance(value, h5py.Dataset):
            dataset = value
        elif (
            isinstance(value, h5py.Group)
            and "data" in value
            and isinstance(value["data"], h5py.Dataset)
        ):
            dataset = value["data"]
        if dataset is not None and dataset.ndim == 1 and len(dataset) >= count:
            columns[name.lower()] = dataset
    rows: list[dict[str, Any]] = []
    for index, start in enumerate(starts):
        if not np.isfinite(start):
            continue
        label = default_label
        numeric_value: float | None = None
        metadata: dict[str, Any] = {}
        for candidate in preferred_columns:
            dataset = columns.get(candidate.lower())
            if dataset is None:
                continue
            value = _scalar(dataset[index])
            if isinstance(value, str) and value:
                label = _sleep_state_label(value) if event_type == "sleep_state" else f"{default_label}：{value}"
                metadata[candidate] = value
            elif isinstance(value, (int, float)) and np.isfinite(value):
                numeric_value = float(value)
                metadata[candidate] = numeric_value
            break
        stop = float(stops[index]) if np.isfinite(stops[index]) else None
        rows.append(
            {
                "event_type": event_type,
                "event_label": label,
                "start_time_seconds": max(0.0, float(start)),
                "stop_time_seconds": max(float(start), stop) if stop is not None else None,
                "numeric_value": numeric_value,
                "unit": unit,
                "metadata": metadata,
                "source_path": group.name,
            }
        )
    return rows


def _read_signal_evidence(
    nwb: h5py.File,
    *,
    max_windows: int,
    max_rois: int,
    session_type: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: dict[str, list[tuple[int, h5py.Group]]] = {
        "calcium": [], "motion": [], "eeg": [], "emg": [],
    }

    def visitor(_name: str, value: h5py.Group | h5py.Dataset) -> None:
        if not isinstance(value, h5py.Group) or "data" not in value:
            return
        dataset = value["data"]
        if not isinstance(dataset, h5py.Dataset) or dataset.ndim not in {1, 2}:
            return
        modality, score = _classify_timeseries(value)
        if modality:
            candidates[modality].append((score, value))

    direct_paths = (
        (
            "acquisition/EEGSignal",
            "acquisition/EMGSignal",
            "acquisition/ActivitySignal",
            "processing/ophys/Fluorescence/Deconvolved",
        )
        if session_type == "offline_consolidation"
        else (
            "processing/behavior/MotionSeries",
            "processing/ophys/Fluorescence/Deconvolved",
        )
    )
    for path in direct_paths:
        if path in nwb:
            visitor(path, nwb[path])
    if not candidates["calcium"] and "processing/ophys" in nwb:
        nwb["processing/ophys"].visititems(visitor)
    if session_type == "offline_consolidation":
        for modality, path in (("eeg", "acquisition/EEGSignal"), ("emg", "acquisition/EMGSignal")):
            if not candidates[modality] and path in nwb:
                visitor(path, nwb[path])
    elif not candidates["motion"] and "processing/behavior" in nwb:
        nwb["processing/behavior"].visititems(visitor)
    windows: list[dict[str, Any]] = []
    roi_metrics: list[dict[str, Any]] = []
    labels = {
        "calcium": "群体钙活动",
        "motion": "运动强度",
        "eeg": "脑电均方根幅值",
        "emg": "肌电均方根幅值",
    }
    for modality, matches in candidates.items():
        if not matches:
            continue
        _, group = max(matches, key=lambda item: item[0])
        signal_name = labels[modality]
        unit = _timeseries_unit(group, "a.u.")
        windows.extend(
            _summarize_timeseries(
                group,
                modality=modality,
                signal_name=signal_name,
                unit=unit,
                max_windows=max_windows,
            )
        )
        if modality == "calcium":
            roi_metrics = _calcium_roi_metrics(group, max_rois=max_rois)
    return windows, roi_metrics


def _classify_timeseries(group: h5py.Group) -> tuple[str | None, int]:
    path = group.name.lower()
    basename = group.name.rsplit("/", 1)[-1].lower()
    if "emg" in path:
        return "emg", 100
    if "eeg" in path or "electroencephal" in path:
        return "eeg", 100
    if "motion" in path or "activitysignal" in path:
        return "motion", 100
    if "/processing/ophys/" in path:
        score = 20
        if "roiresponseseries" in path:
            score += 80
        if "fluorescence" in path or "dfoverf" in path:
            score += 50
        if basename in {"c", "s", "calcium", "deconvolved"}:
            score += 35
        return "calcium", score
    return None, 0


def _summarize_timeseries(
    group: h5py.Group,
    *,
    modality: str,
    signal_name: str,
    unit: str,
    max_windows: int,
) -> list[dict[str, Any]]:
    dataset = group["data"]
    time_axis = _time_axis(group, dataset)
    sample_count = int(dataset.shape[time_axis])
    if sample_count <= 0:
        return []
    start_time, end_time = _time_bounds(group, sample_count)
    window_count = min(max_windows, sample_count)
    edges = np.linspace(0, sample_count, window_count + 1, dtype=int)
    time_edges = np.linspace(start_time, end_time, window_count + 1)
    rows: list[dict[str, Any]] = []
    dense_values: np.ndarray | None = None
    if dataset.ndim == 1 and sample_count <= 2_000_000:
        dense_values = np.asarray(dataset[:], dtype=float)
    for index in range(window_count):
        left = int(edges[index])
        right = max(left + 1, int(edges[index + 1]))
        if dense_values is not None:
            values = dense_values[left:right]
            aggregation = "complete_window"
        else:
            indices = np.linspace(left, right - 1, min(32, right - left), dtype=int)
            values = _sample_dataset(dataset, indices, time_axis=time_axis, max_channels=64)
            aggregation = "representative_samples"
        values = values[np.isfinite(values)]
        if values.size == 0:
            continue
        mean_value = (
            float(np.sqrt(np.mean(np.square(values))))
            if modality in {"eeg", "emg"}
            else float(np.mean(values))
        )
        rows.append(
            {
                "modality": modality,
                "signal_name": signal_name,
                "channel_name": group.name.rsplit("/", 1)[-1],
                "window_start_seconds": max(0.0, float(time_edges[index])),
                "window_end_seconds": max(0.0, float(time_edges[index + 1])),
                "mean_value": mean_value,
                "min_value": float(np.min(values)),
                "max_value": float(np.max(values)),
                "std_value": float(np.std(values)),
                "unit": unit,
                "sample_count": int(values.size),
                "metadata": {
                    "aggregation": aggregation,
                    "time_reference": "session_start",
                },
                "source_path": f"{group.name}/data",
            }
        )
    return rows


def _calcium_roi_metrics(group: h5py.Group, *, max_rois: int) -> list[dict[str, Any]]:
    dataset = group["data"]
    if dataset.ndim != 2:
        return []
    time_axis = _time_axis(group, dataset)
    roi_count = min(int(dataset.shape[1 - time_axis]), max_rois)
    time_count = int(dataset.shape[time_axis])
    if roi_count <= 0 or time_count <= 0:
        return []
    indices = np.linspace(0, time_count - 1, min(2048, time_count), dtype=int)
    values = _sample_dataset(dataset, indices, time_axis=time_axis, max_channels=roi_count)
    if time_axis == 1:
        values = values.T
    if values.ndim == 1:
        values = values[:, None]
    metrics: list[dict[str, Any]] = []
    for roi_index in range(min(roi_count, values.shape[1])):
        series = np.asarray(values[:, roi_index], dtype=float)
        series = series[np.isfinite(series)]
        if series.size == 0:
            continue
        threshold = float(np.mean(series) + np.std(series))
        metrics.append(
            {
                "roi_index": roi_index,
                "mean_activity": float(np.mean(series)),
                "peak_activity": float(np.max(series)),
                "activity_std": float(np.std(series)),
                "active_fraction": float(np.mean(series > threshold)),
                "sample_count": int(series.size),
                "metadata": {"threshold": "mean_plus_one_std"},
                "source_path": f"{group.name}/data",
            }
        )
    return metrics


def _sample_dataset(
    dataset: h5py.Dataset,
    indices: np.ndarray,
    *,
    time_axis: int,
    max_channels: int,
) -> np.ndarray:
    if dataset.ndim == 1:
        return np.asarray(dataset[indices], dtype=float)
    if time_axis == 0:
        return np.asarray(dataset[indices, :max_channels], dtype=float)
    return np.asarray(dataset[:max_channels, indices], dtype=float)


def _time_axis(group: h5py.Group, dataset: h5py.Dataset) -> int:
    if dataset.ndim == 1:
        return 0
    if "timestamps" in group and isinstance(group["timestamps"], h5py.Dataset):
        timestamp_count = len(group["timestamps"])
        if dataset.shape[1] == timestamp_count and dataset.shape[0] != timestamp_count:
            return 1
    return 0


def _time_bounds(group: h5py.Group, sample_count: int) -> tuple[float, float]:
    if "timestamps" in group and len(group["timestamps"]) > 0:
        timestamps = group["timestamps"]
        start = float(timestamps[0])
        end = float(timestamps[min(len(timestamps), sample_count) - 1])
        if np.isfinite(start) and np.isfinite(end) and end >= start:
            return max(0.0, start), max(0.0, end)
    if "starting_time" in group:
        starting_time = group["starting_time"]
        start = float(np.asarray(starting_time[()]).reshape(-1)[0])
        rate = float(starting_time.attrs.get("rate", 1.0) or 1.0)
        if rate > 0:
            return max(0.0, start), max(0.0, start + (sample_count - 1) / rate)
    return 0.0, float(max(0, sample_count - 1))


def _duration(
    events: Iterable[dict[str, Any]],
    signal_windows: Iterable[dict[str, Any]],
) -> float | None:
    values = [
        float(item.get("stop_time_seconds") or item["start_time_seconds"])
        for item in events
    ]
    values.extend(float(item["window_end_seconds"]) for item in signal_windows)
    return max(values) if values else None


def _timestamps_reference_at(nwb: h5py.File, session: dict[str, Any]) -> datetime:
    value: Any = None
    if "timestamps_reference_time" in nwb:
        value = _scalar(np.asarray(nwb["timestamps_reference_time"][()]).reshape(-1)[0])
    elif "session_start_time" in nwb:
        value = _scalar(np.asarray(nwb["session_start_time"][()]).reshape(-1)[0])
    parsed = _parse_datetime(value)
    if parsed is not None:
        return parsed
    started_at = session.get("timestamps_reference_at") or session.get("session_started_at")
    if isinstance(started_at, datetime):
        return started_at
    parsed = _parse_datetime(started_at)
    if parsed is None:
        raise NWBImportError("session has no usable timestamp reference")
    return parsed


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _attach_absolute_times(
    events: list[dict[str, Any]],
    signal_windows: list[dict[str, Any]],
    *,
    timestamps_reference_at: datetime,
) -> None:
    for item in events:
        item["event_started_at"] = timestamps_reference_at + timedelta(
            seconds=float(item["start_time_seconds"])
        )
        stop = item.get("stop_time_seconds")
        item["event_stopped_at"] = (
            timestamps_reference_at + timedelta(seconds=float(stop))
            if stop is not None
            else None
        )
        item.setdefault("metadata", {})["time_reference"] = "session_start"
    for item in signal_windows:
        item["window_started_at"] = timestamps_reference_at + timedelta(
            seconds=float(item["window_start_seconds"])
        )
        item["window_ended_at"] = timestamps_reference_at + timedelta(
            seconds=float(item["window_end_seconds"])
        )
        item.setdefault("metadata", {})["time_reference"] = "session_start"


def _timeseries_unit(group: h5py.Group, fallback: str) -> str:
    value = group.attrs.get("unit")
    if value is None and "data" in group and isinstance(group["data"], h5py.Dataset):
        value = group["data"].attrs.get("unit")
    if value is None and "unit" in group and isinstance(group["unit"], h5py.Dataset):
        value = group["unit"][()]
    if value is None:
        return fallback
    text = str(_scalar(value)).strip()
    return text if text else fallback


def _sleep_state_label(value: str) -> str:
    normalized = value.strip().lower().replace("_", " ")
    labels = {
        "wake": "清醒",
        "quiet wake": "安静清醒",
        "active wake": "活动清醒",
        "nrem": "非快速眼动睡眠",
        "nrem sleep": "非快速眼动睡眠",
        "rem": "快速眼动睡眠",
        "rem sleep": "快速眼动睡眠",
        "sleep": "睡眠",
    }
    return labels.get(normalized, f"睡眠状态：{value}")


def _scalar(value: Any) -> str | int | float:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (int, float, str)):
        return value
    return str(value)
