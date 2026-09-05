from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Asset
from app.models.image_analysis import ImageAnalysis
from app.services.image_batch_analyzer import analyze_all_images
from app.services.image_analyzer import get_image_analyzer

router = APIRouter(
    prefix="/api/ai/images",
    tags=["AI Image Analysis"],
)


@router.post("/analyze/{asset_id}")
def analyze_image(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if asset.source != "local_pc":
        raise HTTPException(
            status_code=400,
            detail="AI image analysis is currently available only for local PC assets.",
        )
    if asset.file_type != "image":
        raise HTTPException(status_code=400, detail="AI image analysis is only available for image assets.")
    if asset.is_missing:
        raise HTTPException(status_code=404, detail="The indexed image is missing.")

    path = Path(asset.path)
    if not path.exists() or not path.is_file():
        asset.is_missing = True
        db.commit()
        raise HTTPException(status_code=404, detail="The image no longer exists on the filesystem.")

    try:
        result = get_image_analyzer().analyze(path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {exc}") from exc

    analysis = db.scalar(select(ImageAnalysis).where(ImageAnalysis.asset_id == asset.id))
    if analysis is None:
        analysis = ImageAnalysis(asset_id=asset.id, analyzed_at=datetime.now(timezone.utc))
        db.add(analysis)

    analysis.caption = result["caption"]
    analysis.category = result["category"]
    analysis.tags = result["tags"]
    analysis.model_name = result["model_name"]
    analysis.processing_time_ms = result["processing_time_ms"]
    analysis.analyzed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(analysis)

    return {
        "asset_id": asset.id,
        "name": asset.name,
        "caption": analysis.caption,
        "category": analysis.category,
        "tags": analysis.tags.split(",") if analysis.tags else [],
        "model_name": analysis.model_name,
        "processing_time_ms": analysis.processing_time_ms,
        "analyzed_at": analysis.analyzed_at.isoformat(),
    }


@router.post("/analyze-all")
def analyze_all(db: Session = Depends(get_db)):
    return analyze_all_images(db)


@router.get("/search")
def search_analyzed_images(
    q: str,
    db: Session = Depends(get_db),
):
    pattern = f"%{q}%"

    rows = db.execute(
        select(ImageAnalysis, Asset)
        .join(
            Asset,
            Asset.id == ImageAnalysis.asset_id,
        )
        .where(
            Asset.is_missing.is_(False),
            (
                ImageAnalysis.caption.ilike(pattern)
                | ImageAnalysis.category.ilike(pattern)
                | ImageAnalysis.tags.ilike(pattern)
            ),
        )
        .order_by(ImageAnalysis.analyzed_at.desc())
        .limit(100)
    ).all()

    return {
        "query": q,
        "total": len(rows),
        "items": [
            {
                "asset_id": asset.id,
                "name": asset.name,
                "path": asset.path,
                "size_bytes": asset.size_bytes,
                "mime_type": asset.mime_type,
                "caption": analysis.caption,
                "category": analysis.category,
                "tags": analysis.tags.split(",") if analysis.tags else [],
                "analyzed_at": (
                    analysis.analyzed_at.isoformat()
                    if analysis.analyzed_at
                    else None
                ),
            }
            for analysis, asset in rows
        ],
    }


@router.get("/{asset_id}")
def get_image_analysis(asset_id: int, db: Session = Depends(get_db)):
    analysis = db.scalar(select(ImageAnalysis).where(ImageAnalysis.asset_id == asset_id))
    if analysis is None:
        raise HTTPException(status_code=404, detail="This image has not been analyzed yet.")
    return {
        "asset_id": analysis.asset_id,
        "caption": analysis.caption,
        "category": analysis.category,
        "tags": analysis.tags.split(",") if analysis.tags else [],
        "model_name": analysis.model_name,
        "processing_time_ms": analysis.processing_time_ms,
        "analyzed_at": analysis.analyzed_at.isoformat(),
    }
