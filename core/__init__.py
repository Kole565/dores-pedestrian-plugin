"""Переиспользуемое ядро пайплайна: детектор, счётчик, runner'ы."""
from .detector import Detector
from .lines import VirtualLine, lines_from_config, lines_to_config
from .runner import run_offline, run_stream, RunResult

__all__ = [
    "Detector",
    "VirtualLine", "lines_from_config", "lines_to_config",
    "run_offline", "run_stream", "RunResult",
]
