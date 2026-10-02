from typing import Tuple

Point = Tuple[float, float]
Line = Tuple[float, float, float, float]  # x1, y1, x2, y2


def side_of_line(p: Point, line: Line) -> float:
    """Знак векторного произведения (p - a) × (b - a).

    > 0 — точка слева от направленного отрезка a→b
    < 0 — справа
    = 0 — на линии
    """
    x1, y1, x2, y2 = line
    px, py = p
    return (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)


def segments_intersect(p1: Point, p2: Point, line: Line) -> bool:
    """Пересекает ли отрезок p1→p2 заданную линию (в пределах её длины)."""
    x1, y1, x2, y2 = line
    s1 = side_of_line(p1, line)
    s2 = side_of_line(p2, line)
    if s1 * s2 > 0:
        return False  # обе точки с одной стороны
    # проверка, что пересечение попадает в границы отрезка линии
    s3 = side_of_line((x1, y1), (p1[0], p1[1], p2[0], p2[1]))
    s4 = side_of_line((x2, y2), (p1[0], p1[1], p2[0], p2[1]))
    return s3 * s4 <= 0
