"""CLI-настройки + реэкспорт гиперпараметров ядра (обратная совместимость).

Гиперпараметры детектора/трекера/визуализации переехали в core/config.py.
Здесь остаются пути и то, что специфично для CLI-запуска.
"""
from pathlib import Path

# --- реэкспорт для обратной совместимости ---
from core.config import (  # noqa: F401
    CONF_THRESHOLD, IOU_THRESHOLD, PERSON_CLASS_ID,
    TRACKER_CFG, TRACK_HIGH_THRESH, TRACK_LOW_THRESH, TRACK_MAX_AGE,
    OUTPUT_FPS_FALLBACK, OUTPUT_CODEC,
    COUNTING_PARAMS, DEFAULT_VIRTUAL_LINES as VIRTUAL_LINES,
    VisualConfig, ReportConfig, VISUAL, REPORT,
)

# ---------------------------------------------------------------------------
# Пути CLI
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
INPUT_VIDEO = "rtsp://localhost:8554/live"
OUTPUT_VIDEO = BASE_DIR / "output" / "annotated.mp4"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_REPORT_JSON = OUTPUT_DIR / "report.json"
OUTPUT_EVENTS_CSV = OUTPUT_DIR / "events.csv"
OUTPUT_INTENSITY_PNG = OUTPUT_DIR / "intensity.png"
MODEL_PATH = "models/yolov8n.pt"
