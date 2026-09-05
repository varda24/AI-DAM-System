from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.person import FaceEmbedding, PersonCluster

CLUSTER_THRESHOLD = 0.48


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator == 0:
        return 0.0
    return float(np.dot(a, b) / denominator)


def cluster_faces(db: Session) -> dict:
    faces = db.scalars(select(FaceEmbedding).order_by(FaceEmbedding.id)).all()
    if not faces:
        return {"faces_considered": 0, "clusters_created": 0}

    for face in faces:
        face.cluster_id = None

    for cluster in db.scalars(select(PersonCluster)).all():
        db.delete(cluster)
    db.flush()

    clusters = []
    for face in faces:
        embedding = np.frombuffer(face.embedding, dtype=np.float32)
        best_cluster = None
        best_similarity = 0.0

        for cluster, centroid, count in clusters:
            similarity = cosine_similarity(embedding, centroid)
            if similarity >= CLUSTER_THRESHOLD and similarity > best_similarity:
                best_cluster = (cluster, centroid, count)
                best_similarity = similarity

        if best_cluster is None:
            cluster = PersonCluster(
                label=None,
                face_count=1,
                confidence=round(max(0.0, best_similarity), 3),
                created_at=datetime.now(timezone.utc),
            )
            db.add(cluster)
            db.flush()
            clusters.append((cluster, embedding.copy(), 1))
            face.cluster_id = cluster.id
            continue

        cluster, centroid, count = best_cluster
        face.cluster_id = cluster.id
        new_centroid = (centroid * count + embedding) / (count + 1)
        norm = np.linalg.norm(new_centroid)
        if norm > 0:
            new_centroid /= norm

        for index, item in enumerate(clusters):
            if item[0].id == cluster.id:
                clusters[index] = (cluster, new_centroid, count + 1)
                break

        cluster.face_count = count + 1
        cluster.confidence = round(max(cluster.confidence or 0, best_similarity), 3)

    db.commit()
    return {
        "faces_considered": len(faces),
        "clusters_created": len(clusters),
        "cluster_threshold": CLUSTER_THRESHOLD,
    }