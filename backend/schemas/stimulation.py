from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, model_validator

StimulationEventType = Literal["electric_shock", "flash", "noise"]


class StimulationEventCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mouse_id: str = Field(..., min_length=1, max_length=50)
    device_id: str = Field(..., min_length=1, max_length=50)
    event_type: StimulationEventType
    duration_ms: int = Field(..., gt=0)
    intensity: float | None = Field(default=None, ge=0)
    is_active: bool = True
    next_interval_ms: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("next_interval_ms", "next_delay_ms", "next_trigger_after_ms"),
    )
    started_at: datetime | None = None


class StimulationEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mouse_id: str
    device_id: str
    event_type: StimulationEventType
    duration_ms: int
    intensity: float | None
    is_active: bool
    next_interval_ms: int | None
    next_trigger_at: datetime | None
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime


class StimulationSettingUpdate(BaseModel):
    mouse_id: str | None = Field(default=None, min_length=1, max_length=50)
    device_id: str = Field(..., min_length=1, max_length=50)
    event_type: StimulationEventType
    enabled: bool = True
    min_interval_ms: int = Field(..., ge=0)
    max_interval_ms: int = Field(..., ge=0)
    min_duration_ms: int = Field(..., gt=0)
    max_duration_ms: int = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "StimulationSettingUpdate":
        if self.max_interval_ms < self.min_interval_ms:
            raise ValueError("max_interval_ms must be greater than or equal to min_interval_ms")
        if self.max_duration_ms < self.min_duration_ms:
            raise ValueError("max_duration_ms must be greater than or equal to min_duration_ms")
        return self


class StimulationSettingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mouse_id: str | None
    device_id: str
    event_type: StimulationEventType
    enabled: bool
    min_interval_ms: int
    max_interval_ms: int
    min_duration_ms: int
    max_duration_ms: int
    created_at: datetime
    updated_at: datetime
