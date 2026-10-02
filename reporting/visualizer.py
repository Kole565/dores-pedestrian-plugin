# reporting/visualizer.py
from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterable

import cv2
import numpy as np

from config import VisualConfig
from counting.counter import VirtualLine
from counting.types import CountingStats, LineCrossingEvent
from tracking.types import Track


class FrameVisualizer:
    """Рисует bbox/ID/линии/счётчики/события поверх кадра.

    Заменяет inline-функции draw_tracks / draw_virtual_lines /
    draw_crossing_events / draw_hud / draw_counter_hud из старого pipeline.py.
    """

    def __init__(self, cfg: VisualConfig):
        self.cfg = cfg
        self._trails: dict[int, deque[tuple[int, int]]] = defaultdict(
            lambda: deque(maxlen=cfg.trail_length or 1)
        )

    def render(self, frame, tracks, lines, stats, events,
        frame_idx, total_frames, fps_proc):
        canvas = frame.copy()
        tracks = list(tracks)

        self._update_trails(tracks)
        self._draw_tracks(canvas, tracks)
        self._draw_lines(canvas, lines)
        self._draw_events(canvas, events)
        self._draw_top_hud(canvas, frame_idx, total_frames, fps_proc, len(tracks))
        self._draw_counter_hud(canvas, stats)
        return canvas

    # ---------- internals ----------

    def _update_trails(self, tracks: Iterable[Track]) -> None:
        for t in tracks:
            cx, cy = t.center
            self._trails[t.track_id].append((int(cx), int(cy)))

    def _draw_tracks(self, canvas: np.ndarray, tracks: Iterable[Track]) -> None:
        for t in tracks:
            x1, y1, x2, y2 = (int(v) for v in t.bbox)
            cv2.rectangle(
                canvas, (x1, y1), (x2, y2),
                self.cfg.bbox_color, self.cfg.bbox_thickness,
            )

            label = f"ID {t.track_id}  {t.confidence:.2f}"
            self._put_label(canvas, label, (x1, max(0, y1 - 8)),
                            self.cfg.text_bg_color, self.cfg.text_color)

            if self.cfg.show_center_dot:
                cx, cy = t.bottom_center
                cv2.circle(canvas, (int(cx), int(cy)), 3,
                           self.cfg.bbox_color, -1)

            # хвост трека
            pts = list(self._trails.get(t.track_id, []))
            for i in range(1, len(pts)):
                cv2.line(canvas, pts[i - 1], pts[i], self.cfg.bbox_color, 2)

    def _draw_lines(self, canvas: np.ndarray, lines: list[VirtualLine]) -> None:
        for line in lines:
            x1, y1, x2, y2 = (int(v) for v in line.coords)
            cv2.line(canvas, (x1, y1), (x2, y2),
                     self.cfg.line_color, self.cfg.line_thickness)
            cv2.circle(canvas, (x1, y1), 5, self.cfg.line_color, -1)
            cv2.circle(canvas, (x2, y2), 5, self.cfg.line_color, -1)

            label = (f"{line.line_id}: "
                     f"+→{line.dir_pos_to_neg} / -→{line.dir_neg_to_pos}")
            lx = min(x1, x2)
            ly = min(y1, y2) - 10
            self._put_label(canvas, label, (lx + 4, ly),
                            self.cfg.line_color, (0, 0, 0))

    def _draw_events(
        self, canvas: np.ndarray, events: list[LineCrossingEvent]
    ) -> None:
        for ev in events:
            px, py = int(ev.point[0]), int(ev.point[1])
            color = (
                self.cfg.event_in_color
                if ev.direction in ("in", "left")
                else self.cfg.event_out_color
            )
            cv2.circle(canvas, (px, py), 12, color, 3)
            cv2.putText(
                canvas, f"{ev.direction}#{ev.track_id}", (px + 14, py - 8),
                cv2.FONT_HERSHEY_SIMPLEX, self.cfg.font_scale,
                color, self.cfg.font_thickness, cv2.LINE_AA,
            )

    def _draw_top_hud(
        self,
        canvas: np.ndarray,
        frame_idx: int,
        total_frames: int,
        fps_proc: float,
        active_tracks: int,
    ) -> None:
        h, w = canvas.shape[:2]
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (w, 40), self.cfg.hud_bg_color, -1)
        cv2.addWeighted(overlay, 0.5, canvas, 0.5, 0, canvas)

        text = (
            f"Frame {frame_idx}/{total_frames}  |  "
            f"FPS: {fps_proc:.1f}  |  Active tracks: {active_tracks}"
        )
        cv2.putText(canvas, text, (10, 27), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, self.cfg.hud_text_color, 1, cv2.LINE_AA)

    def _draw_counter_hud(
        self, canvas: np.ndarray, stats: CountingStats
    ) -> None:
        h, w = canvas.shape[:2]
        lines_text = [f"TOTAL: {stats.total}"]
        for line_id, dirs in stats.per_line.items():
            parts = [f"{d}={n}" for d, n in sorted(dirs.items())]
            lines_text.append(f"{line_id}: " + "  ".join(parts))

        box_h = 24 * len(lines_text) + 10
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, h - box_h), (w, h),
                      self.cfg.hud_bg_color, -1)
        cv2.addWeighted(overlay, 0.5, canvas, 0.5, 0, canvas)

        y = h - box_h + 20
        for line in lines_text:
            cv2.putText(canvas, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, self.cfg.hud_text_color, 1, cv2.LINE_AA)
            y += 24

    def _put_label(
        self,
        canvas: np.ndarray,
        text: str,
        org: tuple[int, int],
        bg_color: tuple,
        fg_color: tuple,
    ) -> None:
        (tw, th), _ = cv2.getTextSize(
            text, cv2.FONT_HERSHEY_SIMPLEX,
            self.cfg.font_scale, self.cfg.font_thickness,
        )
        x, y = org
        cv2.rectangle(canvas, (x - 3, y - th - 4), (x + tw + 4, y + 4),
                      bg_color, -1)
        cv2.putText(canvas, text, (x, y),
                    cv2.FONT_HERSHEY_SIMPLEX, self.cfg.font_scale,
                    fg_color, self.cfg.font_thickness, cv2.LINE_AA)
