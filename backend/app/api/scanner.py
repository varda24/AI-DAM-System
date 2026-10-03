import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Asset
from app.services.analysis_jobs import enqueue_asset_jobs, start_analysis_worker
from app.services.local_scanner import (
    estimate_local_scan,
    list_local_roots,
    list_local_subdirectories,
    scan_local_folder,
    search_local_directories,
)
from app.services.storage_history import create_storage_snapshot


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/api/scanner",
    tags=["Scanner"],
)


class ScanRequest(BaseModel):
    folder_path: str | None = None
    included_paths: list[str] = Field(default_factory=list)
    excluded_paths: list[str] = Field(default_factory=list)


@router.get("/local/tree")
def local_folder_tree(parent_path: str | None = None):
    if parent_path is None:
        return {"roots": list_local_roots(), "folders": []}
    try:
        return {
            "roots": [],
            "parent_path": parent_path,
            "folders": list_local_subdirectories(parent_path),
        }
    except NotADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/local/tree/search")
def local_folder_search(q: str = ""):
    return search_local_directories(q)


@router.post("/local/estimate")
def local_scan_estimate(
    request: ScanRequest,
    db: Session = Depends(get_db),
):
    included_paths = request.included_paths or (
        [request.folder_path] if request.folder_path else []
    )
    return estimate_local_scan(
        db=db,
        included_paths=included_paths,
        excluded_paths=request.excluded_paths,
    )


@router.post("/local")
def scan_local(
    request: ScanRequest,
    db: Session = Depends(get_db),
):
    """
    Scan a local folder and update the unified asset index.

    After a successful scan, create one storage snapshot from the
    resulting database state.

    Storage-history failure does not invalidate a successful scan.
    """

    try:
        included_paths = request.included_paths or (
            [request.folder_path] if request.folder_path else []
        )
        if not included_paths:
            raise HTTPException(
                status_code=422,
                detail="Select at least one folder to scan.",
            )

        scan_result = scan_local_folder(
            db=db,
            folder_path=included_paths,
            excluded_paths=request.excluded_paths,
        )

        analysis_asset_ids = scan_result.pop("analysis_asset_ids", [])
        if analysis_asset_ids:
            assets_for_analysis = db.scalars(
                select(Asset).where(Asset.id.in_(analysis_asset_ids))
            ).all()
            scan_result["analysis_jobs"] = enqueue_asset_jobs(
                db=db,
                assets=assets_for_analysis,
            )
            start_analysis_worker()
        else:
            scan_result["analysis_jobs"] = {
                "queued": 0,
                "already_current": 0,
            }

        # ---------------------------------------------------------
        # Storage history
        # ---------------------------------------------------------
        #
        # The filesystem scan has completed successfully at this
        # point. The scanner service is responsible for committing
        # its asset changes before returning.
        #
        # The snapshot service reads the indexed database state.
        # It does NOT perform another filesystem scan.
        #
        try:
            snapshot = create_storage_snapshot(
                db=db,
                source="local_pc",
            )

            scan_result["storage_snapshot"] = {
                "id": snapshot.id,
                "captured_at": snapshot.captured_at.isoformat(),
                "total_files": snapshot.total_files,
                "total_bytes": snapshot.total_bytes,
                "duplicate_savings_bytes": (
                    snapshot.duplicate_savings_bytes
                ),
            }

        except Exception:
            # A history failure must never turn a successful
            # filesystem scan into a failed scan.
            logger.exception(
                "Storage snapshot creation failed after local scan."
            )

            scan_result["storage_snapshot"] = None

        return scan_result

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except NotADirectoryError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
