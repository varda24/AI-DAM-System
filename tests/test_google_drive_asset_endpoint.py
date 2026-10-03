from datetime import datetime, timezone
from pathlib import PureWindowsPath

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.api import google_drive
from app.models.asset import Asset


@pytest.fixture

def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Asset.__table__])
    with Session(engine) as db:
        yield db
    engine.dispose()


def make_asset(source, file_id, path, account_id=None):
    now = datetime.now(timezone.utc)
    return Asset(
        source=source,
        source_account_id=account_id,
        source_file_id=file_id,
        name="example.txt",
        path=path,
        extension=".txt",
        mime_type="text/plain",
        file_type="document",
        size_bytes=4,
        created_at=now,
        modified_at=now,
        is_missing=False,
        last_scanned_at=now,
    )


def test_drive_asset_endpoint_never_returns_local_rows_or_windows_paths(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
):
    session.add_all([
        make_asset("local_pc", "D:\\Photos\\example.txt", "D:\\Photos\\example.txt"),
        make_asset("google_drive", "drive-id-1", "Google Drive/example.txt", "account-1"),
        make_asset("google_drive", "drive-id-bad", "D:\\Photos\\leaked.txt", "account-1"),
        make_asset("google_drive", "drive-id-other", "Google Drive/other.txt", "account-2"),
    ])
    session.commit()
    monkeypatch.setattr(
        google_drive,
        "get_drive_about",
        lambda: {"user": {"permissionId": "account-1"}},
    )

    response = google_drive.google_drive_assets(
        page=1,
        page_size=50,
        parent_id=None,
        db=session,
    )

    assert response["total"] == 1
    assert [asset["source"] for asset in response["items"]] == ["google_drive"]
    assert [asset["drive_file_id"] for asset in response["items"]] == ["drive-id-1"]
    assert all(not PureWindowsPath(asset["path"]).is_absolute() for asset in response["items"])
