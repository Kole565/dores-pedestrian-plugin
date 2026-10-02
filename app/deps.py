"""FastAPI-зависимости."""
from __future__ import annotations

from fastapi import Request

from .jobs import JobRunner
from .store import JobStore


def get_store(request: Request) -> JobStore:
    return request.app.state.store


def get_runner(request: Request) -> JobRunner:
    return request.app.state.runner
