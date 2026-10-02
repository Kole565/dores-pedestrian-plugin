from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

import config


class FileSource:
    """Обёртка над cv2.VideoCapture для файлов (mp4/avi/...)."""

    def __init__(self, path: str):
        self.path = str(path)
        self._cap: Optional[cv2.VideoCapture] = None

    # --- жизненный цикл ---

    def open(self) -> bool:
        self._cap = cv2.VideoCapture(self.path)
        return bool(self._cap.isOpened())

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self._cap is None:
            return False, None
        return self._cap.read()

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    # --- свойства ---

    def get(self, prop: int) -> float:
        if self._cap is None:
            return 0.0
        return float(self._cap.get(prop))

    @property
    def is_live(self) -> bool:
        return False

    @property
    def width(self) -> int:
        return int(self.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def height(self) -> int:
        return int(self.get(cv2.CAP_PROP_FRAME_HEIGHT))

    @property
    def fps(self) -> float:
        return self.get(cv2.CAP_PROP_FPS) or float(config.OUTPUT_FPS_FALLBACK)

    @property
    def frame_count(self) -> int:
        return int(self.get(cv2.CAP_PROP_FRAME_COUNT))
