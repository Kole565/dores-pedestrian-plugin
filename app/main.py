"""FastAPI-приложение: сборка роутеров, lifespan, CORS."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import jobs as jobs_module
from .schemas import HealthResponse, LimitsResponse
from .settings import settings
from .store import JobStore

# Роутеры по этапам
from .routers import jobs as jobs_router


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    logger.info("Старт backend. data_dir=%s", settings.data_dir)

    store = JobStore(settings.jobs_json)
    zombies = store.mark_zombies_as_failed()
    if zombies:
        logger.warning("Помечено %d 'зомби'-задач как failed", zombies)

    runner = jobs_module.init_runner(store)

    app.state.store = store
    app.state.runner = runner

    yield

    # --- shutdown ---
    logger.info("Остановка backend...")
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

    return app


app = create_app()
