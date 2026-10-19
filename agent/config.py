from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


APP_NAME = "明察鼠毫 多模态证据 Agent"
APP_VERSION = "0.2.0"

BACKEND_API_URL = os.getenv(
    "MINGCHA_BACKEND_API_URL", "http://127.0.0.1:8000"
).rstrip("/")
BACKEND_API_TIMEOUT_SECONDS = float(
    os.getenv("MINGCHA_BACKEND_API_TIMEOUT_SECONDS", "15")
)

# 阿里云百炼 OpenAI 兼容接口。生产环境可替换为业务空间专属地址。
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
DASHSCOPE_BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
).rstrip("/")
DASHSCOPE_MODEL = os.getenv("DASHSCOPE_MODEL", "deepseek-v4.1-flash").strip()
DASHSCOPE_ENABLE_THINKING = _env_bool("DASHSCOPE_ENABLE_THINKING", True)
DASHSCOPE_REASONING_EFFORT = os.getenv(
    "DASHSCOPE_REASONING_EFFORT", "low"
).strip().lower()
DASHSCOPE_MAX_TOKENS = int(os.getenv("DASHSCOPE_MAX_TOKENS", "2400"))
DASHSCOPE_TIMEOUT_SECONDS = float(os.getenv("DASHSCOPE_TIMEOUT_SECONDS", "180"))

AGENT_ALLOW_RULE_FALLBACK = _env_bool("AGENT_ALLOW_RULE_FALLBACK", True)
AGENT_MAX_HISTORY_MESSAGES = int(os.getenv("AGENT_MAX_HISTORY_MESSAGES", "12"))
AGENT_MAX_VISION_FEATURES = int(os.getenv("AGENT_MAX_VISION_FEATURES", "500"))

# 检索增强生成：知识文档随项目管理，向量通过百炼 OpenAI 兼容接口生成。
RAG_ENABLED = _env_bool("RAG_ENABLED", True)
RAG_USE_EMBEDDINGS = _env_bool("RAG_USE_EMBEDDINGS", True)
RAG_EMBEDDING_MODEL = os.getenv(
    "RAG_EMBEDDING_MODEL", "text-embedding-v4"
).strip()
RAG_EMBEDDING_DIMENSIONS = int(os.getenv("RAG_EMBEDDING_DIMENSIONS", "512"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.08"))
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "900"))
RAG_KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"
RAG_CACHE_PATH = Path(__file__).resolve().parent / "cache" / "knowledge_index.json"


def validate_settings() -> list[str]:
    issues: list[str] = []
    if not DASHSCOPE_API_KEY:
        issues.append("DASHSCOPE_API_KEY is not configured")
    if DASHSCOPE_REASONING_EFFORT not in {"low", "high", "max"}:
        issues.append(
            "DASHSCOPE_REASONING_EFFORT must be one of: low, high, max"
        )
    if DASHSCOPE_MODEL != "deepseek-v4.1-flash":
        issues.append(
            "DASHSCOPE_MODEL is not deepseek-v4.1-flash; verify the intended model"
        )
    if RAG_EMBEDDING_DIMENSIONS not in {64, 128, 256, 512, 768, 1024, 1536, 2048}:
        issues.append("RAG_EMBEDDING_DIMENSIONS is not supported by text-embedding-v4")
    if RAG_TOP_K < 1 or RAG_TOP_K > 10:
        issues.append("RAG_TOP_K must be between 1 and 10")
    return issues

