from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.image_analysis import search_analyzed_images
from app.core.database import Base
from app.models.analysis_job import AnalysisJob
from app.models.asset import Asset
from app.models.image_analysis import ImageAnalysis


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[Asset.__table__, ImageAnalysis.__table__, AnalysisJob.__table__],
    )
    with Session(engine) as db:
        yield db
    engine.dispose()


def test_blank_image_search_lists_saved_analyses_and_query_filters(session: Session):
    now = datetime.now(timezone.utc)
    asset = Asset(
        source="local_pc",
        source_file_id="/images/bordered.jpg",
        name="bordered.jpg",
        path="/images/bordered.jpg",
        extension=".jpg",
        mime_type="image/jpeg",
        file_type="image",
        size_bytes=100,
        is_missing=False,
        last_scanned_at=now,
    )
    session.add(asset)
    session.flush()
    session.add(
        ImageAnalysis(
            asset_id=asset.id,
            caption="a black background with a white border",
            category="other",
            tags="",
            model_name="test-model",
            analyzed_at=now,
        )
    )
    session.commit()

    all_results = search_analyzed_images(q=None, db=session)
    matching_results = search_analyzed_images(q="black", db=session)
    no_match_results = search_analyzed_images(q="landscape", db=session)

    assert all_results["total"] == 1
    assert all_results["items"][0]["asset_id"] == asset.id
    assert all_results["items"][0]["caption"] == "a black background with a white border"
    assert all_results["items"][0]["category"] == "other"
    assert matching_results["total"] == 1
    assert no_match_results["total"] == 0


def test_blank_image_search_includes_queued_images_with_status(session: Session):
    now = datetime.now(timezone.utc)
    asset = Asset(
        source="local_pc",
        source_file_id="/images/pending.jpg",
        name="pending.jpg",
        path="/images/pending.jpg",
        extension=".jpg",
        mime_type="image/jpeg",
        file_type="image",
        size_bytes=100,
        is_missing=False,
        last_scanned_at=now,
    )
    session.add(asset)
    session.flush()
    session.add(AnalysisJob(
        asset_id=asset.id,
        job_type="IMAGE_ANALYSIS",
        status="PENDING",
        asset_signature="100:2026-10-03:",
        created_at=now,
    ))
    session.commit()

    result = search_analyzed_images(q=None, db=session)

    assert result["total"] == 1
    assert result["items"][0]["asset_id"] == asset.id
    assert result["items"][0]["analysis_status"] == "PENDING"
    assert result["items"][0]["caption"] is None