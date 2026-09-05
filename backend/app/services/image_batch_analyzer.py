from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.image_analysis import ImageAnalysis
from app.services.image_analyzer import get_image_analyzer


def analyze_all_images(db: Session) -> dict:
    analyzer = get_image_analyzer()

    assets = db.scalars(
        select(Asset).where(
            Asset.source == "local_pc",
            Asset.file_type == "image",
            Asset.is_missing.is_(False),
        )
    ).all()

    analyzed = 0
    skipped = 0
    failed = 0
    errors = []

    for asset in assets:
        path = Path(asset.path)

        if not path.exists() or not path.is_file():
            asset.is_missing = True
            skipped += 1
            continue

        try:
            result = analyzer.analyze(path)

            analysis = db.scalar(
                select(ImageAnalysis).where(
                    ImageAnalysis.asset_id == asset.id
                )
            )

            if analysis is None:
                analysis = ImageAnalysis(asset_id=asset.id)
                db.add(analysis)

            analysis.caption = result["caption"]
            analysis.category = result["category"]
            analysis.tags = result["tags"]
            analysis.model_name = result["model_name"]
            analysis.processing_time_ms = result["processing_time_ms"]
            analysis.analyzed_at = datetime.now(timezone.utc)

            analyzed += 1

            if analyzed % 10 == 0:
                db.commit()

        except Exception as exc:
            failed += 1
            errors.append(
                {
                    "asset_id": asset.id,
                    "name": asset.name,
                    "error": str(exc),
                }
            )

    db.commit()

    return {
        "images_found": len(assets),
        "images_analyzed": analyzed,
        "images_skipped": skipped,
        "images_failed": failed,
        "errors": errors[:50],
    }