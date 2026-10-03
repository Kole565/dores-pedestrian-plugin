"""Отдельный upload-эндпоинт: сохранить видео без запуска обработки.

Нужен редактору линий: чтобы нарисовать линии, достаточно первого кадра.

Файлы помечаются префиксом `up_`, чтобы не путаться с input-файлами
offline-задач (те создаются в той же директории без префикса).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from ..schemas import UploadInfo
from ..settings import settings

logger = logging.getLogger("app.uploads")
router = APIRouter(prefix="/api/uploads", tags=["uploads"])

UPLOAD_PREFIX = "up_"


@router.post("", response_model=UploadInfo, status_code=201)
async def create_upload(
    file: Annotated[UploadFile, File(description="Видеофайл")],
) -> UploadInfo:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in settings.allowed_video_ext:
        raise HTTPException(
            status_code=400,
            detail=f"Недопустимое расширение '{ext}'",
        )

    upload_id = uuid.uuid4().hex[:12]
    path = settings.uploads_dir / f"{UPLOAD_PREFIX}{upload_id}{ext}"

    written = 0
    try:
        with path.open("wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.max_upload_bytes:
                    out.close()
                    path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"Файл превышает лимит {settings.max_upload_bytes} байт",
                    )
                out.write(chunk)
    except HTTPException:
        raise
    except OSError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Ошибка записи: {exc}")

    logger.info(
        "upload saved: id=%s size=%d ext=%s name=%r",
        upload_id, written, ext, file.filename,
    )

    return UploadInfo(
        id=upload_id,
        filename=file.filename or path.name,
        size_bytes=written,
        created_at=datetime.utcnow(),
    )


@router.delete("/{upload_id}", status_code=204)
def delete_upload(upload_id: str) -> None:
    for ext in settings.allowed_video_ext:
        p = settings.uploads_dir / f"{UPLOAD_PREFIX}{upload_id}{ext}"
        if p.exists():
            p.unlink()
            logger.info("upload deleted: id=%s", upload_id)
            return None
    raise HTTPException(status_code=404, detail="Upload не найден")
