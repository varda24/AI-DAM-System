from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.cleanup import CleanupItem, CleanupOperation
from app.services.cleanup_service import (
    execute_cleanup,
    preview_cleanup,
    restore_operation,
)

router = APIRouter(
    prefix="/api/cleanup",
    tags=["Cleanup"],
)


class CleanupRequest(BaseModel):
    asset_ids: list[int] = Field(min_length=1)


@router.post("/preview")
def cleanup_preview(
    request: CleanupRequest,
    db: Session = Depends(get_db),
):
    return preview_cleanup(db, request.asset_ids)


@router.post("/execute")
def cleanup_execute(
    request: CleanupRequest,
    db: Session = Depends(get_db),
):
    try:
        return execute_cleanup(db, request.asset_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{operation_id}/restore")
def cleanup_restore(
    operation_id: int,
    db: Session = Depends(get_db),
):
    try:
        return restore_operation(db, operation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/history")
def cleanup_history(
    db: Session = Depends(get_db),
):
    operations = db.scalars(
        select(CleanupOperation).order_by(desc(CleanupOperation.created_at))
    ).all()

    return {
        "operations": [
            {
                "id": operation.id,
                "status": operation.status,
                "action": operation.action,
                "asset_count": operation.asset_count,
                "total_size_bytes": operation.total_size_bytes,
                "created_at": operation.created_at.isoformat() if operation.created_at else None,
                "completed_at": operation.completed_at.isoformat() if operation.completed_at else None,
                "error_message": operation.error_message,
            }
            for operation in operations
        ]
    }


@router.get("/{operation_id}")
def cleanup_operation_details(
    operation_id: int,
    db: Session = Depends(get_db),
):
    operation = db.get(CleanupOperation, operation_id)

    if operation is None:
        raise HTTPException(status_code=404, detail="Cleanup operation not found.")

    items = db.scalars(
        select(CleanupItem).where(CleanupItem.operation_id == operation_id)
    ).all()

    return {
        "id": operation.id,
        "status": operation.status,
        "action": operation.action,
        "asset_count": operation.asset_count,
        "total_size_bytes": operation.total_size_bytes,
        "created_at": operation.created_at.isoformat() if operation.created_at else None,
        "completed_at": operation.completed_at.isoformat() if operation.completed_at else None,
        "items": [
            {
                "id": item.id,
                "asset_id": item.asset_id,
                "original_path": item.original_path,
                "recovery_path": item.recovery_path,
                "size_bytes": item.size_bytes,
                "status": item.status,
                "error_message": item.error_message,
            }
            for item in items
        ],
    }