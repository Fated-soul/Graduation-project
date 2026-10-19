from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from components.metric_card import render_status_pill


def animals_dataframe(animals: list[dict[str, object]]) -> pd.DataFrame:
    return pd.DataFrame(animals)


def _format_number(value: object, digits: int = 1, empty: str = "-") -> str:
    if value is None or pd.isna(value):
        return empty
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def render_animal_table(animals: list[dict[str, object]], limit: int | None = None) -> None:
    rows = animals[:limit] if limit else animals
    if not rows:
        st.info("暂无实验动物数据。")
        return

    body = ""
    for animal in rows:
        online = bool(animal["online"])
        online_html = (
            '<span class="status-pill status-normal"><span class="dot"></span>在线</span>'
            if online
            else '<span class="status-pill status-muted"><span class="dot offline"></span>离线</span>'
        )
        body += f"""
        <tr>
            <td><strong>{escape(str(animal["id"]))}</strong></td>
            <td>{escape(str(animal["experiment"]))}</td>
            <td>{escape(str(animal["stage"]))}</td>
            <td>{escape(_format_number(animal.get("body_temperature", animal.get("temperature"))))} ℃</td>
            <td>{escape(_format_number(animal.get("heart_rate"), 0))} bpm</td>
            <td>{escape(_format_number(animal.get("blood_oxygen")))} %</td>
            <td>{render_status_pill(str(animal["risk_level"]))}</td>
            <td>{online_html}</td>
        </tr>
        """

    st.markdown(
        f"""
        <table class="data-table">
            <thead>
                <tr>
                    <th>动物编号</th>
                    <th>当前实验</th>
                    <th>实验阶段</th>
                    <th>小鼠体温</th>
                    <th>心率</th>
                    <th>血氧</th>
                    <th>风险等级</th>
                    <th>在线状态</th>
                </tr>
            </thead>
            <tbody>{body}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


def render_full_animal_table(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("暂无实验动物数据。")
        return

    display_source = df.copy()
    if "body_temperature" in display_source.columns and "temperature" in display_source.columns:
        display_source = display_source.drop(columns=["temperature"])

    display_df = display_source.rename(
        columns={
            "id": "动物编号",
            "experiment": "实验名称",
            "stage": "实验阶段",
            "device_ids": "绑定设备",
            "body_temperature": "小鼠体温",
            "temperature": "小鼠体温",
            "environment_temperature": "环境温度",
            "heart_rate": "心率",
            "blood_oxygen": "血氧",
            "activity": "活跃度",
            "risk_level": "风险等级",
            "online": "在线状态",
            "group_time": "入组时间",
        }
    ).copy()

    if "小鼠体温" in display_df:
        display_df["小鼠体温"] = display_df["小鼠体温"].map(lambda value: f"{_format_number(value)} ℃")
    if "环境温度" in display_df:
        display_df["环境温度"] = display_df["环境温度"].map(lambda value: f"{_format_number(value)} ℃")
    if "心率" in display_df:
        display_df["心率"] = display_df["心率"].map(lambda value: f"{_format_number(value, 0)} bpm")
    if "血氧" in display_df:
        display_df["血氧"] = display_df["血氧"].map(lambda value: f"{_format_number(value)} %")
    if "活跃度" in display_df:
        display_df["活跃度"] = display_df["活跃度"].map(lambda value: f"{_format_number(value, 0)}%")
    if "在线状态" in display_df:
        display_df["在线状态"] = display_df["在线状态"].map(lambda value: "在线" if value else "离线")

    preferred_columns = [
        "动物编号",
        "实验名称",
        "实验阶段",
        "绑定设备",
        "小鼠体温",
        "心率",
        "血氧",
        "环境温度",
        "风险等级",
        "在线状态",
        "入组时间",
    ]
    visible_columns = [column for column in preferred_columns if column in display_df.columns]
    st.dataframe(display_df[visible_columns], width="stretch", hide_index=True)
