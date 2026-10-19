from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VisionKeypointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mouse_id: str
    source_animal_id: str
    frame_index: int
    keypoint_name: str
    x: float | None
    y: float | None
    confidence: float | None
    source_file: str
    recorded_at: datetime
    created_at: datetime


class BehaviorFrameFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mouse_id: str
    source_animal_id: str
    frame_index: int
    center_x: float | None
    center_y: float | None
    movement_distance: float | None
    mean_confidence: float | None
    keypoint_count: int
    source_file: str
    recorded_at: datetime
    created_at: datetime


class VisionImportSummary(BaseModel):
    source_file: str = Field(..., description="导入的视觉 CSV 文件名")
    keypoint_rows: int = Field(..., ge=0, description="导入或更新的关键点行数")
    feature_rows: int = Field(..., ge=0, description="导入或更新的帧级特征行数")
    mouse_ids: list[str] = Field(default_factory=list, description="本次导入涉及的实验鼠编号")
