"""V1 API Router assembly."""

from __future__ import annotations

from fastapi import APIRouter

from .events import router as events_router
from .export import router as export_router
from .incidents import router as incidents_router
from .pipeline import router as pipeline_router
from .relationships import router as relationships_router
from .stats import router as stats_router

router = APIRouter()

router.include_router(events_router, prefix="/events", tags=["Events"])
router.include_router(incidents_router, prefix="/incidents", tags=["Incidents"])
router.include_router(relationships_router, prefix="/relationships", tags=["Relationships"])
router.include_router(pipeline_router, prefix="/pipeline", tags=["Pipeline"])
router.include_router(stats_router, prefix="/stats", tags=["Statistics"])
router.include_router(export_router, prefix="/export", tags=["Export"])
