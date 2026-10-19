from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentVitalSignsOverride(BaseModel):
    """Optional manual override; normally Agent reads the latest Backend values."""

    model_config = ConfigDict(extra="forbid")

    body_temperature: float = Field(..., ge=20, le=45)
    heart_rate: float | None = Field(default=None, ge=0, le=1000)
    blood_oxygen: float | None = Field(default=None, ge=0, le=100)


class AgentAnalyzeRequest(BaseModel):
    """Frontend-facing request for one mouse analysis."""

    model_config = ConfigDict(extra="forbid")

    # Optional since the Agent can now adapt Backend /api/vision data itself.
    vision: dict[str, Any] | None = None
    vital_signs: AgentVitalSignsOverride | None = None
    use_llm: bool = True
    use_semantic_reasoning: bool = True
    llm_provider: Literal["bailian", "openai", "zhipu", "doubao"] = "bailian"
    model: str | None = None
    history_hours: int = Field(default=24, ge=1, le=168)
    history_limit: int = Field(default=500, ge=1, le=5000)
    stimulation_hours: int = Field(default=168, ge=1, le=168)
    stimulation_limit: int = Field(default=100, ge=1, le=1000)


class AgentCreateConversationRequest(BaseModel):
    """Create a stateful conversation owned by the standalone Agent service."""

    model_config = ConfigDict(extra="forbid")

    mouse_id: str | None = Field(default=None, min_length=1, max_length=100)
    vision: dict[str, Any] | None = None
    llm_provider: Literal["bailian", "openai", "zhipu", "doubao"] = "bailian"
    model: str | None = None
    use_llm: bool = True
    use_semantic_reasoning: bool = False


class AgentConversationMessageRequest(BaseModel):
    """One user turn forwarded to an existing Agent conversation."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, max_length=4000)
    mouse_id: str | None = Field(default=None, min_length=1, max_length=100)
    vision: dict[str, Any] | None = None
    vital_signs: dict[str, Any] | None = None
