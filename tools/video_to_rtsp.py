"""Dev-утилита: публикует видеофайл как RTSP-поток через ffmpeg.

Пример:
    python tools/video_to_rtsp.py --input video.mp4 --loop --port 8554
    # → rtsp://localhost:8554/live

Требует установленного ffmpeg в PATH.

ВАЖНО: это НЕ часть runtime-сервиса. Утилита для разработки и демо.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


class VideoToRTSP:
    """Обёртка над ffmpeg-subprocess для публикации файла по RTSP."""

    def __init__(
        self,
        input_path: str,
        rtsp_url: str,
        *,
        loop: bool = False,
        fps: float | None = None,
        bitrate: str = "2M",
        preset: str = "veryfast",
        rtsp_transport: str = "tcp",
    ):
        self.input_path = input_path
        self.rtsp_url = rtsp_url
        self.loop = loop
        self.fps = fps
        self.bitrate = bitrate
        self.preset = preset
        self.rtsp_transport = rtsp_transport
        self._proc: subprocess.Popen | None = None

    def start(self) -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("ffmpeg не найден в PATH. Установите ffmpeg.")

        cmd: list[str] = ["ffmpeg", "-hide_banner", "-loglevel", "warning"]

        if self.loop:
            cmd += ["-stream_loop", "-1"]
        cmd += ["-re", "-i", self.input_path]

        if self.fps is not None:
            cmd += ["-r", str(self.fps)]

        cmd += [
            "-c:v", "libx264",
            "-preset", self.preset,
            "-tune", "zerolatency",
            "-b:v", self.bitrate,
            "-pix_fmt", "yuv420p",
            "-g", "30",
            "-f", "rtsp",
            "-rtsp_transport", self.rtsp_transport,
            self.rtsp_url,
        ]

        self._proc = subprocess.Popen(
            cmd, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def wait(self) -> int:
        if self._proc is None:
            return -1
        return self._proc.wait()

    def stop(self) -> None:
        if self._proc is None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        self._proc = None


def main() -> int:
    ap = argparse.ArgumentParser(description="Публикация видео как RTSP-поток")
    ap.add_argument("--input", required=True, help="Путь к видеофайлу")
    ap.add_argument("--loop", action="store_true", help="Зациклить видео")
    ap.add_argument("--fps", type=float, default=None, help="Переопределить FPS")
    ap.add_argument("--bitrate", default="2M", help="Битрейт (например, 2M)")
    ap.add_argument("--port", type=int, default=8554, help="Порт RTSP-сервера")
    ap.add_argument("--host", default="localhost", help="Хост RTSP-сервера")
    ap.add_argument("--path", default="live", help="Путь потока (без слэша)")
    args = ap.parse_args()

    if not Path(args.input).exists():
        print(f"[ERROR] Файл не найден: {args.input}", file=sys.stderr)
        return 2

    url = f"rtsp://{args.host}:{args.port}/{args.path}"
    pub = VideoToRTSP(
        args.input, url,
        loop=args.loop, fps=args.fps, bitrate=args.bitrate,
    )

    print(f"[INFO] Публикация: {args.input} → {url}")
    print("[INFO] Ctrl+C для остановки.")
    try:
        pub.start()
        return pub.wait()
    except KeyboardInterrupt:
        print("\n[INFO] Остановка...")
        pub.stop()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
