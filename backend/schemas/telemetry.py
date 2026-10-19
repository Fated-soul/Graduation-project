from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TelemetryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mouse_id: str | None = Field(default=None, max_length=50, description="实验鼠编号")
    device_id: str = Field(..., min_length=1, max_length=50, description="来源设备编号")
    temperature: float | None = Field(default=None, ge=-50, le=100, description="环境温度，单位 ℃")
    humidity: float | None = Field(default=None, ge=0, le=100, description="环境湿度，单位 %")
    is_dark: bool | None = Field(default=None, description="是否为黑暗环境")
    voltage: float | None = Field(default=None, ge=0, description="设备电压，单位 V")
    current: float | None = Field(default=None, ge=0, description="设备电流，单位 A")
    recorded_at: datetime | None = Field(default=None, description="采集时间，不传时使用服务器时间")


class TelemetryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mouse_id: str | None
    device_id: str
    temperature: float | None
    humidity: float | None
    is_dark: bool | None
    voltage: float | None
    current: float | None
    recorded_at: datetime
    created_at: datetime
