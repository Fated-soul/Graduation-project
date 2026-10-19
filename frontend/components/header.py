from __future__ import annotations

from datetime import datetime
from html import escape

import streamlit as st

from data.backend_data import backend_summary
from utils.constants import PAGE_DESCRIPTIONS


def render_header(page_name: str) -> None:
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    description = PAGE_DESCRIPTIONS.get(page_name, "实验动物多模态智能造模与 Agent 辅助决策")
    summary = backend_summary()
    connected = bool(summary.get("connected"))
    connection_class = "status-normal" if connected else "status-muted"
    connection_text = "数据服务正常" if connected else "数据服务未连接"
    st.markdown(
        f"""
        <div class="app-header">
            <div>
                <div class="page-title">{escape(page_name)}</div>
                <div class="page-desc">{escape(description)}</div>
            </div>
            <div class="header-status">
                <span class="status-pill {connection_class}"><span class="dot"></span>{connection_text}</span>
                <span class="header-time">{escape(current_time)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

