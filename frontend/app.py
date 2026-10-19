from __future__ import annotations

from pathlib import Path
import sys

import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from components.header import render_header
from components.sidebar import render_sidebar
from pages import (
    data_sources,
    dataset_agent,
    evidence_review,
    public_dashboard,
    research_data,
    sessions,
    subjects,
)
from utils.state import initialize_session_state
from utils.styles import load_global_styles


PAGE_RENDERERS = {
    "造模总览": public_dashboard.render,
    "实验动物": subjects.render,
    "造模会话": sessions.render,
    "多模态复核": evidence_review.render,
    "Agent 辅助决策": dataset_agent.render,
    "数据来源": data_sources.render,
    "研究数据": research_data.render,
}


def main() -> None:
    st.set_page_config(
        page_title="明察鼠毫 - 实验动物多模态智能造模与 Agent 辅助决策系统",
        page_icon="明",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    initialize_session_state()
    load_global_styles()
    render_sidebar()

    current_page = st.session_state.current_page
    render_header(current_page)
    PAGE_RENDERERS.get(current_page, public_dashboard.render)()


if __name__ == "__main__":
    main()
