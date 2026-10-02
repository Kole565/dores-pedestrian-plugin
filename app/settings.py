"""Настройки сервера: пути, лимиты, режимы.

Не путать с core/config.py — там гиперпараметры детектора/трекера.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw is not None else default


@dataclass
class Settings:
    # --- пути ---
    base_dir: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent.parent
    )
    data_dir: Path = field(init=False)
    uploads_dir: Path = field(init=False)
    results_dir: Path = field(init=False)
    jobs_json: Path = field(init=False)

    # --- лимиты ---
    max_upload_bytes: int = field(
        default_factory=lambda: _env_int("MAX_UPLOAD_BYTES", 2 * 1024**3)
    )  # 2 GiB
    allowed_video_ext: tuple[str, ...] = (
        ".mp4", ".avi", ".mov", ".mkv", ".webm",
    )

    # --- job runner ---
    max_workers: int = field(
        default_factory=lambda: _env_int("JOB_MAX_WORKERS", 2)
    )
    model_path: str = field(
        default_factory=lambda: os.getenv("MODEL_PATH", "yolov8n.pt")
    )

    # --- прочее ---
    cors_allow_origins: tuple[str, ...] = (
        "http://localhost:5173",  # Vite dev
        "http://127.0.0.1:5173",
        "http://localhost:8000",
    )
    debug: bool = field(default_factory=lambda: _env_bool("APP_DEBUG", False))

    def __post_init__(self) -> None:
        self.data_dir = self.base_dir / "data"
        self.uploads_dir = self.data_dir / "uploads"
        self.results_dir = self.data_dir / "results"
        self.jobs_json = self.data_dir / "jobs.json"

        for p in (self.data_dir, self.uploads_dir, self.results_dir):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
