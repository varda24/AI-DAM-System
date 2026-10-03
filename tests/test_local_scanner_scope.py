from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.asset import Asset
from app.services import local_scanner
from app.services.local_scanner import scan_local_folder


@pytest.fixture

def session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Asset.__table__])
    with Session(engine) as db:
        yield db
    engine.dispose()


def indexed_asset(path, name):
    now = datetime.now(timezone.utc)
    return Asset(
        source="local_pc",
        source_file_id=str(path),
        name=name,
        path=str(path),
        extension=".txt",
        mime_type="text/plain",
        file_type="document",
        size_bytes=path.stat().st_size,
        created_at=now,
        modified_at=now,
        accessed_at=now,
        is_missing=False,
        last_scanned_at=now,
    )


def test_scan_includes_selected_root_and_preserves_excluded_assets(session, tmp_path):
    photos = tmp_path / "Photos"
    allowed = photos / "2025"
    excluded = photos / "Private"
    outside = tmp_path / "Outside"
    allowed.mkdir(parents=True)
    excluded.mkdir()
    outside.mkdir()
    (allowed / "keep.txt").write_text("keep", encoding="utf-8")
    private_file = excluded / "private.txt"
    private_file.write_text("private", encoding="utf-8")
    outside_file = outside / "outside.txt"
    outside_file.write_text("outside", encoding="utf-8")

    private_asset = indexed_asset(private_file, private_file.name)
    outside_asset = indexed_asset(outside_file, outside_file.name)
    session.add_all([private_asset, outside_asset])
    session.commit()

    result = scan_local_folder(
        session,
        [str(photos)],
        excluded_paths=[str(excluded)],
    )

    assert result["files_scanned"] == 1
    assert result["files_added"] == 1
    assert result["excluded_paths"] == [str(excluded.resolve())]
    assert private_asset.is_missing is False
    assert outside_asset.is_missing is False
    assert session.scalar(
        select(Asset).where(Asset.path == str(allowed / "keep.txt"))
    ) is not None
    assert session.scalar(
        select(Asset).where(Asset.path == str(private_file))
    ) is private_asset


def test_scan_rejects_exclusion_outside_included_roots(session, tmp_path):
    included = tmp_path / "Included"
    excluded = tmp_path / "Excluded"
    included.mkdir()
    excluded.mkdir()

    with pytest.raises(ValueError, match="inside an included folder"):
        scan_local_folder(session, [str(included)], [str(excluded)])


def test_folder_search_finds_matching_directories_without_reading_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    match = tmp_path / "Projects" / "Archive"
    (match / "child").mkdir(parents=True)
    (tmp_path / "Pictures").mkdir()
    (tmp_path / "Projects" / "notes.txt").write_text("not scanned", encoding="utf-8")
    monkeypatch.setattr(
        local_scanner,
        "list_local_roots",
        lambda: [{"path": str(tmp_path), "name": str(tmp_path)}],
    )

    result = local_scanner.search_local_directories("project")

    assert result["folders"] == [{"path": str((tmp_path / "Projects").resolve()), "name": "Projects"}]
    assert result["truncated"] is False
