from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Asset
from app.models.duplicate import DuplicateGroup, DuplicateMember
from app.services.duplicate_detector import detect_exact_duplicates

router = APIRouter(
    prefix="/api/duplicates",
    tags=["Duplicates"],
)


@router.post("/detect")
def run_duplicate_detection(
    hash_local_assets: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    return detect_exact_duplicates(db, hash_local_assets=hash_local_assets)


@router.get("")
def list_duplicate_groups(
    db: Session = Depends(get_db),
):
    groups = db.scalars(
        select(DuplicateGroup).order_by(
            DuplicateGroup.potential_savings_bytes.desc()
        )
    ).all()

    result = []

    for group in groups:
        assets = db.scalars(
            select(Asset)
            .join(
                DuplicateMember,
                DuplicateMember.asset_id == Asset.id,
            )
            .where(
                DuplicateMember.duplicate_group_id == group.id
            )
            .order_by(Asset.id)
        ).all()

        result.append(
            {
                "id": group.id,
                "sha256": group.sha256,
                "file_size_bytes": group.file_size_bytes,
                "file_count": group.file_count,
                "potential_savings_bytes": group.potential_savings_bytes,
                "created_at": (
                    group.created_at.isoformat()
                    if group.created_at
                    else None
                ),
                "assets": [
                    {
                        "id": asset.id,
                        "source": asset.source,
                        "source_account_id": asset.source_account_id,
                        "source_folder_id": asset.source_folder_id,
                        "web_view_link": asset.web_view_link,
                        "drive_file_id": (
                            asset.source_file_id
                            if asset.source == "google_drive"
                            else None
                        ),
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
                    for asset in assets
                ],
            }
        )

    return {
        "total_groups": len(result),
        "groups": result,
    }


@router.get("/summary")
def duplicate_summary(
    db: Session = Depends(get_db),
):
    group_count = db.scalar(
        select(func.count(DuplicateGroup.id))
    ) or 0

    duplicate_files = db.scalar(
        select(
            func.coalesce(
                func.sum(DuplicateGroup.file_count),
                0,
            )
        )
    ) or 0

    potential_savings = db.scalar(
        select(
            func.coalesce(
                func.sum(
                    DuplicateGroup.potential_savings_bytes
                ),
                0,
            )
        )
    ) or 0

    return {
        "duplicate_groups": group_count,
        "duplicate_files": duplicate_files,
        "potential_savings_bytes": potential_savings,
    }