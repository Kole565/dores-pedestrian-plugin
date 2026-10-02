"""Pydantic-схемы HTTP API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Общее
# ---------------------------------------------------------------------------

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class LimitsResponse(BaseModel):
    max_upload_bytes: int
    allowed_video_ext: list[str]


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class JobProgress(BaseModel):
    frames_done: int = 0
    frames_total: int = 0
    fps_avg: float = 0.0


class JobResult(BaseModel):
    output_video: Optional[str] = None
    report_json: Optional[str] = None
    events_csv: Optional[str] = None
    intensity_png: Optional[str] = None


class JobInfo(BaseModel):
    id: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    input_filename: str
    lines_config_id: Optional[str] = None
    progress: JobProgress = Field(default_factory=JobProgress)
    result: Optional[JobResult] = None
    error_message: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: list[JobInfo]

# ---------------------------------------------------------------------------
# Lines
# ---------------------------------------------------------------------------

UsePoint = Literal["center", "bottom_center"]
Direction = Literal["in", "out", "left", "right", "unknown"]


class Line(BaseModel):
    """Одна виртуальная линия внутри конфига."""
    line_id: str = Field(min_length=1, max_length=64)
    coords: tuple[float, float, float, float] = Field(
        description="(x1, y1, x2, y2) в пикселях исходного кадра",
    )
    direction_pos_to_neg: Direction = "in"
    direction_neg_to_pos: Direction = "out"
    use_point: UsePoint = "bottom_center"


class LinesConfigBase(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    frame_width: Optional[int] = Field(default=None, ge=1)
    frame_height: Optional[int] = Field(default=None, ge=1)
    lines: list[Line] = Field(default_factory=list)


class LinesConfigCreate(LinesConfigBase):
    pass


class LinesConfigUpdate(LinesConfigBase):
    """PUT — полная замена."""
    pass


class LinesConfigPatch(BaseModel):
    """PATCH — частичное обновление."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    frame_width: Optional[int] = Field(default=None, ge=1)
    frame_height: Optional[int] = Field(default=None, ge=1)
    lines: Optional[list[Line]] = None


class LinesConfig(LinesConfigBase):
    id: str
    created_at: datetime
    updated_at: datetime


class LinesConfigListResponse(BaseModel):
    configs: list[LinesConfig]


# ---------------------------------------------------------------------------
# Frame (подложка для редактора линий)
# ---------------------------------------------------------------------------

class FrameSource(str, Enum):
    UPLOAD = "upload"
    STREAM = "stream"


class FrameQuery(BaseModel):
    """Параметры GET /api/lines/frame (не используется напрямую, для доки)."""
    source: FrameSource
    id: str
    t_sec: float = 0.0


class StreamStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class StreamStats(BaseModel):
    total: int = 0
    per_line: dict[str, dict[str, int]] = Field(default_factory=dict)
    fps: float = 0.0
    active_tracks: int = 0
    frames_processed: int = 0


class StreamInfo(BaseModel):
    id: str
    status: StreamStatus
    rtsp_url_masked: str          # пароль замаскирован
    lines_config_id: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    last_frame_at: Optional[datetime] = None
    stats: StreamStats = Field(default_factory=StreamStats)
    error_message: Optional[str] = None


class StreamCreate(BaseModel):
    rtsp_url: str = Field(min_length=1)
    lines_config_id: Optional[str] = None
    # inline для тестов, приоритет как у jobs
    lines_config: Optional[dict] = None


class StreamListResponse(BaseModel):
    streams: list[StreamInfo]
