from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.similarity_detector import analyze_image_hashes, find_similar_images

router = APIRouter(
    prefix="/api/similarity",
    tags=["Image Similarity"],
)


@router.post("/analyze")
def analyze_images(db: Session = Depends(get_db)):
    return analyze_image_hashes(db)


@router.get("/images")
def similar_images(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return find_similar_images(db, page=page, page_size=page_size)
