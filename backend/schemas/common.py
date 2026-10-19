from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class APIResponse(BaseModel):
    success: bool = True
    message: str = "ok"
    data: Any | None = None
