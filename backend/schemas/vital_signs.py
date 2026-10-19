from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VitalSignsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mouse_id: str = Field(..., min_length=1, max_length=50, description="实验鼠编号")
    device_id: str = Field(..., min_length=1, max_length=50, description="来源设备编号")
    body_temperature: float | None = Field(default=None, ge=20, le=45, description="小鼠体温，单位 ℃")
    heart_rate: float | None = Field(default=None, ge=0, le=1000, description="小鼠心率，单位 bpm")
    blood_oxygen: float | None = Field(default=None, ge=0, le=100, description="小鼠血氧饱和度，单位 %")
    recorded_at: datetime | None = Field(default=None, description="采集时间，不传时使用服务器时间")

    @model_validator(mode="after")
    def require_at_least_one_vital_value(self) -> "VitalSignsCreate":
        if (
            self.body_temperature is None
            and self.heart_rate is None
            and self.blood_oxygen is None
        ):
            raise ValueError("at least one vital sign value is required")
        return self


class VitalSignsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mouse_id: str
    device_id: str
    body_temperature: float | None
    heart_rate: float | None
    blood_oxygen: float | None
    recorded_at: datetime
    created_at: datetime
