from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Asset
from app.models.duplicate import DuplicateGroup
from app.models.storage_snapshot import StorageSnapshot
from app.services.storage_history import create_storage_snapshot

router = APIRouter(
    prefix="/api/storage",
    tags=["Storage Intelligence"],
)


@router.get("/summary")
def storage_summary(db: Session = Depends(get_db)):
    base_filter = (
        Asset.source == "local_pc",
        Asset.is_missing.is_(False),
    )

    total_files = (
        db.scalar(
            select(func.count(Asset.id)).where(*base_filter)
        )
        or 0
    )

    total_bytes = (
        db.scalar(
            select(func.coalesce(func.sum(Asset.size_bytes), 0))
            .where(*base_filter)
        )
        or 0
    )

    type_rows = db.execute(
        select(
            Asset.file_type,
            func.count(Asset.id),
            func.coalesce(func.sum(Asset.size_bytes), 0),
        )
        .where(*base_filter)
        .group_by(Asset.file_type)
        .order_by(desc(func.sum(Asset.size_bytes)))
    ).all()

    largest_assets = db.scalars(
        select(Asset)
        .where(*base_filter)
        .order_by(desc(Asset.size_bytes))
        .limit(20)
    ).all()

    duplicate_savings = (
        db.scalar(
            select(
                func.coalesce(
                    func.sum(DuplicateGroup.potential_savings_bytes),
                    0,
                )
            )
        )
        or 0
    )

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    old_files = db.scalars(
        select(Asset)
        .where(
            *base_filter,
            Asset.modified_at.is_not(None),
            Asset.modified_at < thirty_days_ago,
        )
        .order_by(Asset.modified_at.asc())
        .limit(50)
    ).all()

    def asset_summary(asset: Asset) -> dict:
        return {
            "id": asset.id,
            "name": asset.name,
            "path": asset.path,
            "size_bytes": asset.size_bytes,
            "file_type": asset.file_type,
            "modified_at": (
                asset.modified_at.isoformat()
                if asset.modified_at
                else None
            ),
        }

    return {
        "total_files": total_files,
        "total_bytes": total_bytes,
        "duplicate_savings_bytes": duplicate_savings,
        "by_file_type": [
            {
                "file_type": file_type,
                "file_count": file_count,
                "size_bytes": size_bytes,
            }
            for file_type, file_count, size_bytes in type_rows
        ],
        "largest_files": [
            asset_summary(asset)
            for asset in largest_assets
        ],
        "old_files": [
            asset_summary(asset)
            for asset in old_files
        ],
    }


@router.post("/snapshot")
def create_snapshot(
    source: str = Query("local_pc"),
    db: Session = Depends(get_db),
):
    """Create a historical storage snapshot from the indexed database."""

    if not source.strip():
        raise HTTPException(
            status_code=400,
            detail="Source must not be empty.",
        )

    snapshot = create_storage_snapshot(
        db=db,
        source=source,
    )

    return {
        "id": snapshot.id,
        "captured_at": snapshot.captured_at.isoformat(),
        "source": snapshot.source,
        "total_files": snapshot.total_files,
        "total_bytes": snapshot.total_bytes,
        "duplicate_savings_bytes": snapshot.duplicate_savings_bytes,
        "image_files": snapshot.image_files,
        "image_bytes": snapshot.image_bytes,
        "video_files": snapshot.video_files,
        "video_bytes": snapshot.video_bytes,
        "document_files": snapshot.document_files,
        "document_bytes": snapshot.document_bytes,
        "other_files": snapshot.other_files,
        "other_bytes": snapshot.other_bytes,
    }


@router.get("/history")
def storage_history(
    source: str = Query("local_pc"),
    days: int = Query(30),
    db: Session = Depends(get_db),
):
    """Return storage snapshots from the requested historical window."""

    allowed_days = {7, 30, 90, 365}

    if days not in allowed_days:
        raise HTTPException(
            status_code=400,
            detail="days must be one of: 7, 30, 90, 365.",
        )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    snapshots = db.scalars(
        select(StorageSnapshot)
        .where(
            StorageSnapshot.source == source,
            StorageSnapshot.captured_at >= since,
        )
        .order_by(StorageSnapshot.captured_at.asc())
    ).all()

    return {
        "source": source,
        "days": days,
        "snapshot_count": len(snapshots),
        "snapshots": [
            {
                "id": snapshot.id,
                "captured_at": snapshot.captured_at.isoformat(),
                "source": snapshot.source,
                "total_files": snapshot.total_files,
                "total_bytes": snapshot.total_bytes,
                "duplicate_savings_bytes": (
                    snapshot.duplicate_savings_bytes
                ),
                "image_files": snapshot.image_files,
                "image_bytes": snapshot.image_bytes,
                "video_files": snapshot.video_files,
                "video_bytes": snapshot.video_bytes,
                "document_files": snapshot.document_files,
                "document_bytes": snapshot.document_bytes,
                "other_files": snapshot.other_files,
                "other_bytes": snapshot.other_bytes,
            }
            for snapshot in snapshots
        ],
    }


@router.get("/history/summary")
def storage_history_summary(
    source: str = Query("local_pc"),
    days: int = Query(30),
    db: Session = Depends(get_db),
):
    """Return historical storage change statistics."""

    allowed_days = {7, 30, 90, 365}

    if days not in allowed_days:
        raise HTTPException(
            status_code=400,
            detail="days must be one of: 7, 30, 90, 365.",
        )

    since = datetime.now(timezone.utc) - timedelta(days=days)

    snapshots = db.scalars(
        select(StorageSnapshot)
        .where(
            StorageSnapshot.source == source,
            StorageSnapshot.captured_at >= since,
        )
        .order_by(StorageSnapshot.captured_at.asc())
    ).all()

    if not snapshots:
        return {
            "source": source,
            "days": days,
            "snapshot_count": 0,
            "first_snapshot": None,
            "latest_snapshot": None,
            "current_total_bytes": 0,
            "previous_total_bytes": 0,
            "change_bytes": 0,
            "change_percent": 0,
            "current_total_files": 0,
            "previous_total_files": 0,
            "change_files": 0,
            "current_duplicate_savings_bytes": 0,
            "previous_duplicate_savings_bytes": 0,
        }

    first = snapshots[0]
    latest = snapshots[-1]

    previous = snapshots[-2] if len(snapshots) >= 2 else None

    previous_bytes = (
        previous.total_bytes
        if previous
        else first.total_bytes
    )

    previous_files = (
        previous.total_files
        if previous
        else first.total_files
    )

    previous_duplicate_savings = (
        previous.duplicate_savings_bytes
        if previous
        else first.duplicate_savings_bytes
    )

    change_bytes = latest.total_bytes - previous_bytes
    change_files = latest.total_files - previous_files

    change_percent = (
        (change_bytes / previous_bytes) * 100
        if previous_bytes > 0
        else 0
    )

    return {
        "source": source,
        "days": days,
        "snapshot_count": len(snapshots),
        "first_snapshot": first.captured_at.isoformat(),
        "latest_snapshot": latest.captured_at.isoformat(),
        "current_total_bytes": latest.total_bytes,
        "previous_total_bytes": previous_bytes,
        "change_bytes": change_bytes,
        "change_percent": change_percent,
        "current_total_files": latest.total_files,
        "previous_total_files": previous_files,
        "change_files": change_files,
        "current_duplicate_savings_bytes": (
            latest.duplicate_savings_bytes
        ),
        "previous_duplicate_savings_bytes": (
            previous_duplicate_savings
        ),
    }
