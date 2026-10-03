from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.duplicate import DuplicateGroup
from app.models.storage_snapshot import StorageSnapshot


def create_storage_snapshot(
    db: Session,
    source: str = "local_pc",
) -> StorageSnapshot:
    """Create a storage snapshot from the indexed asset database.

    This function intentionally does not access or scan the filesystem.
    """

    base_filter = (
        Asset.source == source,
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
    ).all()

    type_totals = {
        "image": [0, 0],
        "video": [0, 0],
        "document": [0, 0],
        "other": [0, 0],
    }

    for file_type, file_count, size_bytes in type_rows:
        category = file_type if file_type in type_totals else "other"

        type_totals[category][0] += int(file_count or 0)
        type_totals[category][1] += int(size_bytes or 0)

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

    snapshot = StorageSnapshot(
        captured_at=datetime.now(timezone.utc),
        source=source,
        total_files=int(total_files),
        total_bytes=int(total_bytes),
        duplicate_savings_bytes=int(duplicate_savings),
        image_files=type_totals["image"][0],
        image_bytes=type_totals["image"][1],
        video_files=type_totals["video"][0],
        video_bytes=type_totals["video"][1],
        document_files=type_totals["document"][0],
        document_bytes=type_totals["document"][1],
        other_files=type_totals["other"][0],
        other_bytes=type_totals["other"][1],
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)

    return snapshot
