"""Сериализация виртуальных линий: dict ↔ VirtualLine.

Нужно для API (/api/lines) и для CLI (--lines config.json).
Сам класс VirtualLine остаётся в counting.counter — не ломаем импорты.
"""
from __future__ import annotations

from typing import Any

from counting.counter import VirtualLine


def line_from_dict(data: dict[str, Any]) -> VirtualLine:
    """dict → VirtualLine.

    Ожидаемые поля:
      line_id: str
      coords: [x1, y1, x2, y2] (список или кортеж)
      direction_pos_to_neg: str (default "in")
      direction_neg_to_pos: str (default "out")
      use_point: str (default "bottom_center")
    """
    coords = tuple(float(v) for v in data["coords"])
    if len(coords) != 4:
        raise ValueError(
            f"coords должен содержать 4 числа, получено {len(coords)}"
        )
    return VirtualLine(
        line_id=str(data["line_id"]),
        coords=coords,  # type: ignore[arg-type]
        direction_pos_to_neg=data.get("direction_pos_to_neg", "in"),
        direction_neg_to_pos=data.get("direction_neg_to_pos", "out"),
        use_point=data.get("use_point", "bottom_center"),
    )


def line_to_dict(line: VirtualLine) -> dict[str, Any]:
    """VirtualLine → dict (для JSON-ответов API)."""
    return {
        "line_id": line.line_id,
        "coords": list(line.coords),
        "direction_pos_to_neg": line.dir_pos_to_neg,
        "direction_neg_to_pos": line.dir_neg_to_pos,
        "use_point": line.use_point,
    }


def lines_from_config(config: dict[str, Any]) -> list[VirtualLine]:
    """Конфиг {'VIRTUAL_LINES': [...]} → list[VirtualLine].

    Совместимо с текущим форматом config.py.
    """
    return [line_from_dict(item) for item in config["VIRTUAL_LINES"]]


def lines_to_config(lines: list[VirtualLine]) -> dict[str, Any]:
    """Обратное преобразование — на случай экспорта."""
    return {"VIRTUAL_LINES": [line_to_dict(ln) for ln in lines]}
