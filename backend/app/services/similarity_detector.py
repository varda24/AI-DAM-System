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


def _candidate_pairs(assets: list[Asset]):
    """Yield likely pHash pairs before confirming their Hamming distance.

    Nine bit-chunks are used because two hashes at distance <= 8 must share at
    least one unchanged chunk. This preserves the threshold while avoiding a
    full comparison for unrelated images.
    """
    chunk_count = 9
    chunk_widths = [
        (64 // chunk_count) + (1 if index < 64 % chunk_count else 0)
        for index in range(chunk_count)
    ]
    buckets: dict[tuple[int, int], list[Asset]] = {}

    for asset in assets:
        if not asset.perceptual_hash:
            continue
        value = int(asset.perceptual_hash, 16)
        offset = 0
        for chunk_index, width in enumerate(chunk_widths):
            key = (chunk_index, (value >> offset) & ((1 << width) - 1))
            buckets.setdefault(key, []).append(asset)
            offset += width

    yielded: set[tuple[int, int]] = set()
    for bucket in buckets.values():
        for index, asset in enumerate(bucket):
            for candidate in bucket[index + 1:]:
                pair = tuple(sorted((asset.id, candidate.id)))
                if pair not in yielded:
                    yielded.add(pair)
                    yield asset, candidate


def find_similar_images(
    db: Session,
    page: int = 1,
    page_size: int = 25,
) -> dict:
    assets = db.scalars(
        select(Asset).where(
            Asset.file_type == "image",
            Asset.perceptual_hash.is_not(None),
            Asset.is_missing.is_(False),
        )
    ).all()

    parent = {asset.id: asset.id for asset in assets}

    def find(asset_id: int) -> int:
        while parent[asset_id] != asset_id:
            parent[asset_id] = parent[parent[asset_id]]
            asset_id = parent[asset_id]
        return asset_id

    def union(first_id: int, second_id: int) -> None:
        first_root = find(first_id)
        second_root = find(second_id)
        if first_root != second_root:
            parent[second_root] = first_root

    for asset, candidate in _candidate_pairs(assets):
        if (
            asset.perceptual_hash
            and candidate.perceptual_hash
            and hamming_distance(asset.perceptual_hash, candidate.perceptual_hash)
            <= SIMILARITY_THRESHOLD
        ):
            union(asset.id, candidate.id)

    grouped_assets: dict[int, list[Asset]] = {}
    for asset in assets:
        grouped_assets.setdefault(find(asset.id), []).append(asset)

    groups = [
        sorted(group, key=lambda item: item.id)
        for group in grouped_assets.values()
        if len(group) >= 2
    ]
    groups.sort(key=lambda group: (-len(group), group[0].id))

    total_similar_images = sum(len(group) for group in groups)
    total_groups = len(groups)
    start = (page - 1) * page_size
    page_groups = groups[start:start + page_size]

    result = []
    for index, group_assets in enumerate(page_groups, start=start + 1):
        result.append({
            "id": index,
            "asset_count": len(group_assets),
            "assets": [
                {
                    "id": asset.id,
                    "source": asset.source,
                    "source_account_id": asset.source_account_id,
                    "source_folder_id": asset.source_folder_id,
                    "drive_file_id": (
                        asset.source_file_id
                        if asset.source == "google_drive"
                        else None
                    ),
                    "web_view_link": asset.web_view_link,
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
        "page": page,
        "page_size": page_size,
        "total_groups": total_groups,
        "total_pages": (total_groups + page_size - 1) // page_size if total_groups else 0,
        "total_similar_images": total_similar_images,
        "groups": result,
    }
