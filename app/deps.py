# app/deps.py
"""FastAPI-зависимости."""
from __future__ import annotations

from fastapi import Request

from .jobs import JobRunner
from .lines_store import LinesStore
from .store import JobStore


def get_store(request: Request) -> JobStore:
    return request.app.state.store


def get_runner(request: Request) -> JobRunner:
    return request.app.state.runner


def get_lines_store(request: Request) -> LinesStore:
    return request.app.state.lines_store
