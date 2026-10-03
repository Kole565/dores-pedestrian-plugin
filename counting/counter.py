from collections import defaultdict, deque
from typing import Deque, Dict, List, Optional, Tuple

from .geometry import segments_intersect, side_of_line
from tracking.types import Track
from .types import CountingStats, Direction, LineCrossingEvent


class VirtualLine:
    """Виртуальная линия с двумя подписанными направлениями.

    Направление определяется знаком side_of_line:
      - переход из '+' в '−'  → direction_pos_to_neg
      - переход из '−' в '+'  → direction_neg_to_pos
    """

    def __init__(
        self,
        line_id: str,
        coords: Tuple[float, float, float, float],
        direction_pos_to_neg: Direction = "in",
        direction_neg_to_pos: Direction = "out",
        use_point: str = "bottom_center",  # "center" | "bottom_center"
    ):
        self.line_id = line_id
        self.coords = coords
        self.dir_pos_to_neg = direction_pos_to_neg
        self.dir_neg_to_pos = direction_neg_to_pos
        self.use_point = use_point

    def point_for(self, track: Track) -> Tuple[float, float]:
        return track.bottom_center if self.use_point == "bottom_center" else track.center


class LineCounter:
    """Подсчёт пересечений виртуальных линий треками пешеходов.

    Контракт:
      - update(tracks, frame_idx, timestamp) вызывается на КАЖДОМ кадре
        (даже если tracks пуст — иначе потеряем историю для «пропавших» ID);
      - counter хранит историю последних N Track'ов на трек, чтобы
        корректно работать с линиями, у которых разный use_point.
    """

    def __init__(
        self,
        lines: List[VirtualLine],
        history_size: int = 5,
        max_missing_frames: int = 30,
        min_displacement_px: float = 5.0,
    ):
        self.lines = lines
        self.history_size = history_size
        self.max_missing_frames = max_missing_frames
        self.min_displacement_px = min_displacement_px

        # track_id -> deque[(frame_idx, Track)] — храним Track, а не точку,
        # чтобы для каждой линии взять именно её точку (use_point) на обоих концах.
        self._history: Dict[int, Deque[Tuple[int, Track]]] = {}
        self._last_seen: Dict[int, int] = {}

        self.stats = CountingStats(
            total=0,
            per_line={ln.line_id: defaultdict(int) for ln in lines},
        )
        self.events: List[LineCrossingEvent] = []

        self._counted: Dict[Tuple[int, str, Direction], int] = {}

    # ------------------------------------------------------------------ API

    def update(
        self,
        tracks: List[Track],
        frame_idx: int,
        timestamp: float,
    ) -> List[LineCrossingEvent]:
        new_events: List[LineCrossingEvent] = []

        for track in tracks:
            self._update_track(track.track_id, frame_idx, track)

            for line in self.lines:
                point = line.point_for(track)
                ev = self._check_crossing(track, line, frame_idx, timestamp, point)
                if ev is not None:
                    new_events.append(ev)

        self._reap_dead_tracks(frame_idx)
        self.events.extend(new_events)
        return new_events

    def reset(self) -> None:
        self._history.clear()
        self._last_seen.clear()
        self._counted.clear()
        self.events.clear()
        self.stats = CountingStats(
            total=0,
            per_line={ln.line_id: defaultdict(int) for ln in self.lines},
        )

    # ------------------------------------------------------------- internals

    def _update_track(self, track_id: int, frame_idx: int, track: Track) -> None:
        hist = self._history.setdefault(track_id, deque(maxlen=self.history_size))
        hist.append((frame_idx, track))
        self._last_seen[track_id] = frame_idx

    def _reap_dead_tracks(self, frame_idx: int) -> None:
        dead = [
            tid for tid, last in self._last_seen.items()
            if frame_idx - last > self.max_missing_frames
        ]
        for tid in dead:
            self._history.pop(tid, None)
            self._last_seen.pop(tid, None)

        # анти-дребезг: чистим записи старше окна
        ttl = self.max_missing_frames
        stale = [k for k, f in self._counted.items() if frame_idx - f > ttl]
        for k in stale:
            self._counted.pop(k, None)

    def _check_crossing(
        self,
        track: Track,
        line: VirtualLine,
        frame_idx: int,
        timestamp: float,
        curr_point: Tuple[float, float],
    ) -> Optional[LineCrossingEvent]:
        hist = self._history.get(track.track_id)
        if not hist or len(hist) < 2:
            return None

        # prev_point берём через тот же line.point_for, что и curr_point —
        # иначе для use_point="center" мы сравнивали бы center с bottom_center
        prev_track = hist[-2][1]
        prev_point = line.point_for(prev_track)

        curr_side = side_of_line(curr_point, line.coords)
        prev_side = side_of_line(prev_point, line.coords)

        if curr_side == 0 or prev_side == 0:
            return None
        if (curr_side > 0) == (prev_side > 0):
            return None

        dx = curr_point[0] - prev_point[0]
        dy = curr_point[1] - prev_point[1]
        if (dx * dx + dy * dy) ** 0.5 < self.min_displacement_px:
            return None

        if not segments_intersect(prev_point, curr_point, line.coords):
            return None

        direction: Direction = (
            line.dir_pos_to_neg if prev_side > 0 else line.dir_neg_to_pos
        )

        key = (track.track_id, line.line_id, direction)
        last_counted = self._counted.get(key)
        if last_counted is not None and frame_idx - last_counted < self.max_missing_frames:
            return None
        self._counted[key] = frame_idx

        self.stats.total += 1
        self.stats.per_line[line.line_id][direction] += 1

        cross_point = (
            (prev_point[0] + curr_point[0]) / 2.0,
            (prev_point[1] + curr_point[1]) / 2.0,
        )

        return LineCrossingEvent(
            track_id=track.track_id,
            frame_idx=frame_idx,
            timestamp=timestamp,
            direction=direction,
            line_id=line.line_id,
            point=cross_point,
        )
