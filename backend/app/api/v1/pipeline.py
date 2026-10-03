"""Pipeline orchestration API endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...core.config import get_settings
from ...core.dependencies import get_store
from ...services.analysis import AnalysisService
from ...storage.event_store import EventStore

router = APIRouter()


class PipelineRunRequest(BaseModel):
    data_root: Optional[str] = Field(
        None,
        description="Path to log dataset directory. Defaults to configured data root.",
    )
    reset_first: bool = Field(
        True,
        description="Whether to clear existing tables before re-ingesting.",
    )
    temporal_window_seconds: float = Field(
        10.0,
        ge=0.1,
        le=300.0,
        description="Window in seconds for evaluating proximity rules.",
    )


@router.post("/run")
async def run_pipeline(
    req: PipelineRunRequest = PipelineRunRequest(),
    store: EventStore = Depends(get_store),
) -> dict[str, Any]:
    """
    Trigger the complete analysis pipeline:
    1. Ingestion of raw logs across all nodes & families
    2. DuckDB normalized storage
    3. Deterministic correlation & graph generation
    4. Incident reconstruction & evidence building
    """
    settings = get_settings()
    data_path = Path(req.data_root) if req.data_root else settings.data_root_resolved

    if not data_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Data directory '{data_path}' does not exist.",
        )

    service = AnalysisService(store, temporal_window_seconds=req.temporal_window_seconds)

    try:
        summary = service.run_full_pipeline(
            data_root=data_path,
            reset_first=req.reset_first,
        )
        return {
            "status": "success",
            "summary": summary,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis pipeline execution failed: {type(exc).__name__}: {exc}",
        )
