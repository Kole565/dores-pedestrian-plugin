from __future__ import annotations

import logging
import os
import time
from typing import Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class RTSPSource:
    """Источник RTSP с авто-reconnect и защитой от накопления буфера.

    Особенности:
      - backoff при переподключении (экспоненциальный, с потолком);
      - CAP_PROP_BUFFERSIZE=1 — читаем «свежий» кадр, а не из очереди;
      - таймаут открытия (RTSP может «висеть»);
      - health-check: если кадров нет дольше stale_timeout — reconnect;
      - опциональный FFmpeg-бэкенд (OpenCV CAP_FFMPEG) + TCP-транспорт.
    """

    def __init__(
        self,
        url: str,
        *,
        open_timeout_sec: float = 10.0,
        read_timeout_sec: float = 5.0,
        stale_timeout_sec: float = 5.0,
        backoff_initial: float = 1.0,
        backoff_max: float = 30.0,
        prefer_ffmpeg: bool = True,
        rtsp_transport: str = "tcp",
    ):
        self.url = url
        self.open_timeout_sec = open_timeout_sec
        self.read_timeout_sec = read_timeout_sec
        self.stale_timeout_sec = stale_timeout_sec
        self.backoff_initial = backoff_initial
        self.backoff_max = backoff_max
        self.prefer_ffmpeg = prefer_ffmpeg
        self.rtsp_transport = rtsp_transport

        self._cap: Optional[cv2.VideoCapture] = None
        self._backoff = backoff_initial
        self._last_frame_ts: float = 0.0
        self._last_ok: bool = False

    # ------------------------------------------------------------ lifecycle

    def open(self) -> bool:
        """Пытается открыть поток. Возвращает True/False, не бросает."""
        return self._try_open()

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Читает кадр. При сбое/таймауте сам переподключается.

        Возвращает (False, None), пока не восстановится связь —
        это сигнал вызывающему коду «пропустить кадр», а не «конец видео».
        """
        if self._cap is None:
            if not self._try_open():
                return False, None

        ok, frame = self._cap.read()

        now = time.time()
        if ok and frame is not None:
            self._last_frame_ts = now
            self._last_ok = True
            self._backoff = self.backoff_initial  # успех → сброс backoff
            return True, frame

        # --- неудача чтения ---
        self._last_ok = False
        # health-check: если давно не было кадров — точно reconnect
        if now - self._last_frame_ts > self.stale_timeout_sec:
            logger.warning("RTSP stale > %.1fs, reconnect: %s",
                           self.stale_timeout_sec, self._safe_url())
            self._reconnect()
        else:
            # разовый сбой — попробуем ещё раз на следующем кадре
            logger.debug("RTSP read failed (short), will retry")
        return False, None

    def release(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    # ------------------------------------------------------------ properties

    def get(self, prop: int) -> float:
        if self._cap is None:
            return 0.0
        return float(self._cap.get(prop))

    @property
    def is_live(self) -> bool:
        return True

    @property
    def width(self) -> int:
        return int(self.get(cv2.CAP_PROP_FRAME_WIDTH))

    @property
    def height(self) -> int:
        return int(self.get(cv2.CAP_PROP_FRAME_HEIGHT))

    @property
    def fps(self) -> float:
        fps = self.get(cv2.CAP_PROP_FPS)
        # у RTSP часто 0/25/30 — отдаём как есть, fallback в pipeline
        return fps if fps > 0 else 0.0

    @property
    def frame_count(self) -> int:
        return 0  # live — бесконечный

    # ------------------------------------------------------------ internals

    def _try_open(self) -> bool:
        self.release()

        # FFmpeg-параметры: TCP + низкий latency
        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS",
            f"rtsp_transport;{self.rtsp_transport}|stimeout;{int(self.open_timeout_sec * 1e6)}",
        )

        api = cv2.CAP_FFMPEG if self.prefer_ffmpeg else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.url, api)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)         # не копим кадры
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, int(self.open_timeout_sec * 1000))
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, int(self.read_timeout_sec * 1000))

        if not cap.isOpened():
            cap.release()
            logger.warning("RTSP open failed: %s", self._safe_url())
            self._sleep_backoff()
            return False

        self._cap = cap
        self._last_frame_ts = time.time()
        logger.info("RTSP opened: %s (%dx%d)",
                    self._safe_url(), self.width, self.height)
        return True

    def _reconnect(self) -> None:
        self._sleep_backoff()
        self._try_open()

    def _sleep_backoff(self) -> None:
        logger.info("RTSP backoff %.1fs", self._backoff)
        time.sleep(self._backoff)
        self._backoff = min(self._backoff * 2.0, self.backoff_max)

    def _safe_url(self) -> str:
        """Маскирует креды в URL для логов."""
        if "@" in self.url and "://" in self.url:
            scheme, rest = self.url.split("://", 1)
            _, host = rest.split("@", 1)
            return f"{scheme}://***@{host}"
        return self.url
