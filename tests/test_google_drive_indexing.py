from datetime import datetime, timezone
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.asset import Asset
from app.models.duplicate import DuplicateGroup, DuplicateMember
from app.services import google_drive_service
from app.services.duplicate_detector import detect_exact_duplicates


ACCOUNT_ONE = {"user": {"permissionId": "account-one", "emailAddress": "one@example.test"}}
DRIVE_FILE_ID = "drive-file-123"
MODIFIED_TIME = "2026-09-30T12:00:00.000Z"


class FakeRequest:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class FakeAbout:
    def __init__(self, account):
        self.account = account

    def get(self, **_kwargs):
        return FakeRequest(self.account)


class FakeFiles:
    def __init__(self, account, image_bytes):
        self.account = account
        self.image_bytes = image_bytes

    def list(self, **_kwargs):
        return FakeRequest(
            {
                "files": [
                    {
                        "id": DRIVE_FILE_ID,
                        "name": "image1-copy.png",
                        "mimeType": "image/png",
                        "size": str(len(self.image_bytes)),
                        "createdTime": MODIFIED_TIME,
                        "modifiedTime": MODIFIED_TIME,
                        "parents": ["drive-folder-id"],
                        "webViewLink": f"https://drive.google.com/open?id={DRIVE_FILE_ID}",
                    }
                ]
            }
        )

    def get(self, fileId, fields):
        assert fileId == DRIVE_FILE_ID
        assert "size" in fields
        return FakeRequest(
            {
                "id": DRIVE_FILE_ID,
                "name": "image1-copy.png",
                "mimeType": "image/png",
                "size": str(len(self.image_bytes)),
                "modifiedTime": MODIFIED_TIME,
            }
        )

    def get_media(self, fileId):
        assert fileId == DRIVE_FILE_ID
        return self.image_bytes


class FakeDriveService:
    def __init__(self, account, image_bytes):
        self.account = account
        self.image_bytes = image_bytes
        self.file_resource = FakeFiles(account, image_bytes)

    def about(self):
        return FakeAbout(self.account)

    def files(self):
        return self.file_resource


class FakeDownloader:
    def __init__(self, file_handle, content):
        self.file_handle = file_handle
        self.content = content
        self.finished = False

    def next_chunk(self):
        if not self.finished:
            self.file_handle.write(self.content)
            self.finished = True
        return None, True


@pytest.fixture

def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[Asset.__table__, DuplicateGroup.__table__, DuplicateMember.__table__],
    )
    with Session(engine) as db:
        yield db
    engine.dispose()


def make_image_bytes() -> bytes:
    image = Image.new("RGB", (32, 32), color=(220, 40, 50))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_drive_sync_hash_and_cross_source_duplicate(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    image_bytes = make_image_bytes()
    service = FakeDriveService(ACCOUNT_ONE, image_bytes)
    monkeypatch.setattr(google_drive_service, "get_drive_service", lambda: service)

    first_sync = google_drive_service.sync_drive_assets(session, max_files=10)
    assert first_sync["files_added"] == 1
    assert first_sync["content_downloaded"] is False

    drive_asset = session.scalar(
        select(Asset).where(Asset.source == "google_drive")
    )
    assert drive_asset is not None
    assert drive_asset.source_file_id == DRIVE_FILE_ID
    assert drive_asset.source_account_id == "account-one"
    assert drive_asset.source_folder_id == "drive-folder-id"
    assert drive_asset.web_view_link == f"https://drive.google.com/open?id={DRIVE_FILE_ID}"

    second_sync = google_drive_service.sync_drive_assets(session, max_files=10)
    assert second_sync["files_added"] == 0
    assert second_sync["files_unchanged"] == 1

    second_account = {"user": {"permissionId": "account-two", "emailAddress": "two@example.test"}}
    monkeypatch.setattr(
        google_drive_service,
        "get_drive_service",
        lambda: FakeDriveService(second_account, image_bytes),
    )
    third_sync = google_drive_service.sync_drive_assets(session, max_files=10)
    assert third_sync["files_added"] == 1
    assert session.scalar(
        select(Asset.id).where(
            Asset.source == "google_drive",
            Asset.source_file_id == DRIVE_FILE_ID,
        ).order_by(Asset.id.desc())
    )
    assert session.scalar(
        select(Asset.id).where(
            Asset.source == "google_drive",
            Asset.source_account_id == "account-two",
            Asset.source_file_id == DRIVE_FILE_ID,
        )
    ) is not None

    local_path = tmp_path / "image1.png"
    local_path.write_bytes(image_bytes)
    local_asset = Asset(
        source="local_pc",
        source_file_id=str(local_path),
        name=local_path.name,
        path=str(local_path),
        extension=".png",
        mime_type="image/png",
        file_type="image",
        size_bytes=len(image_bytes),
        created_at=datetime.now(timezone.utc),
        modified_at=datetime.now(timezone.utc),
        is_missing=False,
        last_scanned_at=datetime.now(timezone.utc),
    )
    session.add(local_asset)
    session.commit()

    monkeypatch.setattr(
        google_drive_service,
        "get_drive_service",
        lambda: service,
    )
    monkeypatch.setattr(
        google_drive_service,
        "MediaIoBaseDownload",
        lambda file_handle, request, chunksize: FakeDownloader(file_handle, request),
    )
    result = google_drive_service.hash_drive_asset(session, drive_asset.id)
    assert result["cached"] is False
    assert result["sha256"] == google_drive_service.hashlib.sha256(image_bytes).hexdigest()
    assert result["perceptual_hash"]

    duplicate_result = detect_exact_duplicates(session)
    assert duplicate_result["duplicate_groups"] == 1
    group = session.scalar(select(DuplicateGroup))
    assert group is not None
    members = session.scalars(
        select(Asset)
        .join(DuplicateMember, DuplicateMember.asset_id == Asset.id)
        .where(DuplicateMember.duplicate_group_id == group.id)
    ).all()
    assert {asset.source for asset in members} == {"local_pc", "google_drive"}
    assert all(asset.sha256 == result["sha256"] for asset in members)
