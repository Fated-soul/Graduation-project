from __future__ import annotations

import streamlit as st

from components.metric_card import render_section_title
from data.public_dataset import format_datetime, format_size, get_session, get_sessions, import_session_content


STATUS_LABELS = {
    "catalogued": "目录已建立",
    "importing": "正在载入",
    "ready": "内容已就绪",
    "error": "需要重新载入",
}


def render() -> None:
    sessions = get_sessions(limit=500)
    if not sessions:
        st.info("尚未同步造模会话，请先在“数据来源”建立研究目录。")
        return

    render_section_title("造模会话工作台", "按实验动物、研究阶段和证据类型检索会话")
    search_col, animal_col, stage_col = st.columns([1.35, 1, 1])
    with search_col:
        keyword = st.text_input("检索会话", placeholder="输入实验动物或研究阶段").strip().lower()
    with animal_col:
        animals = sorted({str(item.get("subject_code") or "") for item in sessions})
        selected_animal = st.selectbox("实验动物", ["全部", *animals])
    with stage_col:
        stages = sorted({str(item.get("modeling_stage") or "未分类") for item in sessions})
        selected_stage = st.selectbox("研究阶段", ["全部", *stages])

    evidence_filter = st.multiselect(
        "多模态证据",
        ["行为视频", "冻结行为", "足底电击", "钙成像", "EEG", "EMG", "睡眠状态"],
        placeholder="不选择则显示全部会话",
        key="session_evidence_filter",
    )
    filtered = [
        item for item in sessions
        if _matches(item, keyword, selected_animal, selected_stage, evidence_filter)
    ]
    if not filtered:
        st.warning("没有找到符合当前条件的造模会话。")
        return

    labels = {
        int(item["id"]): (
            f"{item.get('subject_code')} · {item.get('modeling_stage') or '未分类'} · "
            f"{format_datetime(item.get('session_started_at'))[:10]}"
        )
        for item in filtered
    }
    preferred = int(st.session_state.get("selected_dataset_session") or list(labels)[0])
    selected_id = st.selectbox(
        f"选择造模会话（共 {len(filtered)} 次）",
        list(labels),
        index=list(labels).index(preferred) if preferred in labels else 0,
        format_func=lambda value: labels[value],
    )
    st.session_state.selected_dataset_session = int(selected_id)
    session = {**next(item for item in filtered if int(item["id"]) == int(selected_id)), **(get_session(int(selected_id)) or {})}

    with st.container(border=True):
        st.markdown(f"### {session.get('subject_code')} · {session.get('modeling_stage') or '造模会话'}")
        metrics = st.columns(5)
        metrics[0].metric("会话时间", format_datetime(session.get("session_started_at"))[:10])
        metrics[1].metric("会话时长", _format_duration(session.get("duration_seconds")))
        metrics[2].metric("事件记录", int(session.get("modeling_event_count") or 0))
        metrics[3].metric("信号时间窗", int(session.get("signal_window_count") or 0))
        metrics[4].metric("钙成像 ROI", int(session.get("calcium_roi_count") or 0))
        st.write(session.get("description") or "本次会话属于多阶段实验动物造模流程。")

    render_section_title("证据完整度", "确认本次造模评估可使用的原始资料和处理结果")
    evidence = [
        ("行为视频", "has_video", format_size(session.get("video_size_bytes"))),
        ("冻结行为", "has_freezing", "行为区间"),
        ("足底电击", "has_shock", "刺激参数"),
        ("钙成像", "has_calcium", "群体活动与 ROI"),
        ("EEG", "has_eeg", "脑电活动"),
        ("EMG", "has_emg", "肌电活动"),
        ("睡眠状态", "has_sleep_states", "离线巩固阶段"),
    ]
    for column, (label, key, detail) in zip(st.columns(7), evidence, strict=True):
        with column:
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.write("可用" if session.get(key) else "未记录")
                st.caption(detail if session.get(key) else "本会话不包含")

    status_value = str(session.get("import_status") or "catalogued")
    if status_value == "ready":
        st.success("会话证据已载入，可进入多模态复核或 Agent 辅助决策。")
    elif status_value == "importing":
        st.info("会话正在载入，请稍后刷新。")
    else:
        if status_value == "error":
            st.warning("上次载入未完成，可以重新读取公开 NWB 文件。")
        if st.button("载入本次会话证据", type="primary", width="stretch"):
            with st.spinner("正在读取刺激、行为、钙成像与生理信号，首次载入可能需要数分钟……"):
                response = import_session_content(int(selected_id))
            if response.get("success") is False:
                st.error(str(response.get("message") or response.get("detail") or "载入失败。"))
            else:
                st.success("本次会话证据已载入。")
                st.rerun()

    left, right = st.columns(2)
    with left:
        if st.button("进入多模态复核", disabled=status_value != "ready", width="stretch"):
            _open_page("多模态复核")
    with right:
        if st.button("进入 Agent 辅助决策", disabled=status_value != "ready", width="stretch"):
            _open_page("Agent 辅助决策")

    with st.expander("查看数据来源与文件信息"):
        st.markdown(f"**来源：** {session.get('source_title') or 'DANDI 000718'}")
        st.markdown(f"**固定版本：** {session.get('source_version') or '未记录'}")
        st.markdown(f"**原始 NWB 文件：** {format_size(session.get('nwb_size_bytes'))}")
        st.markdown(f"**目录更新时间：** {format_datetime(session.get('synced_at'))}")
        if session.get("source_url"):
            st.link_button("查看公开数据集", str(session["source_url"]), width="stretch")


def _matches(item: dict, keyword: str, animal: str, stage: str, evidence: list[str]) -> bool:
    searchable = " ".join(str(item.get(key) or "") for key in ("subject_code", "modeling_stage", "description")).lower()
    if keyword and keyword not in searchable:
        return False
    if animal != "全部" and item.get("subject_code") != animal:
        return False
    if stage != "全部" and (item.get("modeling_stage") or "未分类") != stage:
        return False
    keys = {
        "行为视频": "has_video", "冻结行为": "has_freezing", "足底电击": "has_shock",
        "钙成像": "has_calcium", "EEG": "has_eeg", "EMG": "has_emg", "睡眠状态": "has_sleep_states",
    }
    return all(bool(item.get(keys[label])) for label in evidence)


def _format_duration(value: object) -> str:
    try:
        seconds = max(0, int(float(value)))
    except (TypeError, ValueError):
        return "待载入"
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes} 分 {seconds} 秒"


def _open_page(page_name: str) -> None:
    st.session_state.current_page = page_name
    st.rerun()
