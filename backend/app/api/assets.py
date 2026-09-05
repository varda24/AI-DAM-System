from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Asset

router = APIRouter(
    prefix="/api/assets",
    tags=["Assets"],
)

@router.get("")
def list_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    file_type: str | None = Query(None),
    sort_by: str = Query("modified_at"),
    sort_order: str = Query("desc"),
    include_missing: bool = Query(False),
    db: Session = Depends(get_db),
):
    query = select(Asset)

    # Exclude missing files by default.
    if not include_missing:
        query = query.where(Asset.is_missing.is_(False))

    # Search by file name or path.
    if search:
        search_pattern = f"%{search}%"

        query = query.where(
            or_(
                Asset.name.ilike(search_pattern),
                Asset.path.ilike(search_pattern),
            )
        )

    # Filter by file type.
    if file_type:
        query = query.where(
            Asset.file_type == file_type.lower()
        )

    # Allowed sorting fields.
    sort_columns = {
        "name": Asset.name,
        "size_bytes": Asset.size_bytes,
        "created_at": Asset.created_at,
        "modified_at": Asset.modified_at,
        "accessed_at": Asset.accessed_at,
        "file_type": Asset.file_type,
    }

    sort_column = sort_columns.get(
        sort_by,
        Asset.modified_at,
    )

    if sort_order.lower() == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))

    # Total matching assets before pagination.
    count_query = select(
        func.count()
    ).select_from(
        query.order_by(None).subquery()
    )

    total = db.scalar(count_query) or 0

    offset = (page - 1) * page_size

    assets = db.scalars(
        query
        .offset(offset)
        .limit(page_size)
    ).all()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (
            (total + page_size - 1) // page_size
            if total
            else 0
        ),
        "items": [
            {
                "id": asset.id,
                "source": asset.source,
                "name": asset.name,
                "path": asset.path,
                "extension": asset.extension,
                "mime_type": asset.mime_type,
                "file_type": asset.file_type,
                "size_bytes": asset.size_bytes,
                "created_at": (
                    asset.created_at.isoformat()
                    if asset.created_at
                    else None
                ),
                "modified_at": (
                    asset.modified_at.isoformat()
                    if asset.modified_at
                    else None
                ),
                "accessed_at": (
                    asset.accessed_at.isoformat()
                    if asset.accessed_at
                    else None
                ),
                "is_missing": asset.is_missing,
                "last_scanned_at": (
                    asset.last_scanned_at.isoformat()
                    if asset.last_scanned_at
                    else None
                ),
            }
            for asset in assets
        ],
    }

@router.get("/{asset_id}/preview")
def preview_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_id)

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found.",
        )

    if asset.source != "local_pc":
        raise HTTPException(
            status_code=400,
            detail="Preview is currently available only for local PC assets.",
        )

    file_path = Path(asset.path)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail="The indexed file no longer exists on the filesystem.",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=400,
            detail="The indexed path is not a file.",
        )

    return FileResponse(
        path=file_path,
        media_type=asset.mime_type or "application/octet-stream",
        filename=asset.name,
        content_disposition_type="inline",
    )