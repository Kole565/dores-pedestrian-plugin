"""CRUD конфигов линий + подложка-кадр для редактора."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import cv2
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from ..deps import get_lines_store, get_store
from ..lines_store import LinesStore
from ..schemas import (
    FrameSource,
    LinesConfig,
    LinesConfigCreate,
    LinesConfigListResponse,
    LinesConfigPatch,
    LinesConfigUpdate,
)
from ..settings import settings
from ..store import JobStore

logger = logging.getLogger("app.lines")
router = APIRouter(prefix="/api/lines", tags=["lines"])

# ---------------------------------------------------------------------------
# GET /api/lines/frame — подложка для редактора
# ---------------------------------------------------------------------------

_MAX_FRAME_WIDTH = 1920
_JPEG_QUALITY = 85


@router.get("/frame")
def get_frame(
    source: FrameSource = Query(..., description="upload или stream"),
    id: str = Query(..., description="job_id или stream_id"),
    t_sec: float = Query(0.0, ge=0.0, description="Секунда от начала (для upload)"),
    jobs: JobStore = Depends(get_store),
) -> Response:
    """Возвращает JPEG-кадр для редактора линий.

    - source=upload: берём файл из data/uploads/{id}.{ext},
      читаем кадр на секунде t_sec (по умолчанию — первый).
    - source=stream: этап E; пока 501.

    Возвращает image/jpeg. В заголовках — X-Frame-Width / X-Frame-Height,
    чтобы клиент знал реальный размер кадра.
    """
    if source == FrameSource.STREAM:
        raise HTTPException(
            status_code=501,
            detail="source=stream появится на этапе E",
        )

    # --- upload ---
    job = jobs.get(id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job не найден")

    video_path = _find_upload_file(id)
    if video_path is None:
        raise HTTPException(status_code=404, detail="Видеофайл не найден на диске")

    frame = _read_frame(video_path, t_sec)
    if frame is None:
        raise HTTPException(
            status_code=422,
            detail=f"Не удалось прочитать кадр на t={t_sec}s",
        )

    frame = _downscale_if_needed(frame)

    ok, buf = cv2.imencode(
        ".jpg", frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), _JPEG_QUALITY],
    )
    if not ok:
        raise HTTPException(status_code=500, detail="JPEG-энкодинг не удался")

    h, w = frame.shape[:2]
    return Response(
        content=buf.tobytes(),
        media_type="image/jpeg",
        headers={
            "X-Frame-Width": str(w),
            "X-Frame-Height": str(h),
            "Cache-Control": "no-store",
        },
    )

# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=LinesConfigListResponse)
def list_lines(store: LinesStore = Depends(get_lines_store)) -> LinesConfigListResponse:
    return LinesConfigListResponse(configs=store.list())


@router.post("", response_model=LinesConfig, status_code=201)
def create_lines(
    payload: LinesConfigCreate,
    store: LinesStore = Depends(get_lines_store),
) -> LinesConfig:
    return store.create(payload)


@router.get("/{config_id}", response_model=LinesConfig)
def get_lines(
    config_id: str,
    store: LinesStore = Depends(get_lines_store),
) -> LinesConfig:
    cfg = store.get(config_id)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Конфиг не найден")
    return cfg


@router.put("/{config_id}", response_model=LinesConfig)
def replace_lines(
    config_id: str,
    payload: LinesConfigUpdate,
    store: LinesStore = Depends(get_lines_store),
) -> LinesConfig:
    updated = store.replace(config_id, LinesConfigCreate(**payload.model_dump()))
    if updated is None:
        raise HTTPException(status_code=404, detail="Конфиг не найден")
    return updated


@router.patch("/{config_id}", response_model=LinesConfig)
def patch_lines(
    config_id: str,
    payload: LinesConfigPatch,
    store: LinesStore = Depends(get_lines_store),
) -> LinesConfig:
    updated = store.patch(config_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Конфиг не найден")
    return updated


@router.delete("/{config_id}", status_code=204)
def delete_lines(
    config_id: str,
    store: LinesStore = Depends(get_lines_store),
) -> None:
    if not store.delete(config_id):
        raise HTTPException(status_code=404, detail="Конфиг не найден")
    return None



def _find_upload_file(job_id: str) -> Optional[Path]:
    for ext in settings.allowed_video_ext:
        p = settings.uploads_dir / f"{job_id}{ext}"
        if p.exists():
            return p
    return None


def _read_frame(video_path: Path, t_sec: float):
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return None
    try:
        if t_sec > 0:
            cap.set(cv2.CAP_PROP_POS_MSEC, t_sec * 1000.0)
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


def _downscale_if_needed(frame):
    h, w = frame.shape[:2]
    if w <= _MAX_FRAME_WIDTH:
        return frame
    scale = _MAX_FRAME_WIDTH / w
    new_size = (int(w * scale), int(h * scale))
    return cv2.resize(frame, new_size, interpolation=cv2.INTER_AREA)
