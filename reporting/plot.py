from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


def _choose_bucket(duration_sec: float, events_count: int) -> int:
    """Подбирает размер бакета так, чтобы на графике было 5–15 столбиков.

    Возвращает размер бакета в секундах.
    """
    if duration_sec <= 0:
        return 60

    # целевое количество столбиков
    target_bins = 10
    raw = duration_sec / target_bins

    # округляем до «человеческих» значений
    for candidate in (1, 2, 5, 10, 15, 30, 60, 120, 300, 600):
        if raw <= candidate:
            return candidate
    return int(raw)


def plot_intensity(
    per_minute: dict[int, int],
    out_path: Path,
    duration_sec: float = 0.0,
    bucket_sec: int = 60,
    dpi: int = 120,
    color: str = "#3b82f6",
) -> None:
    """Строит столбчатый график интенсивности.

    Args:
        per_minute: {номер_бакета: количество}. Ключи — целые индексы
            бакетов (0, 1, 2, ...), а не обязательно минуты.
        duration_sec: длительность видео — нужна для подписи оси X.
        bucket_sec: размер одного бакета в секундах (для подписи оси X).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not per_minute:
        minutes, counts = [0], [0]
        max_idx = 0
    else:
        max_idx = max(per_minute)
        indices = list(range(max_idx + 1))
        counts = [per_minute.get(i, 0) for i in indices]
        minutes = indices

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(minutes, counts, color=color, width=0.7, edgecolor="white")

    # --- Явные границы оси X без отрицательных значений ---
    ax.set_xlim(-0.6, max_idx + 0.6)
    # Целочисленные деления по X
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True, nbins=12))

    # --- Ось Y: всегда от 0, с запасом сверху ---
    ymax = max(counts) if counts else 1
    ax.set_ylim(0, max(1, ymax * 1.15))
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))

    # --- Подписи осей с учётом фактического размера бакета ---
    if bucket_sec < 60:
        ax.set_xlabel(f"Время с начала видео, окно {bucket_sec} с")
    else:
        ax.set_xlabel(f"Время с начала видео, окно {bucket_sec // 60} мин")

    ax.set_ylabel("Пешеходов за окно")
    ax.set_title(
        f"Интенсивность пешеходного трафика "
        f"(всего {sum(counts)} событий, {duration_sec:.1f} с видео)"
    )
    ax.grid(axis="y", linestyle="--", alpha=0.4)

    # На столбиках — числовые значения (если их немного)
    if len(minutes) <= 15:
        for x, y in zip(minutes, counts):
            if y > 0:
                ax.text(x, y, str(y), ha="center", va="bottom",
                        fontsize=9, color="#1e3a8a")

    fig.tight_layout()
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
