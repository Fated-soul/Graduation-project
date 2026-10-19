from __future__ import annotations

import os

APP_NAME = "明察鼠毫 多模态研究后端"
APP_DESCRIPTION = "实验动物多模态研究与 Agent 辅助决策系统数据服务"
APP_VERSION = "0.2.0"

# 本地研究环境默认配置，部署时可通过环境变量覆盖。
DB_NAME = os.getenv("IOT_DB_NAME", "IOT")
DB_USER = os.getenv("IOT_DB_USER", "postgres")
DB_PASSWORD = os.getenv("IOT_DB_PASSWORD", "123")
DB_HOST = os.getenv("IOT_DB_HOST", "localhost")
DB_PORT = os.getenv("IOT_DB_PORT", "5432")

ANIMAL_STATUS_VALUES = ("normal", "attention", "high_risk", "offline")
STIMULATION_EVENT_TYPES = ("electric_shock", "flash", "noise")
CAMERA_STREAM_URL = os.getenv(
    "CAMERA_STREAM_URL",
    "https://numbness-dimple-retinal.ngrok-free.dev/video_feed",
)

# 独立 Mouse Agent API。Backend 只通过 HTTP 代理，不直接导入 Agent 模型代码。
AGENT_API_URL = os.getenv("AGENT_API_URL", "http://127.0.0.1:8001").rstrip("/")
AGENT_API_TIMEOUT_SECONDS = float(os.getenv("AGENT_API_TIMEOUT_SECONDS", "360"))

# 本地开发配置：允许 Streamlit 和 FastAPI 调试访问。
CORS_ORIGINS = [
    "http://localhost",
    "http://localhost:8501",
    "http://127.0.0.1",
    "http://127.0.0.1:8501",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# DANDI 公开数据集。目录同步只写入元数据，NWB 与视频内容按需远程读取。
DANDI_API_URL = os.getenv("DANDI_API_URL", "https://api.dandiarchive.org").rstrip("/")
DANDI_DANDISET_ID = os.getenv("DANDI_DANDISET_ID", "000718")
DANDI_VERSION = os.getenv("DANDI_VERSION", "0.260825.1902")
DANDI_SOURCE_KEY = f"dandi-{DANDI_DANDISET_ID}-{DANDI_VERSION}"
DANDI_REQUEST_TIMEOUT_SECONDS = float(os.getenv("DANDI_REQUEST_TIMEOUT_SECONDS", "30"))
