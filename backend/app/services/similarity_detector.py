from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.services.image_similarity import calculate_perceptual_hash, hamming_distance

SIMILARITY_THRESHOLD = 8


def analyze_image_hashes(db: Session) -> dict:
    assets = db.scalars(
        select(Asset).where(
            Asset.source == "local_pc",
            Asset.file_type == "image",
            Asset.is_missing.is_(False),
        )
    ).all()

    analyzed = 0
    errors = []

    for asset in assets:
        path = Path(asset.path)

        if not path.exists() or not path.is_file():
            asset.is_missing = True
            continue

        try:
            asset.perceptual_hash = calculate_perceptual_hash(path)
            analyzed += 1
        except Exception as exc:
            errors.append({"asset_id": asset.id, "path": asset.path, "error": str(exc)})

    db.commit()

    return {
        "images_considered": len(assets),
        "images_analyzed": analyzed,
        "errors": errors,
    }


def find_similar_images(db: Session) -> dict:
    assets = db.scalars(
        select(Asset).where(
            Asset.file_type == "image",
            Asset.perceptual_hash.is_not(None),
            Asset.is_missing.is_(False),
        )
    ).all()

    groups = []
    assigned: set[int] = set()

    for asset in assets:
        if asset.id in assigned or not asset.perceptual_hash:
            continue

        current_group = [asset]

        for candidate in assets:
            if candidate.id == asset.id or candidate.id in assigned or not candidate.perceptual_hash:
                continue

            if hamming_distance(asset.perceptual_hash, candidate.perceptual_hash) <= SIMILARITY_THRESHOLD:
                current_group.append(candidate)

        if len(current_group) >= 2:
            for member in current_group:
                assigned.add(member.id)
            groups.append(current_group)

    result = []
    for index, group_assets in enumerate(groups, start=1):
        result.append({
            "id": index,
            "asset_count": len(group_assets),
            "assets": [
                {
                    "id": asset.id,
                    "name": asset.name,
                    "path": asset.path,
                    "size_bytes": asset.size_bytes,
                    "mime_type": asset.mime_type,
                    "modified_at": asset.modified_at.isoformat() if asset.modified_at else None,
                    "perceptual_hash": asset.perceptual_hash,
                }
                for asset in group_assets
            ],
        })

    return {
        "total_groups": len(result),
        "total_similar_images": sum(group["asset_count"] for group in result),
        "groups": result,
    }