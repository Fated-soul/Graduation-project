from __future__ import annotations

import streamlit as st

from utils.constants import APP_NAME, APP_SUBTITLE, NAV_GROUPS


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-logo">
                <div class="logo-mark">明</div>
                <div class="sidebar-brand-copy">
                    <div class="sidebar-title">{APP_NAME}</div>
                    <div class="sidebar-subtitle">{APP_SUBTITLE}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for group_index, (group_name, items) in enumerate(NAV_GROUPS):
            st.markdown(
                f'<div class="sidebar-section-label">{group_name}</div>',
                unsafe_allow_html=True,
            )
            with st.container(key=f"sidebar_nav_group_{group_index}"):
                for page_name, icon in items:
                    active = st.session_state.current_page == page_name
                    if st.button(
                        page_name,
                        icon=icon,
                        key=f"nav_{page_name}",
                        width="stretch",
                        type="primary" if active else "secondary",
                    ):
                        st.session_state.current_page = page_name
                        st.rerun()
