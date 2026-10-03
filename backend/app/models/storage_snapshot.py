from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StorageSnapshot(Base):
    __tablename__ = "storage_snapshots"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="local_pc",
        index=True,
    )

    total_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    total_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    duplicate_savings_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    image_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    image_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    video_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    video_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    document_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    document_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    other_files: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    other_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    __table_args__ = (
        Index(
            "ix_storage_snapshots_source_captured_at",
            "source",
            "captured_at",
        ),
    )
