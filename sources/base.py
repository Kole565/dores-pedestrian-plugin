# sources/base.py
from __future__ import annotations

from typing import Optional, Protocol, Tuple, runtime_checkable

import cv2
import numpy as np


@runtime_checkable
class VideoSource(Protocol):
    """Единый контракт источника кадров.

    Реализации: FileSource, Mot17Source, RTSPSource.
    Позволяет pipeline/core работать с любым источником одинаково.
    """

    # --- жизненный цикл ---
    def open(self) -> bool: ...
    def read(self) -> Tuple[bool, Optional[np.ndarray]]: ...
    def release(self) -> None: ...

    # --- свойства кадра ---
    def get(self, prop: int) -> float: ...

    # --- мета ---
    @property
    def is_live(self) -> bool:
        """True для RTSP/камеры (нет конечного frame_count, нужен reconnect)."""
        ...

    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    @property
    def fps(self) -> float: ...
    @property
    def frame_count(self) -> int:
        """0 для live-источников."""
        ...
