from dataclasses import dataclass, field
from typing import Dict, List, Literal, Tuple

Direction = Literal["in", "out", "left", "right", "unknown"]

@dataclass
class LineCrossingEvent:
    """Событие пересечения линии одним треком."""
    track_id: int
    frame_idx: int
    timestamp: float                    # секунды от начала видео
    direction: Direction
    line_id: str                        # имя линии, если их несколько
    point: Tuple[float, float]          # где именно пересёк (для визуализации)

@dataclass
class CountingStats:
    """Агрегированная статистика на текущий момент."""
    total: int = 0
    per_line: Dict[str, Dict[Direction, int]] = field(default_factory=dict)
    # например: {"line_main": {"in": 12, "out": 8}}

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "per_line": {k: dict(v) for k, v in self.per_line.items()},
        }
