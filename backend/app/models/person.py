from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, LargeBinary, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PersonCluster(Base):
    __tablename__ = "person_clusters"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    face_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cluster_id: Mapped[int | None] = mapped_column(
        ForeignKey("person_clusters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    face_index: Mapped[int] = mapped_column(Integer, nullable=False)
    detection_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)