from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.person import FaceEmbedding, PersonCluster
from app.services.face_analyzer import analyze_all_faces
from app.services.person_clustering import cluster_faces

router = APIRouter(
    prefix="/api/people",
    tags=["People"],
)


@router.post("/analyze")
def analyze_faces(db: Session = Depends(get_db)):
    return analyze_all_faces(db)


@router.post("/cluster")
def create_clusters(db: Session = Depends(get_db)):
    return cluster_faces(db)


@router.get("/clusters")
def get_clusters(db: Session = Depends(get_db)):
    clusters = db.scalars(select(PersonCluster).order_by(PersonCluster.id.asc())).all()
    result = []

    for cluster in clusters:
        faces = db.scalars(select(FaceEmbedding).where(FaceEmbedding.cluster_id == cluster.id)).all()
        result.append({
            "id": cluster.id,
            "label": cluster.label,
            "face_count": cluster.face_count,
            "confidence": cluster.confidence,
            "asset_ids": list(dict.fromkeys(face.asset_id for face in faces)),
            "created_at": cluster.created_at.isoformat(),
        })

    return {"total_clusters": len(result), "clusters": result}