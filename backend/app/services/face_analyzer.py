from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.person import FaceEmbedding
from app.services.face_engine import get_face_engine


def embedding_to_bytes(embedding: np.ndarray) -> bytes:
    return embedding.astype(np.float32).tobytes()


def bytes_to_embedding(value: bytes) -> np.ndarray:
    return np.frombuffer(value, dtype=np.float32)


def analyze_asset_faces(db: Session, asset: Asset) -> dict:
    path = Path(asset.path)
    if not path.exists():
        asset.is_missing = True
        db.commit()
        return {"asset_id": asset.id, "faces_detected": 0, "status": "missing"}

    faces = get_face_engine().detect_faces(path)
    db.execute(delete(FaceEmbedding).where(FaceEmbedding.asset_id == asset.id))

    for index, face in enumerate(faces):
        db.add(FaceEmbedding(
            asset_id=asset.id,
            cluster_id=None,
            embedding=embedding_to_bytes(face["embedding"]),
            face_index=index,
            detection_confidence=face["confidence"],
            created_at=datetime.now(timezone.utc),
        ))

    db.commit()
    return {"asset_id": asset.id, "faces_detected": len(faces), "status": "analyzed"}


def analyze_all_faces(db: Session) -> dict:
    assets = db.scalars(select(Asset).where(
        Asset.source == "local_pc",
        Asset.file_type == "image",
        Asset.is_missing.is_(False),
    )).all()

    analyzed = 0
    total_faces = 0
    failed = 0
    errors = []

    for asset in assets:
        try:
            result = analyze_asset_faces(db, asset)
            if result["status"] == "analyzed":
                analyzed += 1
                total_faces += result["faces_detected"]
        except Exception as exc:
            failed += 1
            errors.append({"asset_id": asset.id, "name": asset.name, "error": str(exc)})

    return {
        "images_found": len(assets),
        "images_analyzed": analyzed,
        "faces_detected": total_faces,
        "images_failed": failed,
        "errors": errors[:50],
    }