"""Pipeline orchestration API endpoints."""

from __future__ import annotations

import io
import os
import re
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from ...core.config import get_settings
from ...core.dependencies import get_store
from ...ingestion.engine import _identify_family, _identify_node, discover_log_files
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


def _scan_dataset_dir(path: Path, name: str, dataset_id: str) -> dict[str, Any]:
    """Scan a directory for log files, nodes, and families."""
    if not path.exists():
        return {
            "id": dataset_id,
            "name": name,
            "path": str(path),
            "exists": False,
            "files": [],
            "nodes": [],
            "log_families": [],
            "file_count": 0,
        }

    log_files = discover_log_files(path)
    nodes = sorted(
        list(
            {
                node
                for p in log_files
                if (node := _identify_node(p)) is not None
            }
        )
    )
    families = sorted(
        list(
            {
                fam
                for p in log_files
                if (fam := _identify_family(p)) is not None
            }
        )
    )

    return {
        "id": dataset_id,
        "name": name,
        "path": str(path),
        "exists": True,
        "files": [str(p.relative_to(path)) for p in log_files],
        "nodes": nodes,
        "log_families": families,
        "file_count": len(log_files),
    }


@router.get("/datasets")
async def list_datasets() -> dict[str, Any]:
    """List all available datasets (pre-packaged and user-uploaded)."""
    settings = get_settings()
    datasets: list[dict[str, Any]] = []

    # 1. Dataset 2 (Multi-Incident Synthetic Dataset)
    d2_path = settings.project_root / "ps3_dataset_2"
    if d2_path.exists():
        datasets.append(
            _scan_dataset_dir(d2_path, "Dataset 2 (Multi-Incident Scenario)", "ps3_dataset_2")
        )

    # 2. Dataset 1 (Primary Baseline)
    d1_path = settings.project_root / "data"
    if d1_path.exists():
        # Only list if it has log files
        d1_info = _scan_dataset_dir(d1_path, "Dataset 1 (Primary Baseline)", "dataset_1")
        if d1_info["file_count"] > 0:
            datasets.append(d1_info)

    # 3. User Uploads in data/uploads/
    uploads_dir = settings.project_root / "data" / "uploads"
    if uploads_dir.exists():
        for item in sorted(uploads_dir.iterdir()):
            if item.is_dir():
                info = _scan_dataset_dir(item, f"Uploaded: {item.name}", f"upload_{item.name}")
                if info["file_count"] > 0:
                    datasets.append(info)

    return {"datasets": datasets}


@router.post("/upload")
async def upload_dataset(
    dataset_name: Optional[str] = Form(None),
    files: List[UploadFile] = File(...),
) -> dict[str, Any]:
    """
    Upload a multi-node log dataset.
    Supports either:
    - Multiple individual log files with directory paths in filenames (e.g. NODE_A/operator.log)
    - A single .zip archive containing the dataset directory tree
    """
    settings = get_settings()
    upload_id = dataset_name or f"dataset_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    # Clean dataset name for directory
    clean_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', upload_id)
    target_dir = settings.project_root / "data" / "uploads" / clean_id
    target_dir.mkdir(parents=True, exist_ok=True)

    saved_files: list[str] = []

    for file in files:
        filename = file.filename or "unknown.log"
        content = await file.read()

        # If it's a zip archive, extract it
        if filename.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    for member in zf.namelist():
                        # Guard against path traversal
                        if ".." in member or member.startswith("/"):
                            continue
                        extracted_path = target_dir / member
                        if member.endswith("/"):
                            extracted_path.mkdir(parents=True, exist_ok=True)
                        else:
                            extracted_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(extracted_path, "wb") as f_out:
                                f_out.write(zf.read(member))
                            if member.endswith(".log"):
                                saved_files.append(member)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Invalid zip file: {exc}")
        else:
            # Normalize path delimiters in filename (e.g. NODE_A/operator.log)
            normalized_rel = filename.replace("\\", "/").lstrip("/")
            file_dest = target_dir / normalized_rel
            file_dest.parent.mkdir(parents=True, exist_ok=True)
            with open(file_dest, "wb") as f_out:
                f_out.write(content)
            saved_files.append(normalized_rel)

    # Discover and validate structure
    dataset_info = _scan_dataset_dir(target_dir, upload_id, clean_id)

    return {
        "status": "success",
        "dataset": dataset_info,
        "message": f"Successfully uploaded {dataset_info['file_count']} log files into {clean_id}",
    }


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

    # If data_path is relative, resolve from project root
    if not data_path.is_absolute():
        data_path = settings.project_root / data_path

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
