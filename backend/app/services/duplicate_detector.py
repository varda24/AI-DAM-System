from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.duplicate import DuplicateGroup, DuplicateMember
from app.services.hashing import calculate_sha256


def detect_exact_duplicates(db: Session) -> dict:
    assets = db.scalars(
        select(Asset).where(
            Asset.source == "local_pc",
            Asset.is_missing.is_(False),
        )
    ).all()

    hashed_count = 0
    hash_errors = []

    for asset in assets:
        file_path = Path(asset.path)

        if not file_path.exists() or not file_path.is_file():
            asset.is_missing = True
            continue

        try:
            asset.sha256 = calculate_sha256(file_path)
            hashed_count += 1

        except (OSError, PermissionError) as exc:
            hash_errors.append(
                {
                    "asset_id": asset.id,
                    "path": asset.path,
                    "error": str(exc),
                }
            )

    db.flush()

    # Rebuild duplicate groups from the current indexed assets.
    db.execute(delete(DuplicateMember))
    db.execute(delete(DuplicateGroup))

    assets_with_hash = db.scalars(
        select(Asset).where(
            Asset.sha256.is_not(None),
            Asset.is_missing.is_(False),
        )
    ).all()

    hash_groups: dict[str, list[Asset]] = {}

    for asset in assets_with_hash:
        if asset.sha256:
            hash_groups.setdefault(
                asset.sha256,
                [],
            ).append(asset)

    duplicate_group_count = 0
    duplicate_asset_count = 0
    potential_savings = 0

    now = datetime.now(timezone.utc)

    for sha256, grouped_assets in hash_groups.items():
        if len(grouped_assets) < 2:
            continue

        file_size = grouped_assets[0].size_bytes
        duplicate_count = len(grouped_assets)

        savings = file_size * (duplicate_count - 1)

        group = DuplicateGroup(
            sha256=sha256,
            file_size_bytes=file_size,
            file_count=duplicate_count,
            potential_savings_bytes=savings,
            created_at=now,
        )

        db.add(group)
        db.flush()

        for asset in grouped_assets:
            db.add(
                DuplicateMember(
                    duplicate_group_id=group.id,
                    asset_id=asset.id,
                )
            )

        duplicate_group_count += 1
        duplicate_asset_count += duplicate_count
        potential_savings += savings

    db.commit()

    return {
        "assets_considered": len(assets),
        "assets_hashed": hashed_count,
        "duplicate_groups": duplicate_group_count,
        "duplicate_assets": duplicate_asset_count,
        "potential_savings_bytes": potential_savings,
        "hash_errors": hash_errors,
    }