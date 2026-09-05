from pathlib import Path

import numpy as np
from insightface.app import FaceAnalysis


class FaceEngine:
    def __init__(self):
        self.app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        self.app.prepare(ctx_id=0, det_size=(640, 640))

    def detect_faces(self, file_path: str | Path) -> list[dict]:
        import cv2

        image = cv2.imread(str(file_path))
        if image is None:
            raise ValueError("Unable to read image.")

        results = []
        for face in self.app.get(image):
            embedding = np.asarray(face.embedding, dtype=np.float32)
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            results.append({
                "embedding": embedding,
                "confidence": float(face.det_score),
                "bbox": face.bbox.tolist() if face.bbox is not None else None,
            })
        return results


_engine: FaceEngine | None = None


def get_face_engine() -> FaceEngine:
    global _engine
    if _engine is None:
        _engine = FaceEngine()
    return _engine