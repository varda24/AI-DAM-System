from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Asset
from app.models.duplicate import DuplicateGroup

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

    total_files = db.scalar(select(func.count(Asset.id)).where(*base_filter)) or 0
    total_bytes = db.scalar(select(func.coalesce(func.sum(Asset.size_bytes), 0)).where(*base_filter)) or 0

    type_rows = db.execute(
        select(Asset.file_type, func.count(Asset.id), func.coalesce(func.sum(Asset.size_bytes), 0))
        .where(*base_filter)
        .group_by(Asset.file_type)
        .order_by(desc(func.sum(Asset.size_bytes)))
    ).all()

    largest_assets = db.scalars(
        select(Asset).where(*base_filter).order_by(desc(Asset.size_bytes)).limit(20)
    ).all()

    duplicate_savings = db.scalar(
        select(func.coalesce(func.sum(DuplicateGroup.potential_savings_bytes), 0))
    ) or 0

    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    old_files = db.scalars(
        select(Asset).where(
            *base_filter,
            Asset.modified_at.is_not(None),
            Asset.modified_at < thirty_days_ago,
        ).order_by(Asset.modified_at.asc()).limit(50)
    ).all()

    def asset_summary(asset: Asset) -> dict:
        return {
            "id": asset.id,
            "name": asset.name,
            "path": asset.path,
            "size_bytes": asset.size_bytes,
            "file_type": asset.file_type,
            "modified_at": asset.modified_at.isoformat() if asset.modified_at else None,
        }

    return {
        "total_files": total_files,
        "total_bytes": total_bytes,
        "duplicate_savings_bytes": duplicate_savings,
        "by_file_type": [
            {"file_type": file_type, "file_count": file_count, "size_bytes": size_bytes}
            for file_type, file_count, size_bytes in type_rows
        ],
        "largest_files": [asset_summary(asset) for asset in largest_assets],
        "old_files": [asset_summary(asset) for asset in old_files],
    }