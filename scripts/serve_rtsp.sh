#!/usr/bin/env bash
# scripts/serve_rtsp.sh — обёртка над tools/video_to_rtsp.py
#
# Использование:
#   ./scripts/serve_rtsp.sh path/to/video.mp4 [--loop] [--port 8554]
#
# Зависимость: ffmpeg в PATH.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <video_file> [--loop] [--port N] [--fps F] [--bitrate 2M]" >&2
  exit 1
fi

INPUT="$1"; shift || true

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "[ERROR] ffmpeg не найден. Установите: apt install ffmpeg" >&2
  exit 1
fi

exec python "$PROJECT_ROOT/tools/video_to_rtsp.py" --input "$INPUT" "$@"
