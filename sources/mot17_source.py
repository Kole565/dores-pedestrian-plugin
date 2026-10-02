from __future__ import annotations

import configparser
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

import config


class Mot17Source:
    """Источник для MOT17-последовательности (папка img1/*.jpg).

    Совместим с контрактом VideoSource.
    """

    def __init__(self, seq_dir: str):
        self.seq_dir = Path(seq_dir)

        cp = configparser.ConfigParser()
        cp.read(self.seq_dir / "seqinfo.ini")
        s = cp["Sequence"]

        self.im_dir = self.seq_dir / s["imDir"]
        self.ext = s["imExt"]
        self._fps = float(s["frameRate"])
        self._width = int(s["imWidth"])
        self._height = int(s["imHeight"])

        self.frames: list[Path] = []
        self._idx = 0

    # --- жизненный цикл ---

    def open(self) -> bool:
        self.frames = sorted(self.im_dir.glob(f"*{self.ext}"))
        self._idx = 0
        return len(self.frames) > 0

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if self._idx >= len(self.frames):
            return False, None
        img = cv2.imread(str(self.frames[self._idx]))
        self._idx += 1
        return (img is not None), img

    def release(self) -> None:
        self.frames = []
        self._idx = 0

    # --- свойства ---

    def get(self, prop: int) -> float:
        if prop == cv2.CAP_PROP_FRAME_WIDTH:  return float(self._width)
        if prop == cv2.CAP_PROP_FRAME_HEIGHT: return float(self._height)
        if prop == cv2.CAP_PROP_FPS:          return self._fps
        if prop == cv2.CAP_PROP_FRAME_COUNT:  return float(len(self.frames))
        return 0.0

    @property
    def is_live(self) -> bool:
        return False

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def fps(self) -> float:
        return self._fps or float(config.OUTPUT_FPS_FALLBACK)

    @property
    def frame_count(self) -> int:
        return len(self.frames)
