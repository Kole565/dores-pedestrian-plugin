# reporting/video_writer.py
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class AnnotatedVideoWriter:
    """Обёртка над cv2.VideoWriter с context-manager."""

    def __init__(
        self,
        out_path: Path,
        fps: float,
        size: tuple[int, int],
        fourcc: str = "mp4v",
    ):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self.out_path = out_path
        self._writer = cv2.VideoWriter(
            str(out_path),
            cv2.VideoWriter_fourcc(*fourcc),
            fps,
            size,
        )
        if not self._writer.isOpened():
            raise RuntimeError(f"Не удалось открыть VideoWriter: {out_path}")

    def write(self, frame: np.ndarray) -> None:
        self._writer.write(frame)

    def close(self) -> None:
        self._writer.release()

    def __enter__(self) -> "AnnotatedVideoWriter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
