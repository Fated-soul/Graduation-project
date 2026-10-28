from __future__ import annotations

from datetime import datetime, timedelta
import json
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from components.metric_card import render_section_title
from components.synchronized_player import render_synchronized_player
from data.public_dataset import (
    add_annotation,
    delete_annotation,
    format_datetime,
    get_aligned_subject_timeline,
    get_session,
    get_session_analyses,
    get_sessions,
    get_subjects,
    get_timeline,
    import_session_content,
    session_video_url,
)


SESSION_TYPE_LABELS = {
    "neutral_exposure": "基线适应",
    "fear_conditioning": "恐惧条件化（FC）",
    "offline_consolidation": "离线巩固（Offline）",
    "recall_assessment": "记忆回忆评估",
    "longitudinal_followup": "跨周随访",
    "other": "其他研究会话",
}
MODALITY_LABELS = {
    "calcium": "钙活动",
    "motion": "运动强度",
    "eeg": "脑电",
    "emg": "肌电",
}
MODALITY_COLORS = {
    "calcium": "#7656c7",
    "motion": "#1688c4",
    "eeg": "#169b6b",
    "emg": "#d27b19",
}
SIGNAL_UNIT_LABELS = {
    "v": "V",
    "volt": "V",
    "volts": "V",
    "mv": "mV",
    "millivolt": "mV",
    "millivolts": "mV",
    "uv": "μV",
    "μv": "μV",
    "microvolt": "μV",
    "microvolts": "μV",
    "hz": "Hz",
}
ARBITRARY_UNIT_VALUES = {
    "",
    "a.u",
    "a.u.",
    "au",
    "arbitrary unit",
    "arbitrary units",
    "dimensionless",
    "n.a",
    "n.a.",
    "n/a",
    "na",
    "none",
    "unitless",
}
SESSION_TYPE_COLORS = {
    "neutral_exposure": "#2c9f8f",
    "fear_conditioning": "#1688c4",
    "offline_consolidation": "#7656c7",
    "recall_assessment": "#d27b19",
    "longitudinal_followup": "#6b7f91",
    "other": "#5f788f",
}
SESSION_EVIDENCE = {
    "neutral_exposure": "适应期行为视频、活动、冻结基线和钙活动",
    "fear_conditioning": "足底电击、行为视频、冻结行为和钙活动",
    "offline_consolidation": "睡眠状态、脑电、肌电和钙活动",
    "recall_assessment": "回忆期行为视频、冻结行为、活动和钙活动",
    "longitudinal_followup": "跨时段行为与神经活动变化",
    "other": "本场会话已记录的行为、事件和神经活动",
}


def render() -> None:
    subjects = get_subjects()
    if not subjects:
        st.info("尚未同步公开研究目录。")
        return

    subject_ids = [str(item["subject_id"]) for item in subjects]
    if st.session_state.get("review_subject_id") not in subject_ids:
        st.session_state.review_subject_id = subject_ids[0]
    subject_id = st.selectbox(
        "实验动物",
        subject_ids,
        key="review_subject_id",
    )
    sessions = get_sessions(subject_id=subject_id, limit=300)
    if not sessions:
        st.info("该实验动物暂无可复核会话。")
        return

    aligned = get_aligned_subject_timeline(subject_id)
    render_section_title(
        "纵向多模态复核",
        "按真实采集时间浏览基线、造模、离线巩固、记忆回忆与随访证据",
    )
    selected_id = _session_select("复核会话", sessions, "review_primary_session")
    selected_session = get_session(selected_id) or {}
    _render_session_overview(selected_session)
    _render_absolute_timeline(
        aligned,
        {int(item["id"]) for item in sessions},
        chart_key="review_all_sessions_timeline",
    )
    st.caption(
        "会话节点按采集先后等距排布，节点下方是实际采集时刻，连线标注真实间隔。"
        "等距排布仅用于清晰展示研究流程，不表示这些会话是连续采集。"
    )
    _render_session_detail(selected_session, key_prefix=f"session_{selected_id}")


def _session_select(label: str, sessions: list[dict[str, Any]], key: str) -> int:
    options = [int(item["id"]) for item in sessions]
    labels = {
        int(item["id"]): (
            f"{item.get('modeling_stage') or SESSION_TYPE_LABELS.get(str(item.get('session_type')), '研究会话')}"
            f" · {format_datetime(item.get('session_started_at'))}"
        )
        for item in sessions
    }
    ready = next(
        (int(item["id"]) for item in sessions if item.get("import_status") == "ready"),
        options[0],
    )
    stored = st.session_state.get(key)
    try:
        preferred = int(stored)
    except (TypeError, ValueError):
        preferred = ready
    if preferred not in options:
        preferred = ready
    if st.session_state.get(key) != preferred:
        st.session_state[key] = preferred
    return int(
        st.selectbox(
            label,
            options,
            format_func=lambda value: labels[value],
            key=key,
        )
    )


def _render_session_overview(session: dict[str, Any]) -> None:
    session_type = str(session.get("session_type") or "other")
    start, end = _session_bounds(session)
    columns = st.columns(4)
    columns[0].metric("研究阶段", SESSION_TYPE_LABELS.get(session_type, "研究会话"))
    columns[1].metric("采集日期", start.strftime("%Y-%m-%d") if start else "未记录")
    columns[2].metric("采集时段", _clock_range(start, end))
    columns[3].metric("证据状态", "已载入" if session.get("import_status") == "ready" else "待载入")


def _render_absolute_timeline(
    aligned: dict[str, Any],
    selected_ids: set[int],
    *,
    chart_key: str,
) -> None:
    sessions = [
        item
        for item in aligned.get("sessions", [])
        if int(item["id"]) in selected_ids
    ]
    points: list[tuple[dict[str, Any], datetime, datetime | None]] = []
    for session in sessions:
        start = _parse_datetime(
            session.get("timeline_origin_at") or session.get("session_started_at")
        )
        if start is None:
            continue
        end = _parse_datetime(session.get("session_ended_at"))
        points.append((session, start, end))
    points.sort(key=lambda item: item[1])

    if not points:
        st.info("当前没有可绘制的真实时间记录。")
        return

    positions = list(range(len(points)))
    labels = [
        SESSION_TYPE_LABELS.get(str(session.get("session_type") or "other"), "研究会话")
        for session, _, _ in points
    ]
    colors = [
        SESSION_TYPE_COLORS.get(str(session.get("session_type") or "other"), "#5f788f")
        for session, _, _ in points
    ]
    status_labels = [
        "已载入" if session.get("import_status") == "ready" else "待载入"
        for session, _, _ in points
    ]
    custom_data = [
        [
            _format_absolute(start),
            _clock_range(start, end),
            _format_gap(end - start) if end else "时长未记录",
            status,
        ]
        for (_, start, end), status in zip(points, status_labels, strict=True)
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=positions,
            y=[0] * len(points),
            mode="lines+markers+text",
            line={"color": "#c9d8e2", "width": 4},
            marker={
                "size": 22,
                "color": colors,
                "line": {"color": "#ffffff", "width": 3},
            },
            text=labels,
            textposition="top center",
            textfont={"size": 13, "color": "#243b53"},
            customdata=custom_data,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "采集开始：%{customdata[0]}<br>"
                "采集时段：%{customdata[1]}<br>"
                "记录时长：%{customdata[2]}<br>"
                "证据状态：%{customdata[3]}<extra></extra>"
            ),
            showlegend=False,
        )
    )

    for index in range(1, len(points)):
        previous_end = points[index - 1][2] or points[index - 1][1]
        current_start = points[index][1]
        relationship = (
            f"间隔 {_format_gap(current_start - previous_end)}"
            if current_start >= previous_end
            else "采集时间重叠"
        )
        fig.add_annotation(
            x=index - 0.5,
            y=-0.22,
            text=relationship,
            showarrow=False,
            font={"size": 11, "color": "#60758a"},
            bgcolor="#f1f6f9",
            bordercolor="#dbe7ee",
            borderpad=4,
        )

    fig.update_layout(
        height=320,
        margin={"l": 35, "r": 35, "t": 65, "b": 55},
        plot_bgcolor="#f8fbfd",
        paper_bgcolor="rgba(0,0,0,0)",
        hovermode="closest",
    )
    fig.update_xaxes(
        title="采集先后顺序",
        tickmode="array",
        tickvals=positions,
        ticktext=[f"{start:%m-%d}<br>{start:%H:%M}" for _, start, _ in points],
        range=[-0.45, max(0.45, len(points) - 0.55)],
        fixedrange=True,
        showgrid=False,
        zeroline=False,
    )
    fig.update_yaxes(
        range=[-0.48, 0.52],
        fixedrange=True,
        visible=False,
    )
    st.plotly_chart(
        fig,
        width="stretch",
        config={"displayModeBar": False, "scrollZoom": False},
        key=chart_key,
    )


def _render_session_detail(session: dict[str, Any], *, key_prefix: str) -> None:
    session_id = int(session["id"])
    session_type = str(session.get("session_type") or "")
    is_offline = session_type == "offline_consolidation"
    expected = SESSION_EVIDENCE.get(session_type, SESSION_EVIDENCE["other"])

    st.markdown(f"#### {SESSION_TYPE_LABELS.get(session_type, '研究会话')}")
    st.caption(
        f"采集开始：{_format_absolute(_parse_datetime(session.get('timestamps_reference_at') or session.get('session_started_at')))} · "
        f"本视图用于复核{expected}"
    )
    if session.get("import_status") != "ready":
        with st.container(border=True):
            st.write(f"该会话目录已找到，载入后可查看{expected}。")
            if st.button("载入该会话证据", type="primary", key=f"{key_prefix}_import", width="stretch"):
                with st.spinner("正在从 DANDI 读取 NWB 证据，这可能需要几分钟……"):
                    response = import_session_content(session_id)
                if response.get("success") is False:
                    st.error(str(response.get("message") or "载入失败。"))
                else:
                    st.success("会话证据已载入。")
                    st.rerun()
        return

    timeline = get_timeline(session_id)
    events = timeline["modeling_events"]
    signals = timeline["signal_windows"]
    analyses = get_session_analyses(session_id)

    metrics = st.columns(4)
    if is_offline:
        metrics[0].metric("睡眠片段", sum(item.get("event_type") == "sleep_state" for item in events))
        metrics[1].metric("脑电时间窗", sum(item.get("modality") == "eeg" for item in signals))
        metrics[2].metric("肌电时间窗", sum(item.get("modality") == "emg" for item in signals))
        metrics[3].metric("钙活动时间窗", sum(item.get("modality") == "calcium" for item in signals))
    elif session_type == "fear_conditioning":
        metrics[0].metric("电击记录", sum(item.get("event_type") == "electric_shock" for item in events))
        metrics[1].metric("冻结片段", sum(item.get("event_type") == "freezing" for item in events))
        metrics[2].metric("钙活动时间窗", sum(item.get("modality") == "calcium" for item in signals))
        metrics[3].metric("人工复核", len(timeline["annotations"]))
    else:
        metrics[0].metric("行为片段", sum(item.get("event_type") in {"freezing", "behavior_state"} for item in events))
        metrics[1].metric("运动时间窗", sum(item.get("modality") == "motion" for item in signals))
        metrics[2].metric("钙活动时间窗", sum(item.get("modality") == "calcium" for item in signals))
        metrics[3].metric("人工复核", len(timeline["annotations"]))

    _render_review_workspace(
        session_id=session_id,
        session=session,
        session_type=session_type,
        events=events,
        signals=signals,
        annotations=timeline["annotations"],
        analyses=analyses,
        key_prefix=key_prefix,
    )

    _render_annotation_records(
        session_id,
        timeline["annotations"],
        key_prefix=key_prefix,
    )
    _render_signal_charts(session, events, signals)
    st.download_button(
        "导出本场会话证据",
        data=json.dumps(
            {"会话信息": session, "事件": events, "信号摘要": signals, "人工复核": timeline["annotations"]},
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        file_name=f"{session.get('subject_code', 'animal')}_{SESSION_TYPE_LABELS.get(session_type, '研究会话')}.json",
        mime="application/json",
        key=f"{key_prefix}_export",
        width="stretch",
    )


@st.fragment
def _render_review_workspace(
    *,
    session_id: int,
    session: dict[str, Any],
    session_type: str,
    events: list[dict[str, Any]],
    signals: list[dict[str, Any]],
    annotations: list[dict[str, Any]],
    analyses: list[dict[str, Any]],
    key_prefix: str,
) -> None:
    duration = max(0.0, float(session.get("duration_seconds") or 0))
    timestamp_key = f"{key_prefix}_annotation_time"
    st.session_state.setdefault(timestamp_key, 0.0)

    viewer, review_panel = st.columns([1.65, 0.85], gap="large")
    with viewer:
        selected_time = render_synchronized_player(
            video_url=session_video_url(session_id) if session.get("has_video") else None,
            duration_seconds=session.get("duration_seconds"),
            modeling_events=events,
            signal_windows=signals,
            annotations=annotations,
            session_type=session_type,
            compact=True,
            key=f"{key_prefix}_synchronized_player",
        )
        _sync_annotation_time(
            timestamp_key,
            selected_time,
            duration_seconds=duration if duration > 0 else None,
        )
    with review_panel:
        render_section_title("人工复核", "记录目标时间位置的观察结论")
        with st.form(f"{key_prefix}_annotation_form"):
            timestamp = st.number_input(
                "复核时间点（秒）",
                min_value=0.0,
                max_value=duration if duration > 0 else None,
                step=0.1,
                format="%.1f",
                key=timestamp_key,
            )
            st.caption("播放时自动跟随；暂停、拖动进度或点击时间轴后立即同步，也可手动微调。")
            choices = _annotation_choices(session_type)
            category = st.selectbox(
                "观察类别",
                choices,
                key=f"{key_prefix}_annotation_category",
            )
            note = st.text_area(
                "复核结论",
                height=120,
                key=f"{key_prefix}_annotation_note",
            )
            submitted = st.form_submit_button(
                "保存复核记录",
                type="primary",
                width="stretch",
            )
        if submitted:
            if not note.strip():
                st.warning("请先填写复核结论。")
            else:
                response = add_annotation(
                    session_id,
                    timestamp_seconds=float(timestamp),
                    category=category,
                    note=note.strip(),
                )
                if response.get("success") is False:
                    st.error(str(response.get("message") or "保存失败。"))
                else:
                    st.toast("复核记录已保存。", icon=":material/check_circle:")
                    st.rerun()
        if analyses:
            with st.expander("最近一次 Agent 评估"):
                st.write(analyses[0].get("summary") or "")


def _render_annotation_records(
    session_id: int,
    annotations: list[dict[str, Any]],
    *,
    key_prefix: str,
) -> None:
    render_section_title(
        "复核记录",
        "按会话时间整理已保存的人工观察，可删除误录或不再采用的结论",
    )
    records = _sorted_annotations(annotations)
    if not records:
        st.info("当前会话还没有人工复核记录。")
        return

    for index, record in enumerate(records):
        annotation_id = record.get("id")
        with st.container(border=True):
            content, action = st.columns([8, 1.35], gap="medium", vertical_alignment="top")
            with content:
                category = str(record.get("category") or "观察记录")
                position = _format_session_offset(record.get("timestamp_seconds"))
                st.markdown(f"**{category}** · 会话位置 {position}")
                st.write(str(record.get("note") or "未填写复核结论"))
                author = str(record.get("created_by") or "实验人员")
                created_at = format_datetime(record.get("created_at"))
                st.caption(f"记录人：{author} · 记录时间：{created_at}")
            with action:
                if annotation_id is None:
                    st.button(
                        "删除",
                        icon=":material/delete:",
                        key=f"{key_prefix}_annotation_delete_unavailable_{index}",
                        disabled=True,
                        width="stretch",
                    )
                    continue
                with st.popover(
                    "删除",
                    icon=":material/delete:",
                    width="stretch",
                ):
                    st.write("确认删除这条复核记录？删除后无法恢复。")
                    if st.button(
                        "确认删除",
                        type="primary",
                        key=f"{key_prefix}_annotation_delete_{annotation_id}",
                        width="stretch",
                    ):
                        response = delete_annotation(session_id, int(annotation_id))
                        if response.get("success") is False:
                            st.error(str(response.get("message") or "删除失败。"))
                        else:
                            st.toast("复核记录已删除。", icon=":material/check_circle:")
                            st.rerun()


def _sync_annotation_time(
    timestamp_key: str,
    selected_time: Any,
    *,
    duration_seconds: float | None,
) -> None:
    normalized = _normalize_video_time(selected_time, duration_seconds)
    if normalized is None:
        return
    marker_key = f"{timestamp_key}_last_player_value"
    previous = st.session_state.get(marker_key)
    if previous is not None and abs(float(previous) - normalized) < 0.05:
        return
    st.session_state[timestamp_key] = normalized
    st.session_state[marker_key] = normalized


def _normalize_video_time(value: Any, duration_seconds: float | None) -> float | None:
    try:
        seconds = max(0.0, float(value))
    except (TypeError, ValueError):
        return None
    if duration_seconds is not None:
        seconds = min(seconds, max(0.0, float(duration_seconds)))
    return round(seconds, 1)


def _sorted_annotations(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def sort_key(item: dict[str, Any]) -> tuple[float, str, int]:
        timestamp = item.get("timestamp_seconds")
        try:
            position = float(timestamp)
        except (TypeError, ValueError):
            position = float("inf")
        created_at = str(item.get("created_at") or "")
        try:
            annotation_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            annotation_id = 0
        return position, created_at, annotation_id

    return sorted(annotations, key=sort_key)


def _format_session_offset(value: Any) -> str:
    try:
        seconds = max(0.0, float(value))
    except (TypeError, ValueError):
        return "未定位"
    minutes, remaining = divmod(seconds, 60)
    hours, minutes = divmod(int(minutes), 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{remaining:04.1f}"
    return f"{minutes:02d}:{remaining:04.1f}"


def _signal_axis_label(
    modality: str,
    points: list[dict[str, Any]],
) -> tuple[str, str]:
    signal_name = next(
        (str(item.get("signal_name")).strip() for item in points if item.get("signal_name")),
        MODALITY_LABELS.get(modality, modality),
    )
    raw_unit = next(
        (str(item.get("unit")).strip() for item in points if item.get("unit") is not None),
        "",
    )
    unit_label = _display_signal_unit(raw_unit)
    return f"{signal_name}（{unit_label}）", unit_label


def _display_signal_unit(value: Any) -> str:
    raw = str(value or "").strip()
    normalized = raw.lower().replace("μ", "u").replace("µ", "u")
    if normalized in ARBITRARY_UNIT_VALUES:
        return "a.u."
    return SIGNAL_UNIT_LABELS.get(normalized, raw)


def _render_signal_charts(
    session: dict[str, Any],
    events: list[dict[str, Any]],
    signals: list[dict[str, Any]],
) -> None:
    available = [name for name in ("calcium", "motion", "eeg", "emg") if any(item.get("modality") == name for item in signals)]
    if available:
        render_section_title("信号变化", "按本场会话的真实采集时刻展示各类信号摘要")
        fig = make_subplots(rows=len(available), cols=1, shared_xaxes=True, vertical_spacing=0.08)
        reference = _parse_datetime(session.get("timestamps_reference_at") or session.get("session_started_at"))
        uses_arbitrary_units = False
        for row, modality in enumerate(available, start=1):
            points = [item for item in signals if item.get("modality") == modality]
            axis_label, unit_label = _signal_axis_label(modality, points)
            uses_arbitrary_units = uses_arbitrary_units or unit_label == "a.u."
            x_values = [
                _parse_datetime(item.get("window_started_at"))
                or (reference + timedelta(seconds=float(item.get("window_start_seconds") or 0)) if reference else None)
                for item in points
            ]
            fig.add_trace(
                go.Scatter(
                    x=x_values,
                    y=[item.get("mean_value") for item in points],
                    mode="lines",
                    line={"color": MODALITY_COLORS[modality], "width": 2},
                    name=axis_label,
                    hovertemplate=(
                        f"%{{x|%H:%M:%S}}<br>{axis_label}：%{{y:.4g}}<extra></extra>"
                    ),
                ),
                row=row,
                col=1,
            )
            fig.update_yaxes(title_text=axis_label, fixedrange=True, row=row, col=1)
        fig.update_xaxes(title_text="真实采集时间", fixedrange=True, row=len(available), col=1)
        fig.update_layout(
            height=max(270, 180 * len(available)),
            margin={"l": 20, "r": 20, "t": 15, "b": 35},
            showlegend=False,
            plot_bgcolor="#f8fbfd",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False, "scrollZoom": False})
        if uses_arbitrary_units:
            st.caption(
                "a.u. 表示任意单位；公开数据未提供可换算的物理量纲时，"
                "图中保留原始相对信号幅值，不额外推断单位。"
            )

    sleep_events = [item for item in events if item.get("event_type") == "sleep_state"]
    if sleep_events:
        totals: dict[str, float] = {}
        for item in sleep_events:
            label = str(item.get("event_label") or "未分类")
            duration = max(0.0, float(item.get("stop_time_seconds") or 0) - float(item.get("start_time_seconds") or 0))
            totals[label] = totals.get(label, 0.0) + duration
        fig = go.Figure(
            go.Bar(
                x=list(totals.keys()),
                y=[value / 60 for value in totals.values()],
                marker_color="#12a5a0",
                hovertemplate="%{x}<br>%{y:.2f} 分钟<extra></extra>",
            )
        )
        fig.update_layout(
            title="睡眠与清醒状态构成",
            yaxis_title="累计时长（分钟）",
            height=310,
            margin={"l": 20, "r": 20, "t": 50, "b": 30},
            plot_bgcolor="#f8fbfd",
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _session_bounds(session: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    start = _parse_datetime(session.get("timestamps_reference_at") or session.get("session_started_at"))
    duration = session.get("duration_seconds")
    end = start + timedelta(seconds=float(duration)) if start and duration is not None else None
    return start, end


def _session_display_name(session: dict[str, Any]) -> str:
    session_type = str(session.get("session_type") or "other")
    label = SESSION_TYPE_LABELS.get(session_type, "研究会话")
    started = _parse_datetime(session.get("timeline_origin_at") or session.get("session_started_at"))
    return f"{label} · {started:%m-%d %H:%M}" if started else label


def _annotation_choices(session_type: str) -> list[str]:
    if session_type == "offline_consolidation":
        return ["睡眠状态", "脑电变化", "肌电变化", "钙活动", "其他"]
    if session_type == "fear_conditioning":
        return ["冻结行为", "刺激反应", "钙活动", "视频质量", "其他"]
    if session_type == "recall_assessment":
        return ["冻结行为", "记忆回忆反应", "探索活动", "钙活动", "视频质量", "其他"]
    if session_type == "neutral_exposure":
        return ["适应行为", "探索活动", "冻结基线", "钙活动", "视频质量", "其他"]
    return ["行为变化", "神经活动", "数据质量", "其他"]


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _clock_range(start: datetime | None, end: datetime | None) -> str:
    if start is None:
        return "时间未记录"
    if end is None:
        return start.strftime("%H:%M:%S")
    return f"{start:%H:%M:%S} - {end:%H:%M:%S}"


def _format_absolute(value: datetime | None) -> str:
    if value is None:
        return "时间未记录"
    return value.strftime("%Y-%m-%d %H:%M:%S %z")


def _format_gap(delta: timedelta) -> str:
    seconds = max(0, int(delta.total_seconds()))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days:
        return f"{days}天{hours}小时"
    if hours:
        return f"{hours}小时{minutes}分钟"
    return f"{minutes}分{seconds}秒"
