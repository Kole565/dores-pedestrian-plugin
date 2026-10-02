"""Pydantic-схемы HTTP API."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

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
