from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Source identification
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_account_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_file_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_folder_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    web_view_link: Mapped[str | None] = mapped_column(Text, nullable=True)

    # File information
    name: Mapped[str] = mapped_column(Text, nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    extension: Mapped[str | None] = mapped_column(String(20), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Filesystem timestamps
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Indexing state
    is_missing: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Exact duplicate detection
    sha256: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    # Visual similarity detection
    perceptual_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "source <> 'google_drive' OR source_account_id IS NOT NULL",
            name="ck_drive_assets_require_account",
        ),
        Index(
            "uq_assets_non_drive_source_file",
            "source",
            "source_file_id",
            unique=True,
            postgresql_where=text("source <> 'google_drive'"),
            sqlite_where=text("source <> 'google_drive'"),
        ),
        Index(
            "uq_assets_drive_account_file",
            "source",
            "source_account_id",
            "source_file_id",
            unique=True,
            postgresql_where=text("source = 'google_drive'"),
            sqlite_where=text("source = 'google_drive'"),
        ),
        Index(
            "ix_assets_source_path",
            "source",
            "path",
        ),
    )