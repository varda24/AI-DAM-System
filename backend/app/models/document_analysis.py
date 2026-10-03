from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentAnalysis(Base):
    __tablename__ = "document_analyses"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    document_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="OTHER",
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )

    extracted_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    extracted_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    issue_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    document_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    expiry_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    issue_date_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    expiry_date_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    expiry_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    issuing_organization: Mapped[str | None] = mapped_column(String(255), nullable=True)

    document_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="UNKNOWN",
    )

    ocr_used: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
    )

    page_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ANALYZED",
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    __table_args__ = (
        Index(
            "ix_document_analyses_document_type",
            "document_type",
        ),
        Index(
            "ix_document_analyses_expiry_date",
            "expiry_date",
        ),
        Index(
            "ix_document_analyses_document_status",
            "document_status",
        ),
    )
