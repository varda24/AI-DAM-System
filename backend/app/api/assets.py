from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import asc, case, desc, func, literal, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Asset


router = APIRouter(
    prefix="/api/assets",
    tags=["Assets"],
)


def serialize_asset(asset: Asset) -> dict:
    result = {
        "id": asset.id,
        "source": asset.source,
        "source_account_id": asset.source_account_id,
        "source_folder_id": asset.source_folder_id,
        "web_view_link": asset.web_view_link,
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
        "sha256": asset.sha256,
        "perceptual_hash": asset.perceptual_hash,
        "last_scanned_at": (
            asset.last_scanned_at.isoformat()
            if asset.last_scanned_at
            else None
        ),
    }
    if asset.source == "google_drive":
        result.update({
            "drive_file_id": asset.source_file_id,
        })
    return result


@router.get("")
def list_assets(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    file_type: str | None = Query(None),
    source: str | None = Query(None),
    sort_by: str = Query("modified_at"),
    sort_order: str = Query("desc"),
    include_missing: bool = Query(False),
    folder: str | None = Query(None),
    db: Session = Depends(get_db),
):
    query = select(Asset)

    # Exclude missing files by default.
    if not include_missing:
        query = query.where(
            Asset.is_missing.is_(False)
        )

    if source:
        query = query.where(Asset.source == source)

    # Restrict results to a selected folder and its descendants.
    if folder:
        normalized_folder = str(
            Path(folder).resolve()
        ).rstrip("\\/")

        # PostgreSQL LIKE pattern.
        # Escape % and _ so folder names are treated literally.
        escaped_folder = (
            normalized_folder
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

        folder_pattern = f"{escaped_folder}\\\\%"

        query = query.where(
            or_(
                Asset.path == normalized_folder,
                Asset.path.ilike(
                    folder_pattern,
                    escape="\\",
                ),
            )
        )

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
        query = query.order_by(
            asc(sort_column)
        )
    else:
        query = query.order_by(
            desc(sort_column)
        )

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
        "folder": normalized_folder if folder else None,
        "items": [
            serialize_asset(asset)
            for asset in assets
        ],
    }


@router.get("/folders")
def list_folders(
    parent: str | None = Query(None),
    source: str | None = Query(None),
    include_missing: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Return indexed folders directly below the requested parent.

    This endpoint uses indexed asset paths rather than scanning the
    filesystem directly. That keeps folder navigation consistent with
    the DAM index.
    """

    query = select(
        Asset.path,
        Asset.source,
    )

    if not include_missing:
        query = query.where(
            Asset.is_missing.is_(False)
        )

    if source:
        query = query.where(
            Asset.source == source
        )

    normalized_parent = None

    if parent:
        normalized_parent = str(
            Path(parent).resolve()
        ).rstrip("\\/")

    if db.get_bind().dialect.name == "postgresql":
        normalized_path = func.replace(Asset.path, "\\", "/")

        if normalized_parent:
            parent_for_query = normalized_parent.replace("\\", "/").rstrip("/")
            remainder = func.substr(
                normalized_path,
                len(parent_for_query) + 2,
            )
            child_name = func.split_part(remainder, "/", 1)
            separator = "\\" if "\\" in normalized_parent else "/"
            folder_path = normalized_parent + separator + child_name

            folder_query = query.with_only_columns(
                folder_path.label("path"),
                Asset.source,
            ).where(
                func.left(
                    func.lower(normalized_path),
                    len(parent_for_query) + 1,
                )
                == (parent_for_query + "/").lower(),
                func.strpos(remainder, "/") > 0,
                child_name != "",
            ).distinct()
        else:
            first_part = func.split_part(normalized_path, "/", 1)
            second_part = func.split_part(normalized_path, "/", 2)
            folder_path = case(
                (
                    first_part.op("~")(r"^[A-Za-z]:$"),
                    first_part + literal("\\") + second_part,
                ),
                (
                    func.left(normalized_path, 1) == "/",
                    literal("/") + second_part,
                ),
                else_=first_part + literal("/") + second_part,
            )

            folder_query = query.with_only_columns(
                folder_path.label("path"),
                Asset.source,
            ).where(second_part != "").distinct()

        folders = {}
        for folder_path, asset_source in db.execute(folder_query).all():
            key = folder_path.lower()
            folders.setdefault(
                key,
                {
                    "path": folder_path,
                    "name": Path(folder_path).name or folder_path,
                    "source": asset_source,
                },
            )

        result = sorted(
            folders.values(),
            key=lambda item: item["path"].lower(),
        )

        return {
            "parent": normalized_parent,
            "folders": result,
            "total": len(result),
        }

    rows = db.execute(query).all()

    folders: dict[str, dict] = {}

    for asset_path, asset_source in rows:
        if not asset_path:
            continue

        path = Path(asset_path)

        try:
            asset_parent = str(
                path.parent.resolve()
            ).rstrip("\\/")
        except OSError:
            asset_parent = str(
                path.parent
            ).rstrip("\\/")

        # If a parent folder is selected, only inspect files
        # immediately inside that folder or its descendants.
        if normalized_parent:
            parent_lower = normalized_parent.lower()
            asset_path_lower = str(path).lower()

            if not (
                asset_path_lower == parent_lower
                or asset_path_lower.startswith(
                    parent_lower + "\\"
                )
            ):
                continue

            try:
                relative = path.relative_to(
                    Path(normalized_parent)
                )
            except ValueError:
                continue

            parts = relative.parts

            # We only want the immediate child folder.
            if len(parts) < 2:
                continue

            folder_path = str(
                Path(normalized_parent) / parts[0]
            )
        else:
            # No parent means show top-level directories.
            parts = path.parts

            if len(parts) < 2:
                continue

            # On Windows this preserves the drive root.
            if len(parts) >= 2 and parts[0].endswith(":"):
                folder_path = str(
                    Path(parts[0] + "\\") / parts[1]
                )
            else:
                folder_path = str(
                    Path(parts[0]) / parts[1]
                )

        folder_path = folder_path.rstrip("\\/")

        key = folder_path.lower()

        if key not in folders:
            folders[key] = {
                "path": folder_path,
                "name": Path(folder_path).name
                or folder_path,
                "source": asset_source,
            }

    result = sorted(
        folders.values(),
        key=lambda item: item["path"].lower(),
    )

    return {
        "parent": normalized_parent,
        "folders": result,
        "total": len(result),
    }


@router.get("/{asset_id}")
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_id)

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found.",
        )

    return serialize_asset(asset)


@router.get("/{asset_id}/preview")
def preview_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    asset = db.get(
        Asset,
        asset_id,
    )

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found.",
        )

    if asset.source != "local_pc":
        raise HTTPException(
            status_code=400,
            detail=(
                "Preview is currently available "
                "only for local PC assets."
            ),
        )

    file_path = Path(asset.path)

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "The indexed file no longer exists "
                "on the filesystem."
            ),
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=400,
            detail=(
                "The indexed path is not a file."
            ),
        )

    return FileResponse(
        path=file_path,
        media_type=(
            asset.mime_type
            or "application/octet-stream"
        ),
        filename=asset.name,
        content_disposition_type="inline",
    )
