from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.video_analysis import VideoAnalysis
from app.services.video_analyzer import analyze_video
from app.services.video_similarity import detect_similar_videos


router = APIRouter(
    prefix="/api/videos",
    tags=["Videos"],
)


def _serialize_video_analysis(
    result: VideoAnalysis,
) -> dict:
    return {
        "id": result.id,
        "asset_id": result.asset_id,
        "duration_seconds": result.duration_seconds,
        "width": result.width,
        "height": result.height,
        "fps": result.fps,
        "frame_count": result.frame_count,
        "video_codec": result.video_codec,
        "thumbnail_path": result.thumbnail_path,
        "status": result.status,
        "error_message": result.error_message,
        "analyzed_at": (
            result.analyzed_at.isoformat()
            if result.analyzed_at
            else None
        ),
    }


@router.post("/{asset_id}/analyze")
def analyze_video_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    try:
        result = analyze_video(
            db=db,
            asset_id=asset_id,
        )

        return _serialize_video_analysis(result)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Video analysis failed: {exc}",
        )


@router.get("/{asset_id}")
def get_video_analysis(
    asset_id: int,
    db: Session = Depends(get_db),
):
    result = db.scalar(
        select(VideoAnalysis).where(
            VideoAnalysis.asset_id == asset_id
        )
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Video analysis has not been created for this asset.",
        )

    return _serialize_video_analysis(result)


@router.post("/{asset_id}/reanalyze")
def reanalyze_video_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    try:
        result = analyze_video(
            db=db,
            asset_id=asset_id,
        )

        return _serialize_video_analysis(result)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Video re-analysis failed: {exc}",
        )


@router.get("/{asset_id}/thumbnail")
def get_video_thumbnail(
    asset_id: int,
    db: Session = Depends(get_db),
):
    result = db.scalar(
        select(VideoAnalysis).where(
            VideoAnalysis.asset_id == asset_id
        )
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Video analysis has not been created yet.",
        )

    if not result.thumbnail_path:
        raise HTTPException(
            status_code=404,
            detail="Thumbnail is not available for this video.",
        )

    thumbnail_path = Path(
        result.thumbnail_path
    )

    if not thumbnail_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Video thumbnail file is missing.",
        )

    if not thumbnail_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Video thumbnail path is invalid.",
        )

    return FileResponse(
        path=str(thumbnail_path),
        media_type="image/jpeg",
        filename=thumbnail_path.name,
    )


@router.post("/similarity/detect")
def detect_video_similarity(
    asset_ids: str | None = Query(
        default=None,
        description=(
            "Comma-separated video asset IDs. "
            "If omitted, all indexed local videos are checked."
        ),
    ),
    threshold: float = Query(
        default=0.80,
        ge=0.50,
        le=0.99,
    ),
    sample_count: int = Query(
        default=8,
        ge=3,
        le=20,
    ),
    db: Session = Depends(get_db),
):
    parsed_ids: list[int] | None = None

    if asset_ids:
        try:
            parsed_ids = [
                int(value.strip())
                for value in asset_ids.split(",")
                if value.strip()
            ]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="asset_ids must contain comma-separated integers.",
            )

        if not parsed_ids:
            raise HTTPException(
                status_code=400,
                detail="No valid asset IDs were provided.",
            )

    try:
        return detect_similar_videos(
            db=db,
            asset_ids=parsed_ids,
            threshold=threshold,
            sample_count=sample_count,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Video similarity detection failed: {exc}",
        )