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
      - counter хранит историю последних N позиций на трек для устойчивости
        к шуму bbox.
    """

    def __init__(
        self,
        lines: List[VirtualLine],
        history_size: int = 5,
        max_missing_frames: int = 30,
        min_displacement_px: float = 5.0,
    ):
        """
        Args:
            lines: список виртуальных линий.
            history_size: сколько последних точек трека хранить.
            max_missing_frames: через сколько кадров без обновления трек считается мёртвым.
            min_displacement_px: минимальное смещение точки между кадрами,
                чтобы считать пересечение «настоящим» (фильтр дрожания bbox).
        """
        self.lines = lines
        self.history_size = history_size
        self.max_missing_frames = max_missing_frames
        self.min_displacement_px = min_displacement_px

        # track_id -> deque[(frame_idx, point)]
        self._history: Dict[int, Deque[Tuple[int, Tuple[float, float]]]] = {}
        self._last_seen: Dict[int, int] = {}
        self._last_side: Dict[Tuple[int, str], float] = {}

        # накопленная статистика
        self.stats = CountingStats(
            total=0,
            per_line={ln.line_id: defaultdict(int) for ln in lines},
        )
        # события (можно отдавать наружу для JSON/CSV)
        self.events: List[LineCrossingEvent] = []

        # защита от повторного засчитывания одного и того же перехода
        # (например, если трек «дрожит» вокруг линии)
        self._counted: Dict[Tuple[int, str, Direction], int] = {}

    # ------------------------------------------------------------------ API

    def update(
        self,
        tracks: List[Track],
        frame_idx: int,
        timestamp: float,
    ) -> List[LineCrossingEvent]:
        """Обновить состояние на новом кадре.

        Returns:
            Список событий пересечения, произошедших на этом кадре.
            (Удобно для немедленной визуализации «только что пересёк».)
        """
        new_events: List[LineCrossingEvent] = []

        for track in tracks:
            self._update_track(track.track_id, frame_idx, track.bottom_center)

            for line in self.lines:
                point = line.point_for(track)
                ev = self._check_crossing(track, line, frame_idx, timestamp, point)
                if ev is not None:
                    new_events.append(ev)

        self._reap_dead_tracks(frame_idx)
        self.events.extend(new_events)
        return new_events

    def reset(self) -> None:
        """Сбросить всё состояние (для обработки нового видео)."""
        self._history.clear()
        self._last_seen.clear()
        self._last_side.clear()
        self._counted.clear()
        self.events.clear()
        self.stats = CountingStats(
            total=0,
            per_line={ln.line_id: defaultdict(int) for ln in self.lines},
        )

    # ------------------------------------------------------------- internals

    def _update_track(
        self,
        track_id: int,
        frame_idx: int,
        point: Tuple[float, float],
    ) -> None:
        hist = self._history.setdefault(track_id, deque(maxlen=self.history_size))
        hist.append((frame_idx, point))
        self._last_seen[track_id] = frame_idx


    def _reap_dead_tracks(self, frame_idx: int) -> None:
        dead = [
            tid for tid, last in self._last_seen.items()
            if frame_idx - last > self.max_missing_frames
        ]
        for tid in dead:
            self._history.pop(tid, None)
            self._last_seen.pop(tid, None)
            for key in [k for k in self._last_side if k[0] == tid]:
                self._last_side.pop(key, None)

        # чистим анти-дребезг: запись бесполезна, если старше окна
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

        prev_point = hist[-2][1]
        curr_side = side_of_line(curr_point, line.coords)
        prev_side = side_of_line(prev_point, line.coords)

        # нет смены знака — не пересечение
        if curr_side == 0 or prev_side == 0:
            return None
        if (curr_side > 0) == (prev_side > 0):
            return None

        # фильтр дрожания: смещение должно быть заметным
        dx = curr_point[0] - prev_point[0]
        dy = curr_point[1] - prev_point[1]
        if (dx * dx + dy * dy) ** 0.5 < self.min_displacement_px:
            return None

        # проверяем, что пересечение произошло в пределах отрезка линии
        if not segments_intersect(prev_point, curr_point, line.coords):
            return None

        direction: Direction = (
            line.dir_pos_to_neg if prev_side > 0 else line.dir_neg_to_pos
        )

        # анти-дребезг: не считать один и тот же переход повторно
        # в течение max_missing_frames кадров
        key = (track.track_id, line.line_id, direction)
        last_counted = self._counted.get(key)
        if last_counted is not None and frame_idx - last_counted < self.max_missing_frames:
            return None
        self._counted[key] = frame_idx

        # обновляем статистику
        self.stats.total += 1
        self.stats.per_line[line.line_id][direction] += 1

        # точка пересечения — приблизительно середина отрезка
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

