from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AnimalStatus = Literal["normal", "attention", "high_risk", "offline"]
ExperimentName = Literal["行为无助造模"]
ExperimentStage = Literal["准备阶段", "适应阶段", "应激阶段", "行为测试阶段", "观察阶段", "完成"]


class AnimalCreate(BaseModel):
    mouse_id: str = Field(..., min_length=1, max_length=50)
    current_status: AnimalStatus = "normal"
    experiment_name: ExperimentName = "行为无助造模"
    experiment_stage: ExperimentStage | None = "准备阶段"


class AnimalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mouse_id: str
    current_status: AnimalStatus
    experiment_name: str | None
    experiment_stage: str | None
    created_at: datetime
    updated_at: datetime


class AnimalStatusUpdate(BaseModel):
    status: AnimalStatus
    reason: str | None = Field(default=None, max_length=500)


class AnimalStageUpdate(BaseModel):
    experiment_stage: ExperimentStage


class AnimalDeviceBindingUpdate(BaseModel):
    device_id: str | None = Field(default=None, max_length=50)


class AnimalStatusHistoryResponse(BaseModel):
    id: int
    mouse_id: str
    status: AnimalStatus
    reason: str | None
    recorded_at: datetime
    created_at: datetime
