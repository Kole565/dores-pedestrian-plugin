"""Эндпоинты offline-задач: upload, list, get, result, delete."""
from __future__ import annotations

import json
import logging
import shutil
import uuid
import zipfile
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..deps import get_lines_store, get_runner, get_store
from ..lines_store import LinesStore

from ..jobs import JobRunner
from ..schemas import (
    JobInfo,
    JobListResponse,
    JobStatus,
    LinesConfig,
)
from ..settings import settings
from ..store import JobStore


logger = logging.getLogger("app.jobs")
router = APIRouter(prefix="/api/jobs", tags=["jobs"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _ext_of(filename: str) -> str:
    return Path(filename).suffix.lower()


def _validate_upload(file: UploadFile) -> str:
    ext = _ext_of(file.filename or "")
    if ext not in settings.allowed_video_ext:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Недопустимое расширение '{ext}'. "
                f"Разрешены: {', '.join(settings.allowed_video_ext)}"
            ),
        )
    return ext


def _job_output_dir(job_id: str) -> Path:
    return settings.results_dir / job_id


def _job_input_path(job_id: str, ext: str) -> Path:
    return settings.uploads_dir / f"{job_id}{ext}"

def _ensure_web_playable(job_id: str) -> Path | None:
    """Гарантирует наличие annotated_web.mp4 (H.264, faststart) для <video>.

    cv2.VideoWriter с fourcc='mp4v' (MPEG-4 Part 2) браузеры не играют.
    Перекодируем в H.264 лениво, при первом запросе файла.
    """
    src = _job_output_dir(job_id) / "annotated.mp4"
    if not src.exists():
        return None

    dst = _job_output_dir(job_id) / "annotated_web.mp4"
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst

    if shutil.which("ffmpeg") is None:
        logger.warning(
            "ffmpeg не найден в PATH — annotated.mp4 останется в mp4v "
            "и не будет играть в браузере"
        )
        return None

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-an",
        str(dst),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=600)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        logger.exception("ffmpeg перекодировка не удалась: %s", exc)
        dst.unlink(missing_ok=True)
        return None
    return dst

# ---------------------------------------------------------------------------
# POST /api/jobs — upload + submit
# ---------------------------------------------------------------------------

@router.post("", response_model=JobInfo, status_code=201)
async def create_job(
    file: Annotated[UploadFile, File(description="Видеофайл")],
    lines_config_id: Annotated[str | None, Form()] = None,
    lines_config: Annotated[str | None, Form(
        description="JSON-строка конфига линий (если не задан lines_config_id)"
    )] = None,
    store: JobStore = Depends(get_store),
    runner: JobRunner = Depends(get_runner),
    lines_store: LinesStore = Depends(get_lines_store),
) -> JobInfo:

    """Загрузить видео и поставить задачу в очередь.

    Приоритет конфига линий:
      1. lines_config (JSON-строка)
      2. lines_config_id (этап D — CRUD /api/lines)
      3. дефолт из core.config.DEFAULT_VIRTUAL_LINES
    """
    ext = _validate_upload(file)

    # --- сохраняем файл ---
    job_id = uuid.uuid4().hex[:12]
    input_path = _job_input_path(job_id, ext)
    try:
        written = 0
        with input_path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    out.close()
                    input_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"Файл превышает лимит "
                            f"{settings.max_upload_bytes} байт"
                        ),
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except OSError as exc:
        input_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Ошибка записи: {exc}")

    # --- конфиг линий ---
    resolved_lines = _resolve_lines_config(
        inline_json=lines_config,
        config_id=lines_config_id,
        lines_store=lines_store,
    )

    # --- JobInfo ---
    job = JobInfo(
        id=job_id,
        status=JobStatus.PENDING,
        created_at=datetime.utcnow(),
        input_filename=file.filename or input_path.name,
        lines_config_id=lines_config_id,
    )
    store.save(job)

    # --- статус running и submit ---
    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()
    store.save(job)

    try:
        runner.submit(
            job_id=job_id,
            input_path=input_path,
            output_dir=_job_output_dir(job_id),
            lines_config=resolved_lines,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Не удалось поставить задачу в очередь")
        job.status = JobStatus.FAILED
        job.error_message = f"submit failed: {exc}"
        job.finished_at = datetime.utcnow()
        store.save(job)
        raise HTTPException(status_code=500, detail=str(exc))

    return job


def _lines_config_to_pipeline_format(cfg: LinesConfig) -> dict:
    """LinesConfig (API) → {'VIRTUAL_LINES': [{'line_id':..., 'coords': (...)}, ...]}.

    Pipeline ожидает именно такой формат (как в core/config.py).
    """
    return {
        "VIRTUAL_LINES": [
            {
                "line_id": ln.line_id,
                "coords": tuple(ln.coords),
                "direction_pos_to_neg": ln.direction_pos_to_neg,
                "direction_neg_to_pos": ln.direction_neg_to_pos,
                "use_point": ln.use_point,
            }
            for ln in cfg.lines
        ]
    }

def _resolve_lines_config(
    *,
    inline_json: str | None,
    config_id: str | None,
    lines_store: LinesStore,
) -> dict:
    """Определяет итоговый конфиг линий для задачи.

    Приоритет:
      1. inline_json (JSON-строка в multipart)
      2. config_id  (CRUD /api/lines)
      3. дефолт     (core.config.DEFAULT_VIRTUAL_LINES)
    """
    # 1. inline
    if inline_json:
        try:
            data = json.loads(inline_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"lines_config: некорректный JSON ({exc})",
            )
        if "VIRTUAL_LINES" not in data:
            raise HTTPException(
                status_code=400,
                detail="lines_config: ожидается ключ 'VIRTUAL_LINES'",
            )
        return data

    # 2. config_id
    if config_id:
        cfg = lines_store.get(config_id)
        if cfg is None:
            raise HTTPException(
                status_code=404,
                detail=f"lines_config_id={config_id} не найден",
            )
        return _lines_config_to_pipeline_format(cfg)

    # 3. дефолт
    from core import config as core_config
    return {"VIRTUAL_LINES": core_config.DEFAULT_VIRTUAL_LINES}

# ---------------------------------------------------------------------------
# GET /api/jobs — список
# ---------------------------------------------------------------------------

@router.get("", response_model=JobListResponse)
def list_jobs(store: JobStore = Depends(get_store)) -> JobListResponse:
    return JobListResponse(jobs=store.list())


# ---------------------------------------------------------------------------
# GET /api/jobs/{id} — статус
# ---------------------------------------------------------------------------

@router.get("/{job_id}", response_model=JobInfo)
def get_job(job_id: str, store: JobStore = Depends(get_store)) -> JobInfo:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job не найден")
    return job


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}/result — zip с артефактами
# ---------------------------------------------------------------------------

@router.get("/{job_id}/result")
def get_job_result(
    job_id: str,
    store: JobStore = Depends(get_store),
) -> FileResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job не найден")
    if job.status != JobStatus.DONE:
        raise HTTPException(
            status_code=409,
            detail=f"Job в статусе '{job.status.value}', результат недоступен",
        )

    out_dir = _job_output_dir(job_id)
    if not out_dir.exists():
        raise HTTPException(status_code=404, detail="Директория результатов пуста")

    # собираем zip (кешируем на диск)
    zip_path = settings.results_dir / f"{job_id}.zip"
    if not zip_path.exists() or zip_path.stat().st_mtime < _latest_mtime(out_dir):
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(out_dir.rglob("*")):
                if p.is_file() and not p.name.endswith("_web.mp4"):
                    zf.write(p, arcname=p.relative_to(out_dir))

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"{job_id}.zip",
    )


def _latest_mtime(directory: Path) -> float:
    latest = 0.0
    for p in directory.rglob("*"):
        if p.is_file():
            latest = max(latest, p.stat().st_mtime)
    return latest


# ---------------------------------------------------------------------------
# GET /api/jobs/{id}/files/{name} — отдельный артефакт
# ---------------------------------------------------------------------------

_ALLOWED_ARTIFACTS = {
    "annotated.mp4": "video/mp4",
    "report.json": "application/json",
    "events.csv": "text/csv",
    "intensity.png": "image/png",
}


@router.get("/{job_id}/files/{name}")
def get_job_file(
    job_id: str,
    name: str,
    store: JobStore = Depends(get_store),
) -> FileResponse:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job не найден")
    if job.status != JobStatus.DONE:
        raise HTTPException(status_code=409, detail="Результат ещё не готов")
    if name not in _ALLOWED_ARTIFACTS:
        raise HTTPException(status_code=404, detail="Артефакт не найден")

    # --- специальный случай: видео → web-версия H.264 ---
    if name == "annotated.mp4":
        web = _ensure_web_playable(job_id)
        if web is not None:
            return FileResponse(
                web,
                media_type="video/mp4",
                filename="annotated.mp4",
                headers={"Accept-Ranges": "bytes"},
            )
        # ffmpeg недоступен — отдаём как есть, но хотя бы с правильным
        # content-type, чтобы браузер не путался
        logger.warning(
            "Отдаём annotated.mp4 без перекодировки — в браузере не заиграет"
        )

    path = _job_output_dir(job_id) / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Файл отсутствует на диске")

    return FileResponse(
        path,
        media_type=_ALLOWED_ARTIFACTS[name],
        filename=name,
        headers={"Accept-Ranges": "bytes"} if name.endswith(".mp4") else None,
    )

# ---------------------------------------------------------------------------
# DELETE /api/jobs/{id}
# ---------------------------------------------------------------------------

@router.delete("/{job_id}", status_code=204)
def delete_job(
    job_id: str,
    store: JobStore = Depends(get_store),
) -> None:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job не найден")
    if job.status == JobStatus.RUNNING:
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить running-задачу (остановка — этап E)",
        )

    # чистим диск
    _job_output_dir(job_id).exists() and shutil.rmtree(
        _job_output_dir(job_id), ignore_errors=True
    )
    (settings.results_dir / f"{job_id}.zip").unlink(missing_ok=True)
    for ext in settings.allowed_video_ext:
        (settings.uploads_dir / f"{job_id}{ext}").unlink(missing_ok=True)

    store.delete(job_id)
    return None
