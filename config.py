# config.py
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Пути (как было)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
INPUT_VIDEO = BASE_DIR / "input" / "MOT17" / "train" / "MOT17-09-FRCNN"
OUTPUT_VIDEO = BASE_DIR / "output" / "annotated.mp4"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_REPORT_JSON = OUTPUT_DIR / "report.json"
OUTPUT_EVENTS_CSV = OUTPUT_DIR / "events.csv"
OUTPUT_INTENSITY_PNG = OUTPUT_DIR / "intensity.png"
MODEL_PATH = "yolov8m.pt"

# ---------------------------------------------------------------------------
# Детекция / трекинг (как было)
# ---------------------------------------------------------------------------
CONF_THRESHOLD = 0.4
IOU_THRESHOLD = 0.5
PERSON_CLASS_ID = 0

TRACKER_CFG = "bytetrack.yaml"
#TRACKER_CFG = "bytetrack_fast.yaml"
#TRACKER_CFG = "botsort.yaml"
TRACK_HIGH_THRESH = 0.5
TRACK_LOW_THRESH = 0.1
TRACK_MAX_AGE = 30

OUTPUT_FPS_FALLBACK = 25
OUTPUT_CODEC = "mp4v"

VIRTUAL_LINES = [
    {
        "line_id": "line_main",
#        "coords": (960, 0, 960, 1200), # Vertical line
        "coords": (960, 730, 1270, 840), # Floor line
        "direction_pos_to_neg": "in",
        "direction_neg_to_pos": "out",
        "use_point": "bottom_center",
    },
]

COUNTING_PARAMS = {
    "history_size": 5,
    "max_missing_frames": 30,
    "min_displacement_px": 1.0,
}

# ---------------------------------------------------------------------------
# Этап 4: визуализация и отчёты
# ---------------------------------------------------------------------------

@dataclass
class VisualConfig:
    line_color: tuple = (0, 255, 255)        # BGR, жёлтый — как в pipeline.py
    bbox_color: tuple = (0, 200, 0)          # как было
    text_color: tuple = (0, 0, 0)
    text_bg_color: tuple = (0, 200, 0)
    hud_text_color: tuple = (255, 255, 255)
    hud_bg_color: tuple = (0, 0, 0)
    event_in_color: tuple = (0, 0, 255)      # красный для "in"/"left"
    event_out_color: tuple = (255, 0, 0)     # синий для "out"/"right"
    bbox_thickness: int = 2
    line_thickness: int = 3
    font_scale: float = 0.6
    font_thickness: int = 2
    show_center_dot: bool = True
    trail_length: int = 30                   # как HISTORY_LEN в pipeline.py


@dataclass
class ReportConfig:
    per_minute_bucket_sec: int = 60
    plot_dpi: int = 120
    plot_color: str = "#3b82f6"


VISUAL = VisualConfig()
REPORT = ReportConfig()
