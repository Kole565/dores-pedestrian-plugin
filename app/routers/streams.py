"""Эндпоинты real-time-сессий: create, list, get, snapshot, delete."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from ..deps import get_lines_store, get_manager
from ..lines_store import LinesStore
from ..schemas import (
    StreamCreate,
    StreamInfo,
    StreamListResponse,
    StreamStatus,
)
from ..streams import StreamManager

logger = logging.getLogger("app.streams.api")
router = APIRouter(prefix="/api/streams", tags=["streams"])


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _validate_rtsp_url(url: str) -> None:
    if not url.startswith(("rtsp://", "rtsps://")):
        raise HTTPException(
            status_code=400,
            detail="URL должен начинаться с rtsp:// или rtsps://",
        )


def _resolve_lines_config(
    *,
    inline: dict | None,
    config_id: str | None,
    lines_store: LinesStore,
) -> dict:
    """dict {'VIRTUAL_LINES': [...]} — формат pipeline."""
    if inline is not None:
        if "VIRTUAL_LINES" not in inline:
            raise HTTPException(
                status_code=400,
                detail="lines_config: ожидается ключ 'VIRTUAL_LINES'",
            )
        return inline

    if config_id:
        cfg = lines_store.get(config_id)
        if cfg is None:
            raise HTTPException(
                status_code=404,
                detail=f"lines_config_id={config_id} не найден",
            )
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

    from core import config as core_config
    return {"VIRTUAL_LINES": core_config.DEFAULT_VIRTUAL_LINES}


# ---------------------------------------------------------------------------
# POST /api/streams
# ---------------------------------------------------------------------------

@router.post("", response_model=StreamInfo, status_code=201)
def create_stream(
    payload: StreamCreate,
    manager: StreamManager = Depends(get_manager),
    lines_store: LinesStore = Depends(get_lines_store),
) -> StreamInfo:
    _validate_rtsp_url(payload.rtsp_url)

    lines_config = _resolve_lines_config(
        inline=payload.lines_config,
        config_id=payload.lines_config_id,
        lines_store=lines_store,
    )

    stream_id = uuid.uuid4().hex[:12]
    try:
        session = manager.create(
            stream_id=stream_id,
            rtsp_url=payload.rtsp_url,
            lines_config_id=payload.lines_config_id,
            lines_config=lines_config,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Не удалось создать stream")
        raise HTTPException(status_code=500, detail=str(exc))

    return session.to_info()


# ---------------------------------------------------------------------------
# GET /api/streams
# ---------------------------------------------------------------------------

@router.get("", response_model=StreamListResponse)
def list_streams(manager: StreamManager = Depends(get_manager)) -> StreamListResponse:
    return StreamListResponse(streams=[s.to_info() for s in manager.list()])


# ---------------------------------------------------------------------------
# GET /api/streams/{id}
# ---------------------------------------------------------------------------

@router.get("/{stream_id}", response_model=StreamInfo)
def get_stream(
    stream_id: str,
    manager: StreamManager = Depends(get_manager),
) -> StreamInfo:
    session = manager.get(stream_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Stream не найден")
    return session.to_info()


# ---------------------------------------------------------------------------
# GET /api/streams/{id}/snapshot.jpg
# ---------------------------------------------------------------------------

@router.get("/{stream_id}/snapshot.jpg")
def get_snapshot(
    stream_id: str,
    manager: StreamManager = Depends(get_manager),
) -> Response:
    session = manager.get(stream_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Stream не найден")
    jpeg = session.get_snapshot()
    if jpeg is None:
        raise HTTPException(
            status_code=409,
            detail="Кадр ещё не получен (стрим только запускается?)",
        )
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


# ---------------------------------------------------------------------------
# DELETE /api/streams/{id}
# ---------------------------------------------------------------------------

@router.delete("/{stream_id}", status_code=204)
def delete_stream(
    stream_id: str,
    manager: StreamManager = Depends(get_manager),
) -> None:
    session = manager.get(stream_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Stream не найден")
    manager.delete(stream_id)
    return None


@router.post("/{stream_id}/stop", response_model=StreamInfo)
def stop_stream(
    stream_id: str,
    manager: StreamManager = Depends(get_manager),
) -> StreamInfo:
    session = manager.get(stream_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Stream не найден")
    session.stop()
    return session.to_info()
