from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True)
class Track:
    """Унифицированное представление трека пешехода.

    Это ЕДИНСТВЕННЫЙ контракт между Этапом 2 и Этапом 3.
    Любой трекер (DeepSORT, ByteTrack) должен приводиться к этому виду.
    """
    track_id: int                       # уникальный ID трека (стабильный между кадрами)
    bbox: Tuple[float, float, float, float]  # (x1, y1, x2, y2) в пикселях кадра
    confidence: float = 1.0             # уверенность детекции (0..1), опционально

    @property
    def center(self) -> Tuple[float, float]:
        """Центр bbox — используется для проверки пересечения линии."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def bottom_center(self) -> Tuple[float, float]:
        """Точка 'под ногами' — часто точнее для подсчёта на линии.

        Для уличных камер линия обычно нарисована на земле,
        поэтому центр нижней грани bbox физически корректнее.
        """
        x1, _, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, y2)

