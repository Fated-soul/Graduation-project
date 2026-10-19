from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ControlCommandType = Literal["electric_shock", "flash", "noise"]
ControlCommandStatus = Literal["pending", "sent", "completed", "failed", "expired"]
ControlCommandAckStatus = Literal["completed", "failed"]


class ControlCommandCreate(BaseModel):
    mouse_id: str = Field(..., min_length=1, max_length=50)
    device_id: str = Field(..., min_length=1, max_length=50)
    command_type: ControlCommandType
    duration_ms: int = Field(..., gt=0, le=60000)
    intensity: float | None = Field(default=None, ge=0)


class ControlCommandAck(BaseModel):
    status: ControlCommandAckStatus
    message: str | None = Field(default=None, max_length=500)
    started_at: datetime | None = None


class ControlCommandWebSocketAck(ControlCommandAck):
    command_id: str = Field(..., min_length=1, max_length=64)


class ControlCommandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    command_id: str
    mouse_id: str
    device_id: str
    command_type: ControlCommandType
    duration_ms: int
    intensity: float | None
    status: ControlCommandStatus
    requested_at: datetime
    dispatched_at: datetime | None
    acknowledged_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
