import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.cleanup import CleanupItem, CleanupOperation

RECOVERY_ROOT = Path.home() / "AI-DAM-Recovery"


def preview_cleanup(
    db: Session,
    asset_ids: list[int],
) -> dict:
    if not asset_ids:
        return {
            "asset_count": 0,
            "total_size_bytes": 0,
            "items": [],
        }

    assets = db.scalars(
        select(Asset).where(
            Asset.id.in_(asset_ids),
            Asset.is_missing.is_(False),
        )
    ).all()

    items = []
    total_size = 0

    for asset in assets:
        path = Path(asset.path)
        exists = path.exists() and path.is_file()

        item = {
            "asset_id": asset.id,
            "name": asset.name,
            "path": asset.path,
            "size_bytes": asset.size_bytes,
            "exists": exists,
            "action": "MOVE_TO_RECOVERY" if exists else "SKIP_MISSING",
        }

        items.append(item)

        if exists:
            total_size += asset.size_bytes

    return {
        "asset_count": len(items),
        "total_size_bytes": total_size,
        "items": items,
    }


def execute_cleanup(
    db: Session,
    asset_ids: list[int],
) -> dict:
    if not asset_ids:
        raise ValueError("At least one asset must be selected.")

    assets = db.scalars(
        select(Asset).where(
            Asset.id.in_(asset_ids),
            Asset.is_missing.is_(False),
        )
    ).all()

    if not assets:
        raise ValueError("No valid assets were found.")

    operation = CleanupOperation(
        status="RUNNING",
        action="MOVE_TO_RECOVERY",
        asset_count=len(assets),
        total_size_bytes=0,
        created_at=datetime.now(timezone.utc),
    )

    db.add(operation)
    db.flush()

    moved_count = 0
    total_size = 0

    for asset in assets:
        original_path = Path(asset.path)

        item = CleanupItem(
            operation_id=operation.id,
            asset_id=asset.id,
            original_path=asset.path,
            size_bytes=asset.size_bytes,
            status="PENDING",
        )

        db.add(item)
        db.flush()

        if not original_path.exists():
            asset.is_missing = True
            item.status = "SKIPPED"
            item.error_message = "File no longer exists."
            continue

        if not original_path.is_file():
            item.status = "SKIPPED"
            item.error_message = "Indexed path is not a file."
            continue

        try:
            recovery_folder = RECOVERY_ROOT / f"operation_{operation.id}"
            recovery_folder.mkdir(parents=True, exist_ok=True)
            recovery_name = f"{asset.id}_{uuid4().hex}_{original_path.name}"
            recovery_path = recovery_folder / recovery_name

            shutil.move(str(original_path), str(recovery_path))
            item.recovery_path = str(recovery_path)
            item.status = "MOVED"
            asset.is_missing = True
            moved_count += 1
            total_size += asset.size_bytes

        except (OSError, PermissionError) as exc:
            item.status = "FAILED"
            item.error_message = str(exc)

    operation.asset_count = moved_count
    operation.total_size_bytes = total_size
    operation.status = "COMPLETED" if moved_count > 0 else "FAILED"
    operation.completed_at = datetime.now(timezone.utc)

    db.commit()

    return {
        "operation_id": operation.id,
        "status": operation.status,
        "moved_files": moved_count,
        "total_size_bytes": total_size,
    }


def restore_operation(
    db: Session,
    operation_id: int,
) -> dict:
    items = db.scalars(
        select(CleanupItem).where(
            CleanupItem.operation_id == operation_id,
            CleanupItem.status == "MOVED",
        )
    ).all()

    if not items:
        raise ValueError("No recoverable files found for this operation.")

    restored_count = 0
    failed_count = 0

    for item in items:
        if not item.recovery_path:
            continue

        recovery_path = Path(item.recovery_path)
        original_path = Path(item.original_path)

        if not recovery_path.exists():
            item.status = "RESTORE_FAILED"
            item.error_message = "Recovery file no longer exists."
            failed_count += 1
            continue

        try:
            original_path.parent.mkdir(parents=True, exist_ok=True)

            if original_path.exists():
                item.status = "RESTORE_FAILED"
                item.error_message = "Original path already exists."
                failed_count += 1
                continue

            shutil.move(str(recovery_path), str(original_path))
            asset = db.get(Asset, item.asset_id)

            if asset:
                asset.is_missing = False

            item.status = "RESTORED"
            restored_count += 1

        except (OSError, PermissionError) as exc:
            item.status = "RESTORE_FAILED"
            item.error_message = str(exc)
            failed_count += 1

    db.commit()

    return {
        "operation_id": operation_id,
        "restored_files": restored_count,
        "failed_files": failed_count,
    }