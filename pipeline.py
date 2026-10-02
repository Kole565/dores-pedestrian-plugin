"""
Базовый пайплайн: видео → YOLOv8 (детекция person) → ByteTrack (трекинг)
→ подсчёт пересечений виртуальных линий (Этап 3)
→ аннотированное видео + JSON/CSV/график (Этап 4).
"""

import sys
import time
from pathlib import Path

import signal
import threading

import cv2
from ultralytics import YOLO

import config
from counting.factory import build_counter
from counting.types import LineCrossingEvent
from reporting import (
    AnnotatedVideoWriter,
    FrameVisualizer,
    ReportBuilder,
    plot_intensity,
    write_csv,
    write_json,
)
from tracking.types import Track
from sources.factory import open_source

from tools.mot17_source import Mot17Sequence


def _install_signal_handlers(stop_event: threading.Event) -> None:
    """SIGINT/SIGTERM → выставить stop_event (мягкая остановка)."""
    def _handler(signum, _frame):
        print(f"\n[INFO] Получен сигнал {signum}, останавливаемся...")
        stop_event.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)

# ---------------------------------------------------------------------------
# Ввод / вывод видео
# ---------------------------------------------------------------------------

def open_video(path: str):
    """Тонкая обёртка над open_source для обратной совместимости.

    Возвращает (source, meta) — source удовлетворяет VideoSource.
    """
    src = open_source(path, kind="auto")
    meta = {
        "width":  src.width,
        "height": src.height,
        "fps":    src.fps or config.OUTPUT_FPS_FALLBACK,
        "frame_count": src.frame_count,
        "is_live": src.is_live,
    }
    return src, meta

def results_to_tracks(results) -> list[Track]:
    """Адаптер Ultralytics → Track (без изменений)."""
    if not results:
        return []
    boxes = results[0].boxes
    if boxes is None or boxes.id is None:
        return []
    xyxy = boxes.xyxy.cpu().numpy()
    ids = boxes.id.cpu().numpy().astype(int)
    confs = boxes.conf.cpu().numpy()
    return [
        Track(track_id=int(tid),
              bbox=(float(x1), float(y1), float(x2), float(y2)),
              confidence=float(conf))
        for (x1, y1, x2, y2), tid, conf in zip(xyxy, ids, confs)
    ]


# ---------------------------------------------------------------------------
# Основной цикл
# ---------------------------------------------------------------------------

def main():
    stop_event = threading.Event()
    _install_signal_handlers(stop_event)

    print("[INFO] Загрузка модели YOLO...")
    model = YOLO(config.MODEL_PATH)

    print("[INFO] Инициализация счётчика линий...")
    counter = build_counter({
        "VIRTUAL_LINES": config.VIRTUAL_LINES,
        "COUNTING_PARAMS": config.COUNTING_PARAMS,
    })
    print(f"[INFO] Линий задано: {len(counter.lines)} "
          f"({', '.join(ln.line_id for ln in counter.lines)})")

    print(f"[INFO] Открытие видео: {config.INPUT_VIDEO}")
    cap, meta = open_video(config.INPUT_VIDEO)
    print(f"[INFO] Видео: {meta['width']}x{meta['height']} @ {meta['fps']:.1f} FPS, "
          f"кадров: {meta['frame_count']}")

    # --- Этап 4: визуализатор + отчёт ---
    visualizer = FrameVisualizer(config.VISUAL)
    reporter = ReportBuilder(
        input_video=str(config.INPUT_VIDEO),
        output_video=str(config.OUTPUT_VIDEO),
    )

    frame_idx = 0
    t_start = time.time()
    fps_proc = 0.0


    with AnnotatedVideoWriter(config.OUTPUT_VIDEO, meta["fps"],
        (meta["width"], meta["height"]),
        fourcc=config.OUTPUT_CODEC,) as writer:
        while not stop_event.is_set():
            ok, frame = cap.read()
            if not ok:
                if meta.get("is_live"): # Wait for frame if network is unstable
                    time.sleep(0.01)
                    continue
                break

            frame_idx += 1
            timestamp = frame_idx / meta["fps"]

            results = model.track(
                frame,
                persist=True,
                tracker=config.TRACKER_CFG,
                conf=config.CONF_THRESHOLD,
                iou=config.IOU_THRESHOLD,
                classes=[config.PERSON_CLASS_ID],
                verbose=False,
            )
            tracks = results_to_tracks(results)

            # --- ЭТАП 3: подсчёт (без изменений) ---
            events: list[LineCrossingEvent] = counter.update(
                tracks, frame_idx, timestamp
            )

            # --- ЭТАП 4: аккумуляция событий и метрик ---
            reporter.add_events(events)

            elapsed = time.time() - t_start
            fps_proc = frame_idx / elapsed if elapsed > 0 else 0.0
            reporter.tick(frame_idx, timestamp, fps_proc)

            # --- ЭТАП 4: визуализация ---
            canvas = visualizer.render(
                frame, tracks, counter.lines, counter.stats,
                events, frame_idx, meta["frame_count"], fps_proc,
            )
            writer.write(canvas)

            if frame_idx % 30 == 0:
                print(f"[INFO] Кадр {frame_idx}, FPS: {fps_proc:.1f}, "
                      f"треков: {len(tracks)}, "
                      f"событий: {len(reporter.events)}, "
                      f"total: {counter.stats.total}")

    cap.release()

    # --- ЭТАП 4: финальные отчёты ---
    data = reporter.finalize(counter.stats)

    write_json(data, config.OUTPUT_REPORT_JSON)
    write_csv(data, config.OUTPUT_EVENTS_CSV)
    plot_intensity(
        data.per_bucket,
        config.OUTPUT_INTENSITY_PNG,
        duration_sec=data.duration_sec,
        bucket_sec=data.bucket_sec,
        dpi=config.REPORT.plot_dpi,
        color=config.REPORT.plot_color,
    )

    print(f"[DONE] Видео: {config.OUTPUT_VIDEO}")
    print(f"[DONE] JSON:  {config.OUTPUT_REPORT_JSON}")
    print(f"[DONE] CSV:   {config.OUTPUT_EVENTS_CSV}")
    print(f"[DONE] График: {config.OUTPUT_INTENSITY_PNG}")
    print(f"[DONE] Кадров: {frame_idx}, средний FPS: {fps_proc:.1f}")
    print(f"[DONE] Статистика: {data.stats}")
    print(f"[DONE] Всего событий: {len(data.events)}")


if __name__ == "__main__":
    main()
