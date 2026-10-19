from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

from backend.config import APP_NAME, APP_VERSION
from backend.database.connection import get_connection

router = APIRouter(tags=["system"])


@router.get("/")
def root() -> dict[str, str]:
    return {
        "name": APP_NAME,
        "status": "running",
        "version": APP_VERSION,
    }


@router.get("/api/health")
def health_check() -> dict[str, str]:
    connection = get_connection()
    if connection is None:
        database_status = "disconnected"
        status = "degraded"
    else:
        connection.close()
        database_status = "connected"
        status = "ok"

    return {
        "status": status,
        "database": database_status,
        "timestamp": datetime.now().astimezone().isoformat(),
    }
