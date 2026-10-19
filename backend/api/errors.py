from __future__ import annotations

import psycopg2
from fastapi import HTTPException

from backend.database.connection import DatabaseConnectionError


def raise_database_http_exception(exc: Exception) -> None:
    if isinstance(exc, DatabaseConnectionError):
        raise HTTPException(status_code=503, detail="database unavailable") from exc

    if isinstance(exc, psycopg2.IntegrityError):
        if exc.pgcode == "23505":
            raise HTTPException(status_code=409, detail="record already exists") from exc
        if exc.pgcode == "23503":
            raise HTTPException(
                status_code=400,
                detail="related animal or device does not exist",
            ) from exc
        if exc.pgcode == "23514":
            raise HTTPException(status_code=400, detail="database constraint violated") from exc

    if isinstance(exc, psycopg2.Error):
        raise HTTPException(status_code=500, detail="database operation failed") from exc

    raise HTTPException(status_code=500, detail="internal server error") from exc
