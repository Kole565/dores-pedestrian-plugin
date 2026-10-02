from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

from counting.types import CountingStats, LineCrossingEvent

@dataclass
class ReportData:
    input_video: str
    output_video: str
    fps_avg: float
    frames_processed: int
    duration_sec: float
    stats: dict
    bucket_sec: int = 60                       # ← новое
    per_bucket: dict[int, int] = field(default_factory=dict)   # ← переименовано
    events: list[LineCrossingEvent] = field(default_factory=list)


class ReportBuilder:
    def __init__(self, input_video: str, output_video: str):
        self.input_video = input_video
        self.output_video = output_video
        self.events: list[LineCrossingEvent] = []
        self._last_timestamp = 0.0
        self._frames_processed = 0
        self._fps_avg = 0.0

    def add_events(self, events):
        self.events.extend(events)

    def tick(self, frame_idx, timestamp_sec, fps_avg):
        self._frames_processed = frame_idx
        self._last_timestamp = timestamp_sec
        self._fps_avg = fps_avg

    def finalize(self, stats) -> ReportData:
        duration = self._last_timestamp
        bucket = _choose_bucket(duration)
        per_bucket = self._bucket_events(bucket)
        return ReportData(
            input_video=self.input_video,
            output_video=self.output_video,
            fps_avg=round(self._fps_avg, 2),
            frames_processed=self._frames_processed,
            duration_sec=round(duration, 3),
            stats=stats.as_dict(),
            bucket_sec=bucket,
            per_bucket=per_bucket,
            events=self.events,
        )

    def _bucket_events(self, bucket_sec: int) -> dict[int, int]:
        buckets: dict[int, int] = {}
        for ev in self.events:
            b = int(ev.timestamp // bucket_sec)
            buckets[b] = buckets.get(b, 0) + 1
        return dict(sorted(buckets.items()))


def _choose_bucket(duration_sec: float, target_bins: int = 10) -> int:
    """Подбирает размер бакета (сек) так, чтобы получилось ~target_bins столбиков."""
    if duration_sec <= 0:
        return 60
    raw = duration_sec / target_bins
    for candidate in (1, 2, 5, 10, 15, 30, 60, 120, 300, 600):
        if raw <= candidate:
            return candidate
    return int(raw)

# ---------- exporters ----------

def write_json(data: ReportData, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "input_video": data.input_video,
        "output_video": data.output_video,
        "fps_avg": data.fps_avg,
        "frames_processed": data.frames_processed,
        "duration_sec": data.duration_sec,
        "bucket_sec": data.bucket_sec,
        "stats": data.stats,
        "per_bucket": {str(k): v for k, v in data.per_bucket.items()},
        "events": [
            {
                "track_id": e.track_id,
                "frame_idx": e.frame_idx,
                "timestamp": round(e.timestamp, 3),
                "direction": e.direction,
                "line_id": e.line_id,
                "point": [round(e.point[0], 1), round(e.point[1], 1)],
            }
            for e in data.events
        ],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def write_csv(data: ReportData, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["frame_idx", "timestamp", "track_id",
             "line_id", "direction", "px", "py"]
        )
        for e in data.events:
            writer.writerow([
                e.frame_idx, f"{e.timestamp:.3f}", e.track_id,
                e.line_id, e.direction,
                f"{e.point[0]:.1f}", f"{e.point[1]:.1f}",
            ])
