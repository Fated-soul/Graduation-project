from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CatalogSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100)


class SessionAnnotationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp_seconds: float | None = Field(default=None, ge=0)
    category: str = Field(..., min_length=1, max_length=80)
    note: str = Field(..., min_length=1, max_length=2000)
    created_by: str = Field(default="researcher", min_length=1, max_length=100)


class SessionAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(
        default="请综合分析本次实验会话的多模态证据。",
        min_length=1,
        max_length=2000,
    )
    use_llm: bool = True
    model: str | None = Field(default=None, min_length=1, max_length=100)

