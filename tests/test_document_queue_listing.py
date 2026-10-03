from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.documents import list_document_analyses
from app.core.database import Base
from app.models.analysis_job import AnalysisJob
from app.models.asset import Asset
from app.models.document_analysis import DocumentAnalysis


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[Asset.__table__, DocumentAnalysis.__table__, AnalysisJob.__table__],
    )
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_document_list_includes_indexed_assets_with_queue_status(session: Session):
    now = datetime.now(timezone.utc)
    asset = Asset(
        source="local_pc",
        source_file_id="/docs/income-certificate.pdf",
        name="income-certificate.pdf",
        path="/docs/income-certificate.pdf",
        extension=".pdf",
        mime_type="application/pdf",
        file_type="document",
        size_bytes=120,
        is_missing=False,
        last_scanned_at=now,
    )
    session.add(asset)
    session.flush()
    session.add(AnalysisJob(
        asset_id=asset.id,
        job_type="DOCUMENT_ANALYSIS",
        status="PROCESSING",
        asset_signature="120:2026-10-03:",
        created_at=now,
        started_at=now,
    ))
    session.commit()

    result = list_document_analyses(limit=100, offset=0, status=None, db=session)

    assert result["total"] == 1
    document = result["documents"][0]
    assert document["asset_id"] == asset.id
    assert document["name"] == asset.name
    assert document["analysis_status"] == "PROCESSING"
    assert document["document_status"] == "UNKNOWN"
    assert document["extracted_text"] is None