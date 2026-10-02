"""Хранилище job'ов: JSON-файл с атомарной записью.

Для демо этого достаточно. Позже можно заменить на SQLite —
интерфейс (get/list/save/delete) останется тем же.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Optional

from .schemas import JobInfo


class JobStore:
    """Потокобезопасное JSON-хранилище для JobInfo.

    Атомарная запись: пишем в .tmp, потом os.replace.
    """

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.RLock()
        self._jobs: dict[str, JobInfo] = {}
        self._load()

    # --- внутреннее ---

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # повреждённый файл — начинаем с чистого листа
            raw = {}
        for job_id, payload in raw.items():
            try:
                self._jobs[job_id] = JobInfo.model_validate(payload)
            except Exception:
                # несовместимая запись — пропускаем
                continue

    def _flush_locked(self) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        data = {
            job_id: job.model_dump(mode="json")
            for job_id, job in self._jobs.items()
        }
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self._path)

    # --- публичный API ---

    def save(self, job: JobInfo) -> None:
        with self._lock:
            self._jobs[job.id] = job
            self._flush_locked()

    def get(self, job_id: str) -> Optional[JobInfo]:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[JobInfo]:
        with self._lock:
            return sorted(
                self._jobs.values(),
                key=lambda j: j.created_at,
                reverse=True,
            )

    def delete(self, job_id: str) -> bool:
        with self._lock:
            if job_id not in self._jobs:
                return False
            del self._jobs[job_id]
            self._flush_locked()
            return True

    def mark_zombies_as_failed(self) -> int:
        """После рестарта сервера: running/pending → failed.

        Воркеры ProcessPool не переживают перезапуск процесса.
        """
        from datetime import datetime
        with self._lock:
            count = 0
            for job in self._jobs.values():
                if job.status in ("pending", "running"):
                    job.status = "failed"
                    job.error_message = "Server restarted during job"
                    job.finished_at = datetime.utcnow()
                    count += 1
            if count:
                self._flush_locked()
            return count
