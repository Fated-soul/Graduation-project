from __future__ import annotations

from collections import Counter, defaultdict
from math import isfinite
from typing import Any


def compact_dataset_context(context: dict[str, Any]) -> dict[str, Any]:
    """Keep bounded detail across the full session, with uncropped statistics."""
    events = context.get("modeling_events") or []
    signals = context.get("signal_windows") or []
    selected_signals = _sample_across_time(
        signals, 360, ("modality", "signal_name", "channel_name", "unit"), "window_start_seconds",
    )
    compact = {
        "session": context.get("session"),
        "modeling_events": _sample_across_time(events, 180, ("event_type",), "start_time_seconds"),
        "signal_windows": selected_signals,
        "signal_summary": _signal_summary(signals, selected_signals),
        "modeling_event_summary": _event_summary(events),
        "roi_metrics": (context.get("roi_metrics") or [])[:100],
        "annotations": (context.get("annotations") or [])[-100:],
        "related_sessions": (context.get("related_sessions") or [])[:40],
        "cross_session_events": _sample_across_time(
            context.get("cross_session_events") or [], 240,
            ("session_id", "event_type"), "start_time_seconds",
        ),
        "cross_session_signal_summary": (context.get("cross_session_signal_summary") or [])[:80],
        "absolute_alignment": context.get("absolute_alignment") or {},
    }
    sampled = {"modeling_events", "signal_windows", "cross_session_events"}
    compact["evidence_coverage"] = {
        name: {
            "available_count": len(context.get(name) or []),
            "supplied_count": len(compact[name]),
            "is_reduced": len(compact[name]) < len(context.get(name) or []),
            "selection": (
                "all" if len(compact[name]) == len(context.get(name) or [])
                else "stratified_full_time_sample" if name in sampled
                else "last_records" if name == "annotations" else "first_records"
            ),
        }
        for name in (
            "modeling_events", "signal_windows", "roi_metrics", "annotations",
            "related_sessions", "cross_session_events", "cross_session_signal_summary",
        )
    }
    return compact


def _group_key(row: dict[str, Any], fields: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in fields)


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _sample_across_time(
    rows: list[dict[str, Any]], limit: int,
    group_fields: tuple[str, ...], time_field: str,
) -> list[dict[str, Any]]:
    if len(rows) <= limit:
        return list(rows)
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_group_key(row, group_fields)].append(row)
    ordered = [
        sorted(items, key=lambda row: _finite_number(row.get(time_field)) or 0.0)
        for _, items in sorted(groups.items())
    ]
    quotas = [0] * len(ordered)
    # Share the budget across channels before sampling each channel's full span.
    remaining = limit
    while remaining:
        for index, items in enumerate(ordered):
            if quotas[index] < len(items):
                quotas[index] += 1
                remaining -= 1
                if not remaining:
                    break
    selected: list[dict[str, Any]] = []
    for items, count in zip(ordered, quotas, strict=True):
        if count == 1:
            selected.append(items[len(items) // 2])
        elif count > 1:
            selected.extend(items[index * (len(items) - 1) // (count - 1)] for index in range(count))
    return sorted(selected, key=lambda row: _finite_number(row.get(time_field)) or 0.0)


def _signal_summary(
    rows: list[dict[str, Any]], selected: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    fields = ("modality", "signal_name", "channel_name", "unit")
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    selected_counts = Counter(_group_key(row, fields) for row in selected)
    for row in rows:
        groups[_group_key(row, fields)].append(row)
    summaries = []
    for key, items in sorted(groups.items()):
        def values(field: str) -> list[float]:
            return [value for row in items if (value := _finite_number(row.get(field))) is not None]

        means = values("mean_value")
        minima = values("min_value")
        maxima = values("max_value")
        starts = values("window_start_seconds")
        ends = values("window_end_seconds")
        summaries.append({
            **dict(zip(fields, key, strict=True)),
            "window_count": len(items),
            "supplied_window_count": selected_counts[key],
            "first_window_start_seconds": min(starts) if starts else None,
            "last_window_end_seconds": max(ends) if ends else None,
            "mean_of_window_means": sum(means) / len(means) if means else None,
            "minimum_window_mean": min(means) if means else None,
            "maximum_window_mean": max(means) if means else None,
            "minimum_recorded_sample_value": min(minima) if minima else None,
            "maximum_recorded_sample_value": max(maxima) if maxima else None,
        })
    return summaries


def _event_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get("event_type") or "unknown")].append(row)
    return [{
        "event_type": kind, "event_count": len(items),
        "sum_interval_seconds": sum(
            max(0.0, (_finite_number(row.get("stop_time_seconds")) or 0.0)
                - (_finite_number(row.get("start_time_seconds")) or 0.0))
            for row in items
        ),
    } for kind, items in sorted(groups.items())]
