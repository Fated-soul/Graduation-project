from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg2
from psycopg2.extensions import connection as PGConnection
from psycopg2.extras import RealDictCursor

from backend.config import DB_HOST, DB_NAME, DB_PASSWORD, DB_PORT, DB_USER


class DatabaseConnectionError(RuntimeError):
    """数据库连接失败。"""


def get_connection(*, raise_errors: bool = False) -> PGConnection | None:
    try:
        return psycopg2.connect(
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
    except Exception as exc:
        print("connect db error:", exc)
        if raise_errors:
            raise DatabaseConnectionError(str(exc)) from exc
        return None


@contextmanager
def get_dict_cursor(*, commit: bool = False) -> Iterator[Any]:
    connection = get_connection(raise_errors=True)
    cursor = None
    try:
        cursor = connection.cursor(cursor_factory=RealDictCursor)
        yield cursor
        if commit:
            connection.commit()
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
