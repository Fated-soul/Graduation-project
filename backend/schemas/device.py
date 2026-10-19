from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DeviceCreate(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=50)
    device_type: str = Field(..., min_length=1, max_length=50)
    device_name: str = Field(..., min_length=1, max_length=100)
    mouse_id: str | None = Field(default=None, max_length=50)
    online: bool = False
    voltage: float | None = Field(default=None, ge=0)
    current: float | None = Field(default=None, ge=0)
    last_seen: datetime | None = None


class DeviceStatusUpdate(BaseModel):
    online: bool | None = None
    voltage: float | None = Field(default=None, ge=0)
    current: float | None = Field(default=None, ge=0)
    last_seen: datetime | None = None

    @model_validator(mode="after")
    def require_one_field(self) -> Self:
        if (
            self.online is None
            and self.voltage is None
            and self.current is None
            and self.last_seen is None
        ):
            raise ValueError("at least one device status field is required")
        return self


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    device_type: str
    device_name: str
    mouse_id: str | None
    online: bool
    online_status: str
    voltage: float | None
    current: float | None
    last_seen: datetime | None
    created_at: datetime
    updated_at: datetime
