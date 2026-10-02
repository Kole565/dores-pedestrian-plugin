# pipeline.py
"""CLI-обёртка над core.runner.run_offline.

Обратная совместимость: `python pipeline.py` без аргументов работает
как раньше — читает config.INPUT_VIDEO, пишет в config.OUTPUT_*.

Расширенный запуск:
    python pipeline.py --input video.mp4 --lines lines.json
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from pathlib import Path

import config
from core import config as core_config
from core.runner import run_offline
from sources.factory import open_source


def _install_signal_handlers(stop_event: threading.Event) -> None:
    def _handler(signum, _frame):
        print(f"\n[INFO] Получен сигнал {signum}, останавливаемся...")
        stop_event.set()

    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="DORES Pedestrian Flow — offline-обработка видео",
    )
    ap.add_argument(
        "--input", default=str(config.INPUT_VIDEO),
        help="Путь к видео, RTSP-URL или папка MOT17",
    )
    ap.add_argument(
        "--output-dir", default=str(config.OUTPUT_DIR),
        help="Куда писать артефакты",
    )
    ap.add_argument(
        "--lines", default=None,
        help="JSON-файл с конфигом линий ({'VIRTUAL_LINES': [...]})",
    )
    ap.add_argument(
        "--model", default=config.MODEL_PATH,
        help="Путь к весам YOLO",
    )
    return ap.parse_args()


def _load_lines_config(path: str | None) -> dict:
    if path is None:
        return {"VIRTUAL_LINES": config.VIRTUAL_LINES}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if "VIRTUAL_LINES" not in data:
        raise ValueError(f"{path}: ожидается ключ 'VIRTUAL_LINES'")
    return data


def main() -> int:
    args = _parse_args()

    stop_event = threading.Event()
    _install_signal_handlers(stop_event)

    lines_config = _load_lines_config(args.lines)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Открытие источника: {args.input}")
    source = open_source(args.input, kind="auto")
    print(
        f"[INFO] Источник: {source.width}x{source.height} @ {source.fps:.1f} FPS, "
        f"кадров: {source.frame_count}, live: {source.is_live}"
    )

    print("[INFO] Запуск offline-обработки...")
    try:
        result = run_offline(
            source,
            model_path=args.model,
            lines_config=lines_config,
            output_video=output_dir / "annotated.mp4",
            output_report_json=output_dir / "report.json",
            output_events_csv=output_dir / "events.csv",
            output_intensity_png=output_dir / "intensity.png",
            progress_cb=lambda idx, total, fps: (
                print(
                    f"[INFO] Кадр {idx}"
                    + (f"/{total}" if total else " (live)")
                    + f", FPS: {fps:.1f}"
                ) if idx % 30 == 0 else None
            ),
            stop_check=stop_event.is_set,
        )
    finally:
        source.release()

    print(f"[DONE] Видео: {result.output_video}")
    print(f"[DONE] JSON:  {result.report_json}")
    print(f"[DONE] CSV:   {result.events_csv}")
    print(f"[DONE] График: {result.intensity_png}")
    print(f"[DONE] Кадров: {result.frames_processed}, средний FPS: {result.fps_avg:.1f}")
    print(f"[DONE] Статистика: {result.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
