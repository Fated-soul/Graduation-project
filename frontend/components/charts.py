from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


PLOT_CONFIG = {"displayModeBar": False, "responsive": True}


def _base_layout(fig: go.Figure, title: str, y_title: str) -> go.Figure:
    fig.update_layout(
        title={"text": title, "font": {"size": 16, "color": "#17324d"}},
        margin={"l": 8, "r": 8, "t": 46, "b": 8},
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.35)",
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.08, "x": 0.64},
        font={"family": "Arial, sans-serif", "color": "#334155", "size": 12},
        xaxis={"showgrid": False, "title": ""},
        yaxis={"gridcolor": "rgba(148, 163, 184, 0.18)", "title": y_title},
    )
    return fig


def create_temperature_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["temperature"],
            mode="lines+markers",
            name="体温",
            line={"color": "#0ea5e9", "width": 3, "shape": "spline"},
            marker={"size": 5},
            connectgaps=False,
        )
    )
    fig.add_hrect(y0=38.0, y1=39.5, fillcolor="rgba(239,68,68,0.08)", line_width=0)
    fig.add_hline(
        y=38.0,
        line_dash="dash",
        line_color="#ef4444",
        annotation_text="异常阈值 38.0℃",
        annotation_position="top left",
    )
    return _base_layout(fig, "体温变化趋势", "℃")


def create_heart_rate_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["heart_rate"],
            mode="lines+markers",
            name="心率",
            line={"color": "#8b5cf6", "width": 3, "shape": "spline"},
            marker={"size": 5},
            connectgaps=False,
        )
    )
    fig.add_hrect(y0=470, y1=530, fillcolor="rgba(239,68,68,0.07)", line_width=0)
    fig.add_hline(
        y=470,
        line_dash="dash",
        line_color="#ef4444",
        annotation_text="异常阈值 470 bpm",
        annotation_position="top left",
    )
    return _base_layout(fig, "心率变化趋势", "bpm")


def create_activity_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["activity"],
            mode="lines+markers",
            name="活跃度",
            line={"color": "#10b981", "width": 3, "shape": "spline"},
            marker={"size": 5},
            connectgaps=False,
        )
    )
    return _base_layout(fig, "活跃度趋势", "%")


def create_environment_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["environment_temperature"],
            mode="lines",
            name="环境温度 ℃",
            line={"color": "#0ea5e9", "width": 3, "shape": "spline"},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["humidity"],
            mode="lines",
            name="环境湿度 %",
            line={"color": "#06b6d4", "width": 3, "shape": "spline"},
        )
    )
    return _base_layout(fig, "环境温湿度趋势", "温湿度")


def create_data_trend_chart(df: pd.DataFrame) -> go.Figure:
    value_column = next(column for column in df.columns if column != "timestamp")
    fig = px.line(df, x="timestamp", y=value_column, markers=True)
    fig.update_traces(line={"color": "#0ea5e9", "width": 3, "shape": "spline"})
    return _base_layout(fig, "过去 24 小时多模态数据采集趋势", "记录数")


def create_donut_chart(df: pd.DataFrame) -> go.Figure:
    fig = px.pie(df, names="数据类型", values="数量", hole=0.58, color_discrete_sequence=px.colors.sequential.Teal)
    fig.update_layout(
        title={"text": "不同数据类型占比", "font": {"size": 16, "color": "#17324d"}},
        height=300,
        margin={"l": 8, "r": 8, "t": 46, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        legend={"orientation": "h", "y": -0.04},
        font={"family": "Arial, sans-serif", "color": "#334155", "size": 12},
    )
    return fig


def create_bar_chart(df: pd.DataFrame, x: str, y: str, title: str, color: str = "#0ea5e9") -> go.Figure:
    fig = px.bar(df, x=x, y=y, text=y)
    fig.update_traces(marker_color=color, textposition="outside")
    fig.update_layout(
        title={"text": title, "font": {"size": 16, "color": "#17324d"}},
        height=300,
        margin={"l": 8, "r": 8, "t": 46, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0.35)",
        font={"family": "Arial, sans-serif", "color": "#334155", "size": 12},
        xaxis={"showgrid": False, "title": ""},
        yaxis={"gridcolor": "rgba(148, 163, 184, 0.18)", "title": y},
    )
    return fig


def create_blood_oxygen_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["timestamp"],
            y=df["blood_oxygen"],
            mode="lines+markers",
            name="血氧",
            line={"color": "#06b6d4", "width": 3, "shape": "spline"},
            marker={"size": 5},
            connectgaps=False,
        )
    )
    fig.add_hrect(y0=0, y1=94, fillcolor="rgba(239,68,68,0.07)", line_width=0)
    fig.add_hline(
        y=94,
        line_dash="dash",
        line_color="#ef4444",
        annotation_text="异常阈值 94%",
        annotation_position="bottom left",
    )
    return _base_layout(fig, "血氧变化趋势", "%")
