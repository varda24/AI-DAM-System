from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Asset
from app.models.person import FaceEmbedding, PersonCluster
from app.services.face_analyzer import analyze_all_faces, analyze_asset_faces
from app.services.person_clustering import cluster_faces

router = APIRouter(
    prefix="/api/people",
    tags=["People"],
)


class ClusterLabelUpdate(BaseModel):
    label: str | None = Field(None, max_length=200)


@router.post("/analyze")
def analyze_faces(db: Session = Depends(get_db)):
    return analyze_all_faces(db)


@router.post("/analyze/{asset_id}")
def analyze_single_asset_faces(
    asset_id: int,
    db: Session = Depends(get_db),
):
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if asset.source != "local_pc":
        raise HTTPException(
            status_code=400,
            detail="Face analysis is currently available only for local PC assets.",
        )
    if asset.file_type != "image":
        raise HTTPException(
            status_code=400,
            detail="Face analysis is only available for image assets.",
        )
    if asset.is_missing:
        raise HTTPException(status_code=404, detail="The indexed image is missing.")

    try:
        return analyze_asset_faces(db, asset)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Face analysis failed: {exc}") from exc


@router.post("/cluster")
def create_clusters(db: Session = Depends(get_db)):
    return cluster_faces(db)


@router.get("/clusters")
def get_clusters(db: Session = Depends(get_db)):
    clusters = db.scalars(select(PersonCluster).order_by(PersonCluster.id.asc())).all()
    result = []

    for cluster in clusters:
        faces = db.scalars(select(FaceEmbedding).where(FaceEmbedding.cluster_id == cluster.id)).all()
        asset_ids = list(dict.fromkeys(face.asset_id for face in faces))

        assets = []
        if asset_ids:
            asset_rows = db.scalars(select(Asset).where(Asset.id.in_(asset_ids))).all()
            assets = [
                {
                    "id": asset.id,
                    "name": asset.name,
                    "path": asset.path,
                    "mime_type": asset.mime_type,
                    "file_type": asset.file_type,
                    "size_bytes": asset.size_bytes,
                }
                for asset in asset_rows
            ]

        result.append({
            "id": cluster.id,
            "label": cluster.label,
            "face_count": cluster.face_count,
            "confidence": cluster.confidence,
            "asset_ids": asset_ids,
            "assets": assets,
            "created_at": cluster.created_at.isoformat() if cluster.created_at else None,
        })

    return {"total_clusters": len(result), "clusters": result}


@router.patch("/clusters/{cluster_id}")
def update_cluster_label(
    cluster_id: int,
    payload: ClusterLabelUpdate,
    db: Session = Depends(get_db),
):
    cluster = db.get(PersonCluster, cluster_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Person cluster not found.")

    cluster.label = payload.label.strip() if payload.label else None
    db.commit()
    db.refresh(cluster)

    return {
        "id": cluster.id,
        "label": cluster.label,
        "face_count": cluster.face_count,
        "confidence": cluster.confidence,
    }
