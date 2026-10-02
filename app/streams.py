"""Stream Manager: процесс на стрим + IPC через очереди.

Архитектура:
  FastAPI-процесс
    └─ StreamManager
         ├─ StreamSession (per stream) — держит:
         │    ├─ multiprocessing.Process (воркер)
         │    ├─ frame_queue  ← воркер шлёт JPEG
         │    ├─ stats_queue  ← воркер шлёт статистику
         │    ├─ ctrl_queue   → воркер слушает stop
         │    ├─ snapshot_buf (последний JPEG для /snapshot.jpg)
         │    └─ WS-подписчики (asyncio.Queue на клиента)
         └─ StreamStore (JSON)
"""
from __future__ import annotations

import asyncio
import json
import logging
import multiprocessing as mp
import queue
import threading
import time
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from core.runner import run_stream
from core import config as core_config
from core.lines import line_from_dict
from sources.factory import open_source

from .schemas import (
    StreamInfo,
    StreamStats,
    StreamStatus,
)
from .settings import settings

logger = logging.getLogger("app.streams")


# ---------------------------------------------------------------------------
# Worker: тело процесса, читает RTSP, шлёт JPEG+stats в очереди
# ---------------------------------------------------------------------------

def _worker_run_stream(
    *,
    stream_id: str,
    rtsp_url: str,
    lines_config: dict,
    model_path: str,
    frame_queue: "mp.Queue",
    stats_queue: "mp.Queue",
    ctrl_queue: "mp.Queue",
    target_fps: float,
    jpeg_quality: int,
) -> None:
    """Воркер одного стрима.

    Посылает в frame_queue: bytes (JPEG)
    Посылает в stats_queue: dict {total, per_line, fps, active_tracks, frames_processed}
    Слушает ctrl_queue: {'cmd': 'stop'}
    """
    source = None
    try:
        source = open_source(rtsp_url, kind="rtsp")

        min_dt = 1.0 / target_fps if target_fps > 0 else 0.0
        last_sent = 0.0
        stop_flag = threading.Event()

        def _on_frame(canvas, frame_idx: int, timestamp: float) -> None:
            nonlocal last_sent
            now = time.time()
            if min_dt and (now - last_sent) < min_dt:
                return
            last_sent = now
            ok, buf = cv2.imencode(
                ".jpg", canvas,
                [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality],
            )
            if not ok:
                return
            try:
                frame_queue.put_nowait(buf.tobytes())
            except queue.Full:
                # дропаем старый кадр и пробуем ещё раз
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    frame_queue.put_nowait(buf.tobytes())
                except queue.Full:
                    pass

        def _on_stats(stats, fps: float, active: int, frame_idx: int) -> None:
            try:
                stats_queue.put_nowait({
                    "total": stats.total,
                    "per_line": {k: dict(v) for k, v in stats.per_line.items()},
                    "fps": round(fps, 2),
                    "active_tracks": active,
                    "frames_processed": frame_idx,       # ← новое
                })
            except queue.Full:
                pass

        def _stop_check() -> bool:
            # раз в вызов проверяем ctrl_queue
            try:
                msg = ctrl_queue.get_nowait()
                if msg.get("cmd") == "stop":
                    stop_flag.set()
            except queue.Empty:
                pass
            return stop_flag.is_set()

        run_stream(
            source,
            model_path=model_path,
            lines_config=lines_config,
            on_frame=_on_frame,
            on_stats=_on_stats,
            stats_every_sec=1.0,
            stop_check=_stop_check,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Stream worker %s error: %s", stream_id, exc)
        try:
            stats_queue.put_nowait({
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            })
        except queue.Full:
            pass
    finally:
        if source is not None:
            try:
                source.release()
            except Exception:
                pass
        # сигнал родителю, что мы закончили
        try:
            stats_queue.put_nowait({"__worker_exit__": True})
        except queue.Full:
            pass


# ---------------------------------------------------------------------------
# StreamSession: один стрим
# ---------------------------------------------------------------------------

@dataclass
class _WsSubscriber:
    """Подписчик WS на кадры/статистику."""
    queue: "asyncio.Queue[dict]"
    loop: asyncio.AbstractEventLoop = field(repr=False)


class StreamSession:
    """Обёртка над процессом-воркером + очереди + WS-подписчики."""

    def __init__(
        self,
        *,
        stream_id: str,
        rtsp_url: str,
        rtsp_url_masked: str,
        lines_config_id: Optional[str],
        lines_config: dict,
        model_path: str,
        target_fps: float = 10.0,
        jpeg_quality: int = 80,
    ):
        self.id = stream_id
        self.rtsp_url = rtsp_url
        self.rtsp_url_masked = rtsp_url_masked
        self.lines_config_id = lines_config_id
        self.lines_config = lines_config
        self.model_path = model_path
        self.target_fps = target_fps
        self.jpeg_quality = jpeg_quality

        # --- IPC ---
        self._frame_queue: "mp.Queue" = mp.Queue(maxsize=4)
        self._stats_queue: "mp.Queue" = mp.Queue(maxsize=32)
        self._ctrl_queue: "mp.Queue" = mp.Queue(maxsize=8)

        # --- процесс ---
        self._proc: Optional[mp.Process] = None

        # --- состояние (в родителе) ---
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.stopped_at: Optional[datetime] = None
        self.last_frame_at: Optional[datetime] = None
        self.status: StreamStatus = StreamStatus.STARTING
        self.error_message: Optional[str] = None
        self.stats: StreamStats = StreamStats()

        # --- последний JPEG (для snapshot) ---
        self._snapshot_lock = threading.Lock()
        self._last_jpeg: Optional[bytes] = None

        # --- WS-подписчики ---
        self._subscribers: list[_WsSubscriber] = []
        self._subscribers_lock = threading.Lock()

        # --- служебные потоки ---
        self._stop_event = threading.Event()
        self._pump_thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------ lifecycle

    def start(self) -> None:
        self._proc = mp.Process(
            target=_worker_run_stream,
            kwargs={
                "stream_id": self.id,
                "rtsp_url": self.rtsp_url,
                "lines_config": self.lines_config,
                "model_path": self.model_path,
                "frame_queue": self._frame_queue,
                "stats_queue": self._stats_queue,
                "ctrl_queue": self._ctrl_queue,
                "target_fps": self.target_fps,
                "jpeg_quality": self.jpeg_quality,
            },
            daemon=True,
            name=f"stream-{self.id}",
        )
        self._proc.start()
        self.started_at = datetime.utcnow()
        self.status = StreamStatus.RUNNING

        self._pump_thread = threading.Thread(
            target=self._pump, daemon=True, name=f"stream-pump-{self.id}",
        )
        self._pump_thread.start()

        logger.info("Stream %s started (pid=%s)", self.id, self._proc.pid)

    def stop(self, timeout: float = 5.0) -> None:
        """Мягкая остановка: ctrl-сообщение → join → terminate."""
        if self._stop_event.is_set():
            return
        self._stop_event.set()

        try:
            self._ctrl_queue.put_nowait({"cmd": "stop"})
        except queue.Full:
            pass

        if self._proc is not None:
            self._proc.join(timeout=timeout)
            if self._proc.is_alive():
                logger.warning("Stream %s: force terminate", self.id)
                self._proc.terminate()
                self._proc.join(timeout=2.0)

        self.status = StreamStatus.STOPPED
        self.stopped_at = datetime.utcnow()

        # будим WS-подписчиков статусом
        self._broadcast({"type": "status", "status": "stopped"})

    # ------------------------------------------------------------ pump

    def _pump(self) -> None:
        """Единый поток-насос: читает обе очереди, обновляет состояние и WS."""
        last_stats_ts = 0.0
        while not self._stop_event.is_set():
            # --- кадры ---
            got_frame = False
            try:
                jpeg = self._frame_queue.get_nowait()
                got_frame = True
            except queue.Empty:
                jpeg = None

            if got_frame and jpeg is not None:
                with self._snapshot_lock:
                    self._last_jpeg = jpeg
                self.last_frame_at = datetime.utcnow()
                # отправляем подписчикам (base64-строку готовит ws.py)
                self._broadcast_raw_frame(jpeg)

            # --- статистика ---
            drained_stats = False
            while True:
                try:
                    msg = self._stats_queue.get_nowait()
                except queue.Empty:
                    break
                drained_stats = True

                if msg.get("__worker_exit__"):
                    # воркер закончил — процесс завершится сам
                    continue
                if "error" in msg:
                    self.status = StreamStatus.ERROR
                    self.error_message = msg["error"]
                    self._broadcast({
                        "type": "error",
                        "message": self.error_message,
                    })
                    continue

                self.stats = StreamStats(
                    total=int(msg.get("total", 0)),
                    per_line=msg.get("per_line", {}),
                    fps=float(msg.get("fps", 0.0)),
                    active_tracks=int(msg.get("active_tracks", 0)),
                    frames_processed=int(msg.get("frames_processed", 0)),   # ← из сообщения
                )

            # --- рассылаем stats раз в секунду ---
            now = time.time()
            if drained_stats and (now - last_stats_ts) >= 1.0:
                self._broadcast({
                    "type": "stats",
                    "total": self.stats.total,
                    "per_line": self.stats.per_line,
                    "fps": self.stats.fps,
                    "active": self.stats.active_tracks,
                })
                last_stats_ts = now

            # --- проверяем, не завершился ли процесс ---
            if self._proc is not None and not self._proc.is_alive():
                if self.status == StreamStatus.RUNNING:
                    self.status = StreamStatus.STOPPED
                    self.stopped_at = datetime.utcnow()
                    self._broadcast({
                        "type": "status",
                        "status": "stopped",
                    })
                break

            time.sleep(0.01)

    # ------------------------------------------------------------ WS API

    def subscribe(self, loop: asyncio.AbstractEventLoop) -> "asyncio.Queue[dict]":
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=64)
        sub = _WsSubscriber(queue=q, loop=loop)
        with self._subscribers_lock:
            self._subscribers.append(sub)
        return q

    def unsubscribe(self, q: "asyncio.Queue[dict]") -> None:
        with self._subscribers_lock:
            self._subscribers = [
                s for s in self._subscribers if s.queue is not q
            ]

    def _broadcast(self, msg: dict) -> None:
        """Рассылка JSON-сообщения всем WS-подписчикам."""
        with self._subscribers_lock:
            subs = list(self._subscribers)
        for sub in subs:
            try:
                sub.loop.call_soon_threadsafe(sub.queue.put_nowait, msg)
            except (asyncio.QueueFull, RuntimeError):
                pass

    def _broadcast_raw_frame(self, jpeg: bytes) -> None:
        """Кадр шлём отдельным сообщением с base64."""
        import base64
        b64 = base64.b64encode(jpeg).decode("ascii")
        self._broadcast({
            "type": "frame",
            "jpeg_b64": b64,
            "ts": time.time(),
        })

    # ------------------------------------------------------------ snapshot

    def get_snapshot(self) -> Optional[bytes]:
        with self._snapshot_lock:
            return self._last_jpeg

    # ------------------------------------------------------------ info

    def to_info(self) -> StreamInfo:
        return StreamInfo(
            id=self.id,
            status=self.status,
            rtsp_url_masked=self.rtsp_url_masked,
            lines_config_id=self.lines_config_id,
            created_at=self.created_at,
            started_at=self.started_at,
            stopped_at=self.stopped_at,
            last_frame_at=self.last_frame_at,
            stats=self.stats,
            error_message=self.error_message,
        )


# ---------------------------------------------------------------------------
# StreamManager: реестр сессий
# ---------------------------------------------------------------------------

class StreamManager:
    def __init__(self, *, model_path: str):
        self._sessions: dict[str, StreamSession] = {}
        self._lock = threading.RLock()
        self._model_path = model_path

    def create(
        self,
        *,
        stream_id: str,
        rtsp_url: str,
        lines_config_id: Optional[str],
        lines_config: dict,
    ) -> StreamSession:
        with self._lock:
            if stream_id in self._sessions:
                raise ValueError(f"Stream {stream_id} уже существует")

            session = StreamSession(
                stream_id=stream_id,
                rtsp_url=rtsp_url,
                rtsp_url_masked=_mask_rtsp_url(rtsp_url),
                lines_config_id=lines_config_id,
                lines_config=lines_config,
                model_path=self._model_path,
            )
            self._sessions[stream_id] = session
        session.start()
        return session

    def get(self, stream_id: str) -> Optional[StreamSession]:
        with self._lock:
            return self._sessions.get(stream_id)

    def list(self) -> list[StreamSession]:
        with self._lock:
            return list(self._sessions.values())

    def stop(self, stream_id: str) -> bool:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return False
        session.stop()
        # НЕ удаляем из реестра сразу — даём клиенту увидеть status=stopped.
        # Удаление — через delete().
        return True

    def delete(self, stream_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(stream_id, None)
        if session is None:
            return False
        if session.status not in (StreamStatus.STOPPED, StreamStatus.ERROR):
            session.stop()
        return True

    def shutdown(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
        for s in sessions:
            try:
                s.stop()
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _mask_rtsp_url(url: str) -> str:
    """rtsp://user:pass@host/path → rtsp://***:***@host/path."""
    if "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    if "@" not in rest:
        return url
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        return f"{scheme}://{user}:***@{host}"
    return f"{scheme}://***@{host}"


# ---------------------------------------------------------------------------
# Синглтон (инициализируется в app.main)
# ---------------------------------------------------------------------------

_manager: Optional[StreamManager] = None


def init_manager() -> StreamManager:
    global _manager
    _manager = StreamManager(model_path=settings.model_path)
    return _manager


def get_manager() -> StreamManager:
    if _manager is None:
        raise RuntimeError("StreamManager не инициализирован")
    return _manager


def shutdown_manager() -> None:
    global _manager
    if _manager is not None:
        _manager.shutdown()
        _manager = None
