"""Обёртка над YOLO: загрузка модели + track → list[Track].

Заменяет inline-логику из pipeline.py:
    model = YOLO(...)
    results = model.track(...)
    tracks = results_to_tracks(results)
"""
from __future__ import annotations

from typing import Optional

import numpy as np
from ultralytics import YOLO

from . import config as core_config
from tracking.types import Track


class Detector:
    """YOLO + ByteTrack за одним фасадом.

    Не потокобезопасен (как и сам YOLO) — один экземпляр на процесс/поток.
    """

    def __init__(
        self,
        model_path: str,
        *,
        tracker_cfg: str = core_config.TRACKER_CFG,
        conf: float = core_config.CONF_THRESHOLD,
        iou: float = core_config.IOU_THRESHOLD,
        person_class_id: int = core_config.PERSON_CLASS_ID,
    ):
        self.model_path = model_path
        self.tracker_cfg = tracker_cfg
        self.conf = conf
        self.iou = iou
        self.person_class_id = person_class_id
        self._model: Optional[YOLO] = None

    # --- lifecycle ---

    def load(self) -> None:
        """Явная загрузка весов (можно звать заранее, чтобы прогреть)."""
        if self._model is None:
            self._model = YOLO(self.model_path)

    @property
    def model(self) -> YOLO:
        if self._model is None:
            self.load()
        return self._model

    # --- основной вызов ---

    def track(self, frame: np.ndarray) -> list[Track]:
        """Прогон кадра через YOLO.track + адаптация к list[Track]."""
        results = self.model.track(
            frame,
            persist=True,
            tracker=self.tracker_cfg,
            conf=self.conf,
            iou=self.iou,
            classes=[self.person_class_id],
            verbose=False,
        )
        return self.results_to_tracks(results)

    # --- адаптер ---

    @staticmethod
    def results_to_tracks(results) -> list[Track]:
        """Ultralytics Results → list[Track] (единый контракт)."""
        if not results:
            return []
        boxes = results[0].boxes
        if boxes is None or boxes.id is None:
            return []
        xyxy = boxes.xyxy.cpu().numpy()
        ids = boxes.id.cpu().numpy().astype(int)
        confs = boxes.conf.cpu().numpy()
        return [
            Track(
                track_id=int(tid),
                bbox=(float(x1), float(y1), float(x2), float(y2)),
                confidence=float(conf),
            )
            for (x1, y1, x2, y2), tid, conf in zip(xyxy, ids, confs)
        ]
