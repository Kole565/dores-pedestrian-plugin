"""Job Runner для offline-задач.

Архитектура:
  - FastAPI-процесс принимает upload, сохраняет файл, создаёт JobInfo(pending).
  - Задача уходит в ProcessPoolExecutor (YOLO в отдельном процессе).
  - Воркер пишет прогресс в Manager.dict (общий для всех процессов).
  - FastAPI-поток-наблюдатель (watcher) периодически синхронизирует
    Manager.dict → JobStore и финализирует статус.
"""
from __future__ import annotations

import multiprocessing as mp
import threading
import time
import traceback
from concurrent.futures import Future, ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.runner import run_offline
from core import config as core_config
from sources.factory import open_source

from .schemas import JobInfo, JobProgress, JobResult, JobStatus
from .settings import settings

# ---------------------------------------------------------------------------
# Worker: выполняется в отдельном процессе
# ---------------------------------------------------------------------------

def _worker_run_job(
    *,
    job_id: str,
    input_path: str,
    output_dir: str,
    lines_config: dict,
    model_path: str,
    progress: "mp.Manager.dict",  # type: ignore[valid-type]
) -> dict:
    """Тело воркера. Возвращает dict с результатом (сериализуемый).

    Прогресс пишет в переданный Manager.dict под ключом job_id.
    """
    source = None
    try:
        source = open_source(input_path, kind="auto")

        def _progress_cb(frame_idx: int, frame_count: int, fps: float) -> None:
            progress[job_id] = {
                "frames_done": frame_idx,
                "frames_total": frame_count,
                "fps_avg": round(fps, 2),
            }

        result = run_offline(
            source,
            model_path=model_path,
            lines_config=lines_config,
            output_video=Path(output_dir) / "annotated.mp4",
            output_report_json=Path(output_dir) / "report.json",
            output_events_csv=Path(output_dir) / "events.csv",
            output_intensity_png=Path(output_dir) / "intensity.png",
            progress_cb=_progress_cb,
        )
        return {
            "ok": True,
            "frames_processed": result.frames_processed,
            "fps_avg": result.fps_avg,
            "duration_sec": result.duration_sec,
            "stats": result.stats,
            "output_video": result.output_video,
            "report_json": result.report_json,
            "events_csv": result.events_csv,
            "intensity_png": result.intensity_png,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
    finally:
        if source is not None:
            try:
                source.release()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# JobRunner: управляет пулом, watcher'ами, синхронизацией в JobStore
# ---------------------------------------------------------------------------

class JobRunner:
    """Обёртка над ProcessPoolExecutor + синхронизация прогресса в JobStore."""

    def __init__(self, store, model_path: str, max_workers: int = 2):
        self._store = store
        self._model_path = model_path
        self._executor = ProcessPoolExecutor(max_workers=max_workers)
        # Manager нужен для Manager.dict (разделяемая память между процессами).
        # Создаём лениво — чтобы не плодить процесс, если задач нет.
        self._manager: Optional[mp.Manager] = None
        self._progress: Optional["mp.Manager.dict"] = None  # type: ignore[valid-type]
        self._futures: dict[str, Future] = {}
        self._lock = threading.RLock()

    # --- lifecycle ---

    def _ensure_manager(self) -> None:
        if self._manager is None:
            self._manager = mp.Manager()
            self._progress = self._manager.dict()

    def shutdown(self) -> None:
        with self._lock:
            self._executor.shutdown(wait=False, cancel_futures=True)
            if self._manager is not None:
                self._manager.shutdown()

    # --- submit ---

    def submit(
        self,
        *,
        job_id: str,
        input_path: Path,
        output_dir: Path,
        lines_config: dict,
    ) -> None:
        self._ensure_manager()
        assert self._progress is not None

        output_dir.mkdir(parents=True, exist_ok=True)

        future = self._executor.submit(
            _worker_run_job,
            job_id=job_id,
            input_path=str(input_path),
            output_dir=str(output_dir),
            lines_config=lines_config,
            model_path=self._model_path,
            progress=self._progress,
        )
        with self._lock:
            self._futures[job_id] = future

        # watcher-поток: синхронизирует прогресс и финализирует статус
        threading.Thread(
            target=self._watch,
            args=(job_id, future),
            daemon=True,
            name=f"job-watch-{job_id}",
        ).start()

    # --- watcher ---

    def _watch(self, job_id: str, future: Future) -> None:
        """Раз в секунду подтягивает прогресс; по завершении — финализирует."""
        assert self._progress is not None

        while not future.done():
            self._sync_progress(job_id)
            time.sleep(1.0)
        self._sync_progress(job_id)  # финальный тик

        try:
            payload = future.result()
        except Exception as exc:  # noqa: BLE001
            payload = {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }

        self._finalize(job_id, payload)

        with self._lock:
            self._futures.pop(job_id, None)

    def _sync_progress(self, job_id: str) -> None:
        assert self._progress is not None
        raw = self._progress.get(job_id)
        if not raw:
            return
        job = self._store.get(job_id)
        if job is None or job.status != JobStatus.RUNNING:
            return
        job.progress = JobProgress(
            frames_done=int(raw.get("frames_done", 0)),
            frames_total=int(raw.get("frames_total", 0)),
            fps_avg=float(raw.get("fps_avg", 0.0)),
        )
        self._store.save(job)

    def _finalize(self, job_id: str, payload: dict) -> None:
        job = self._store.get(job_id)
        if job is None:
            return
        job.finished_at = datetime.utcnow()

        if payload.get("ok"):
            job.status = JobStatus.DONE
            job.result = JobResult(
                output_video=payload.get("output_video"),
                report_json=payload.get("report_json"),
                events_csv=payload.get("events_csv"),
                intensity_png=payload.get("intensity_png"),
            )
        else:
            job.status = JobStatus.FAILED
            job.error_message = payload.get("error", "unknown error")
            if settings.debug:
                job.error_message += "\n" + (payload.get("traceback") or "")

        self._store.save(job)


# ---------------------------------------------------------------------------
# Синглтон (инициализируется в app.main при старте)
# ---------------------------------------------------------------------------

_runner: Optional[JobRunner] = None


def init_runner(store) -> JobRunner:
    global _runner
    _runner = JobRunner(
        store=store,
        model_path=settings.model_path,
        max_workers=settings.max_workers,
    )
    return _runner


def get_runner() -> JobRunner:
    if _runner is None:
        raise RuntimeError("JobRunner не инициализирован")
    return _runner


def shutdown_runner() -> None:
    global _runner
    if _runner is not None:
        _runner.shutdown()
        _runner = None
