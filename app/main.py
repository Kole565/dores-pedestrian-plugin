"""FastAPI-приложение: сборка роутеров, lifespan, CORS."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .schemas import HealthResponse, LimitsResponse
from .settings import settings
from .store import JobStore

from . import jobs as jobs_module
from . import streams as streams_module
from . import ws as ws_module

from .lines_store import LinesStore

from .routers import jobs as jobs_router
from .routers import lines as lines_router
from .routers import streams as streams_router


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Start backend. data_dir=%s", settings.data_dir)

    store = JobStore(settings.jobs_json)
    zombies = store.mark_zombies_as_failed()
    if zombies:
        logger.warning("Mark %d 'zombie'-jobs as failed", zombies)

    lines_store = LinesStore(settings.lines_json)

    # дефолтный конфиг при первом старте
    from core import config as core_config
    default_cfg = lines_store.ensure_default(core_config.DEFAULT_VIRTUAL_LINES)
    logger.info("Default lines config: id=%s name=%r", default_cfg.id, default_cfg.name)

    runner = jobs_module.init_runner(store)
    stream_manager = streams_module.init_manager()

    app.state.store = store
    app.state.lines_store = lines_store
    app.state.runner = runner
    app.state.stream_manager = stream_manager

    yield

    logger.info("Остановка backend...")
    streams_module.shutdown_manager()
    jobs_module.shutdown_runner()


def create_app() -> FastAPI:
    app = FastAPI(
        title="DORES Pedestrian Flow API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- служебное ---
    @app.get("/api/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse()

    @app.get("/api/config/limits", response_model=LimitsResponse, tags=["system"])
    def limits() -> LimitsResponse:
        return LimitsResponse(
            max_upload_bytes=settings.max_upload_bytes,
            allowed_video_ext=list(settings.allowed_video_ext),
        )

    # --- бизнес-роутеры ---
    app.include_router(jobs_router.router)
    app.include_router(lines_router.router)
    app.include_router(streams_router.router)
    app.include_router(ws_module.router)

    return app

app = create_app()
