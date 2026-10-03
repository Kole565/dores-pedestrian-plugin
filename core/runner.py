"""Ядро пайплайна: offline- и real-time-циклы обработки.

run_offline() — файл → annotated.mp4 + report.json + events.csv + intensity.png
run_stream()  — RTSP → колбэки on_frame/on_stats (для WS)

Оба используют один и тот же Detector и LineCounter.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from . import config as core_config
from .detector import Detector
from .lines import lines_from_config
from counting.counter import LineCounter
from counting.types import CountingStats, LineCrossingEvent
from reporting import (
    AnnotatedVideoWriter,
    FrameVisualizer,
    ReportBuilder,
    plot_intensity,
    write_csv,
    write_json,
)
from sources.base import VideoSource
from tracking.types import Track


# ---------------------------------------------------------------------------
# Результат offline-прогона
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    """Всё, что нужно знать о завершённом offline-прогоне."""
    frames_processed: int
    fps_avg: float
    duration_sec: float
    stats: dict
    output_video: Optional[str] = None
    report_json: Optional[str] = None
    events_csv: Optional[str] = None
    intensity_png: Optional[str] = None


# Колбэки для real-time
FrameCallback = Callable[[np.ndarray, int, float], None]
StatsCallback = Callable[[CountingStats, float, int, int], None]
StopCheck = Callable[[], bool]


# ---------------------------------------------------------------------------
# Общая часть: обработка одного кадра
# ---------------------------------------------------------------------------

def _process_frame(
    frame: np.ndarray,
    detector: Detector,
    counter: LineCounter,
    frame_idx: int,
    timestamp: float,
) -> tuple[list[Track], list[LineCrossingEvent]]:
    """Один кадр: detector → counter. Общая часть обоих режимов."""
    tracks = detector.track(frame)
    events = counter.update(tracks, frame_idx, timestamp)
    return tracks, events


# ---------------------------------------------------------------------------
# Offline
# ---------------------------------------------------------------------------

def run_offline(
    source: VideoSource,
    *,
    model_path: str,
    lines_config: dict,
    output_video: Path,
    output_report_json: Path,
    output_events_csv: Path,
    output_intensity_png: Path,
    codec: str = core_config.OUTPUT_CODEC,
    fps_fallback: float = core_config.OUTPUT_FPS_FALLBACK,
    visual_cfg: core_config.VisualConfig = core_config.VISUAL,
    report_cfg: core_config.ReportConfig = core_config.REPORT,
    progress_cb: Optional[Callable[[int, int, float], None]] = None,
    stop_check: Optional[StopCheck] = None,
) -> RunResult:
    """Offline-прогон: файл/MOT17 → артефакты на диск.

    Args:
        source: уже открытый VideoSource.
        progress_cb: (frame_idx, frame_count, fps_avg) — для API-прогресса.
        stop_check: () → bool. Если вернёт True — мягкая остановка.
    """
    # --- мета источника ---
    width = source.width
    height = source.height
    fps = source.fps or fps_fallback
    frame_count = source.frame_count

    # --- модель и счётчик ---
    detector = Detector(model_path)
    detector.load()
    counter = LineCounter(
        lines=lines_from_config(lines_config),
        **core_config.COUNTING_PARAMS,
    )

    # --- визуализация + отчёт ---
    visualizer = FrameVisualizer(visual_cfg)
    reporter = ReportBuilder(
        input_video=str(getattr(source, "path", getattr(source, "url", "unknown"))),
        output_video=str(output_video),
    )

    frame_idx = 0
    t_start = time.time()
    fps_proc = 0.0

    with AnnotatedVideoWriter(output_video, fps, (width, height), fourcc=codec) as writer:
        while True:
            if stop_check is not None and stop_check():
                break

            ok, frame = source.read()
            if not ok:
                if source.is_live:
                    time.sleep(0.01)
                    continue
                break

            frame_idx += 1
            timestamp = frame_idx / fps

            tracks, events = _process_frame(
                frame, detector, counter, frame_idx, timestamp
            )
            reporter.add_events(events)

            elapsed = time.time() - t_start
            fps_proc = frame_idx / elapsed if elapsed > 0 else 0.0
            reporter.tick(frame_idx, timestamp, fps_proc)

            canvas = visualizer.render(
                frame, tracks, counter.lines, counter.stats,
                events, frame_idx, frame_count, fps_proc,
            )
            writer.write(canvas)

            if progress_cb is not None:
                progress_cb(frame_idx, frame_count, fps_proc)

    # --- финальные артефакты ---
    data = reporter.finalize(counter.stats)
    write_json(data, output_report_json)
    write_csv(data, output_events_csv)
    plot_intensity(
        data.per_bucket,
        output_intensity_png,
        duration_sec=data.duration_sec,
        bucket_sec=data.bucket_sec,
        dpi=report_cfg.plot_dpi,
        color=report_cfg.plot_color,
    )

    return RunResult(
        frames_processed=frame_idx,
        fps_avg=round(fps_proc, 2),
        duration_sec=data.duration_sec,
        stats=data.stats,
        output_video=str(output_video),
        report_json=str(output_report_json),
        events_csv=str(output_events_csv),
        intensity_png=str(output_intensity_png),
    )


# ---------------------------------------------------------------------------
# Real-time
# ---------------------------------------------------------------------------

def run_stream(
    source: VideoSource,
    *,
    model_path: str,
    lines_config: dict,
    on_frame: Optional[FrameCallback] = None,
    on_stats: Optional[StatsCallback] = None,
    stats_every_sec: float = 1.0,
    stop_check: Optional[StopCheck] = None,
) -> RunResult:
    """Real-time-цикл: RTSP → колбэки on_frame/on_stats.

    Не пишет на диск. Этап E обернёт это в multiprocessing.Process
    и подключит WebSocket.

    Args:
        on_frame: (annotated_frame, frame_idx, timestamp) — для JPEG-кодирования.
        on_stats: (stats, fps_avg, active_tracks) — раз в stats_every_sec.
        stop_check: () → bool — мягкая остановка.
    """
    fps = source.fps or core_config.OUTPUT_FPS_FALLBACK

    detector = Detector(model_path)
    detector.load()
    counter = LineCounter(
        lines=lines_from_config(lines_config),
        **core_config.COUNTING_PARAMS,
    )
    visualizer = FrameVisualizer(core_config.VISUAL)

    frame_idx = 0
    t_start = time.time()
    fps_proc = 0.0
    last_stats_ts = 0.0

    while True:
        if stop_check is not None and stop_check():
            break

        ok, frame = source.read()
        if not ok:
            # RTSPSource сам ретраит; ждём и пробуем снова
            time.sleep(0.01)
            continue

        frame_idx += 1
        timestamp = frame_idx / fps

        tracks, events = _process_frame(
            frame, detector, counter, frame_idx, timestamp
        )

        elapsed = time.time() - t_start
        fps_proc = frame_idx / elapsed if elapsed > 0 else 0.0

        canvas = visualizer.render(
            frame, tracks, counter.lines, counter.stats,
            events, frame_idx, 0, fps_proc,  # 0 = live
        )

        if on_frame is not None:
            on_frame(canvas, frame_idx, timestamp)

        now = time.time()
        if on_stats is not None and (now - last_stats_ts) >= stats_every_sec:
            on_stats(counter.stats, fps_proc, len(tracks), frame_idx)
            last_stats_ts = now

    return RunResult(
        frames_processed=frame_idx,
        fps_avg=round(fps_proc, 2),
        duration_sec=frame_idx / fps if fps > 0 else 0.0,
        stats=counter.stats.as_dict(),
    )
