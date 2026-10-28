from __future__ import annotations

from pathlib import Path
import sys

import streamlit as st


FRONTEND_DIR = Path(__file__).resolve().parents[1]
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from components.synchronized_player import render_synchronized_player


selected_time = render_synchronized_player(
    video_url=None,
    duration_seconds=30.0,
    modeling_events=[],
    signal_windows=[],
    annotations=[],
    key="synchronized_player_smoke_test",
)
st.write("播放器组件已载入", selected_time)
