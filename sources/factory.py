from __future__ import annotations

from pathlib import Path
from typing import Literal, Union

from .base import VideoSource
from .file_source import FileSource
from .mot17_source import Mot17Source
from .rtsp_source import RTSPSource

Kind = Literal["auto", "file", "rtsp", "mot17"]


def open_source(uri: str, kind: Kind = "auto") -> VideoSource:
    """Создаёт и открывает источник по URI.

    kind="auto" определяет тип:
      - rtsp://, rtsps://       → RTSPSource
      - папка с seqinfo.ini     → Mot17Source
      - всё остальное           → FileSource
    """
    resolved = _resolve_kind(uri) if kind == "auto" else kind

    if resolved == "rtsp":
        src = RTSPSource(uri)
    elif resolved == "mot17":
        src = Mot17Source(uri)
    elif resolved == "file":
        src = FileSource(uri)
    else:
        raise ValueError(f"Неизвестный тип источника: {resolved}")

    if not src.open():
        # RTSP сам ретраит; для file/mot17 — сразу ошибка
        if resolved != "rtsp":
            raise RuntimeError(f"Не удалось открыть источник: {uri}")
    return src


def _resolve_kind(uri: str) -> Kind:
    if uri.startswith(("rtsp://", "rtsps://")):
        return "rtsp"
    p = Path(uri)
    if p.is_dir() and (p / "seqinfo.ini").exists():
        return "mot17"
    return "file"
