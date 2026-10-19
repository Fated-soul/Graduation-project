from __future__ import annotations

import base64
import os
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from utils.api_client import get_api_base_url

REMOTE_CAMERA_STREAM_URL = "https://numbness-dimple-retinal.ngrok-free.dev/video_feed"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_CAMERA_VIDEO_PATH = PROJECT_ROOT / "vedio.mp4"
CAMERA_SOURCE_ENV = "MINGCHA_CAMERA_SOURCE"


def get_backend_camera_stream_url() -> str:
    return f"{get_api_base_url()}/api/camera/stream"


def _render_remote_camera_stream(mouse_id: str) -> None:
    proxy_url = get_backend_camera_stream_url()
    fallback_url = REMOTE_CAMERA_STREAM_URL
    html = (
        '<div class="camera-frame">'
        f'<img src="{escape(proxy_url)}" '
        f'onerror="this.onerror=null;this.src=\'{escape(fallback_url)}\';" '
        f'alt="{escape(mouse_id)} 实时摄像头影像" />'
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


@lru_cache(maxsize=1)
def _load_local_video_base64() -> str:
    return base64.b64encode(LOCAL_CAMERA_VIDEO_PATH.read_bytes()).decode("ascii")


def _render_local_camera_video(mouse_id: str) -> None:
    if not LOCAL_CAMERA_VIDEO_PATH.exists():
        st.warning("当前暂时无法读取实时影像，请检查影像来源。")
        return

    video_base64 = _load_local_video_base64()
    components.html(
        f"""
        <style>
            html, body {{
                margin: 0;
                padding: 0;
                background: transparent;
                overflow: hidden;
            }}
            .camera-frame {{
                width: min(100%, 760px);
                aspect-ratio: 1 / 1;
                margin: 0 auto;
                overflow: hidden;
                border-radius: 12px;
                border: 1px solid rgba(14, 116, 144, 0.14);
                background: #0f172a;
                display: grid;
                place-items: center;
            }}
            .camera-frame video {{
                width: 100%;
                height: 100%;
                display: block;
                object-fit: contain;
            }}
        </style>
        <div class="camera-frame">
            <video autoplay muted loop playsinline preload="auto"
                   disablepictureinpicture
                   controlslist="nodownload nofullscreen noremoteplayback"
                   aria-label="{escape(mouse_id)} 实时摄像头影像">
                <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
            </video>
        </div>
        """,
        height=790,
        scrolling=False,
    )


def render_camera_stream(mouse_id: str) -> None:
    st.markdown(
        f"""
        <div class="camera-card">
            <div class="camera-card-head">
                <div>
                    <strong>{escape(mouse_id)} 实时影像</strong>
                    <div class="section-subtitle">小鼠行为监控画面实时展示</div>
                </div>
                <span class="status-pill status-normal">实时</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if os.getenv(CAMERA_SOURCE_ENV, "local").strip().lower() == "remote":
        _render_remote_camera_stream(mouse_id)
    else:
        _render_local_camera_video(mouse_id)
