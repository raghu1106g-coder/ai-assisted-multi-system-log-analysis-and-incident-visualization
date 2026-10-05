"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import router as v1_router
from .core.config import get_settings
from .core.dependencies import set_global_store
from .core.logging import configure_logging, get_logger
from .storage.event_store import EventStore

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    settings = get_settings()
    configure_logging(settings.log_level)

    # Initialize DuckDB connection
    store = EventStore(settings.duckdb_path_resolved)
    store.connect()
    set_global_store(store)
    app.state.store = store

    logger.info("application_started", port=settings.port, db=str(settings.duckdb_path_resolved))
    yield

    # Shutdown
    store.close()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="PS3 Log Analyzer",
        description=(
            "AI-assisted multi-system log analysis and incident visualization. "
            "Synthetic prototype dataset — not real aviation data."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS — frontend origins only; never expose API key
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(v1_router, prefix="/api/v1")

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)

