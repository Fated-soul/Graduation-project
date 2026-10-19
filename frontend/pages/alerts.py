from __future__ import annotations

import streamlit as st

from components.alert_list import render_alert_items
from components.metric_card import render_metric_card, render_section_title
from data.backend_data import get_animals, get_risk_events


def render() -> None:
    animals = get_animals()
    alerts = get_risk_events(animals)
    high_risk = sum(1 for alert in alerts if alert["level"] == "高风险")
    pending = sum(1 for alert in alerts if alert["status"] == "待复核")
    data_gaps = sum(1 for alert in alerts if alert["status"] == "数据不足")
    metric_cols = st.columns(4)
    metrics = [
        ("当前风险对象", len(alerts), "只", "依据实时状态与最新评估", "险", "关注" if alerts else "正常"),
        ("高风险", high_risk, "只", "需要优先人工复核", "危", "高风险" if high_risk else "正常"),
        ("待人工复核", pending, "条", "尚未确认处置方案", "待", "关注" if pending else "正常"),
        ("数据不足", data_gaps, "只", "采集连续性需要恢复", "缺", "关注" if data_gaps else "正常"),
    ]
    for col, metric in zip(metric_cols, metrics, strict=True):
        with col:
            render_metric_card(*metric)

    filter_cols = st.columns(2)
    with filter_cols[0]:
        level_options = ["全部"] + sorted({alert["level"] for alert in alerts})
        level_filter = st.selectbox("风险级别筛选", level_options)
    with filter_cols[1]:
        status_options = ["全部"] + sorted({alert["status"] for alert in alerts})
        status_filter = st.selectbox("复核状态筛选", status_options)

    filtered = []
    for alert in alerts:
        if level_filter != "全部" and alert["level"] != level_filter:
            continue
        if status_filter != "全部" and alert["status"] != status_filter:
            continue
        filtered.append(alert)

    render_section_title("风险评估与事件追踪", f"当前筛选结果：{len(filtered)} 条")
    if filtered:
        render_alert_items(filtered, compact=False)
    else:
        st.info("当前没有符合筛选条件的风险对象。")
