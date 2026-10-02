"""Гиперпараметры ядра: детекция, трекинг, визуализация, отчёты.

Не содержит путей к входным/выходным файлам и настроек сервера —
это остаётся в CLI (pipeline.py) и app/settings.py.
"""
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Детекция / трекинг
# ---------------------------------------------------------------------------
CONF_THRESHOLD = 0.4
IOU_THRESHOLD = 0.5
PERSON_CLASS_ID = 0

TRACKER_CFG = "bytetrack.yaml"
TRACK_HIGH_THRESH = 0.5
TRACK_LOW_THRESH = 0.1
TRACK_MAX_AGE = 30

OUTPUT_FPS_FALLBACK = 25
OUTPUT_CODEC = "mp4v"

# ---------------------------------------------------------------------------
# Подсчёт
# ---------------------------------------------------------------------------
COUNTING_PARAMS = {
    "history_size": 5,
    "max_missing_frames": 30,
    "min_displacement_px": 1.0,
}

# Дефолтный конфиг линий (используется при первом запуске сервера,
# если БД пуста). Раньше был VIRTUAL_LINES в config.py.
DEFAULT_VIRTUAL_LINES = [
    {
        "line_id": "line_main",
        "coords": (960, 730, 1270, 840),
        "direction_pos_to_neg": "in",
        "direction_neg_to_pos": "out",
        "use_point": "bottom_center",
    },
]

# ---------------------------------------------------------------------------
# Визуализация
# ---------------------------------------------------------------------------
@dataclass
class VisualConfig:
    line_color: tuple = (0, 255, 255)
    bbox_color: tuple = (0, 200, 0)
    text_color: tuple = (0, 0, 0)
    text_bg_color: tuple = (0, 200, 0)
    hud_text_color: tuple = (255, 255, 255)
    hud_bg_color: tuple = (0, 0, 0)
    event_in_color: tuple = (0, 0, 255)
    event_out_color: tuple = (255, 0, 0)
    bbox_thickness: int = 2
    line_thickness: int = 3
    font_scale: float = 0.6
    font_thickness: int = 2
    show_center_dot: bool = True
    trail_length: int = 30


@dataclass
class ReportConfig:
    per_minute_bucket_sec: int = 60
    plot_dpi: int = 120
    plot_color: str = "#3b82f6"


VISUAL = VisualConfig()
REPORT = ReportConfig()
