from fastapi import APIRouter, Depends
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
def similar_images(db: Session = Depends(get_db)):
    return find_similar_images(db)