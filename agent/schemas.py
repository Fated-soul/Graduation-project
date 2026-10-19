from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class APIResponse(BaseModel):
    success: bool = True
    message: str = "ok"
    data: Any | None = None


class VitalSignsOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature: float | None = Field(default=None, ge=20, le=45)
    body_temperature: float | None = Field(default=None, ge=20, le=45)
    heart_rate: float | None = Field(default=None, ge=0, le=1000)
    blood_oxygen: float | None = Field(default=None, ge=0, le=100)


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vision: dict[str, Any] | None = None
    vital_signs: VitalSignsOverride | None = None
    use_llm: bool = True
    use_semantic_reasoning: bool = True
    llm_provider: str = "bailian"
    model: str | None = None
    history_hours: int = Field(default=24, ge=1, le=168)
    history_limit: int = Field(default=500, ge=1, le=5000)
    stimulation_hours: int = Field(default=168, ge=1, le=168)
    stimulation_limit: int = Field(default=100, ge=1, le=1000)


class CreateConversationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mouse_id: str | None = Field(default=None, min_length=1, max_length=100)
    vision: dict[str, Any] | None = None
    llm_provider: str = "bailian"
    model: str | None = None
    use_llm: bool = True
    use_semantic_reasoning: bool = True


class ConversationMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=4000)
    mouse_id: str | None = Field(default=None, min_length=1, max_length=100)
    vision: dict[str, Any] | None = None
    vital_signs: VitalSignsOverride | None = None


class DatasetSessionAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=10000)
    model: str | None = Field(default=None, min_length=1, max_length=100)


class KnowledgeSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=10)


class AnalysisResult(BaseModel):
    mouse_id: str
    risk_score: int = Field(..., ge=0, le=100)
    risk_level: str
    summary: str
    vital_analysis: str
    behavior_analysis: str
    stage_analysis: str
    risk_analysis: str
    recommendation: str
    control_strategy: str
    factors: list[str] = Field(default_factory=list)
    analysis_source: str
    model_provider: str | None = None
    model_name: str | None = None
    experiment_stage: str | None = None
    knowledge_sources: list[dict[str, Any]] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=datetime.now)

