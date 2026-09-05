from datetime import datetime, timezone
from pathlib import Path
import mimetypes
import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
    ".heic",
    ".heif",
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".webm",
    ".wmv",
    ".flv",
    ".m4v",
}

AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".flac",
    ".aac",
    ".m4a",
    ".ogg",
    ".wma",
}

DOCUMENT_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".txt",
    ".csv",
    ".rtf",
}

def classify_file_type(extension: str) -> str:
    extension = extension.lower()

    if extension in IMAGE_EXTENSIONS:
        return "image"

    if extension in VIDEO_EXTENSIONS:
        return "video"

    if extension in AUDIO_EXTENSIONS:
        return "audio"

    if extension in DOCUMENT_EXTENSIONS:
        return "document"

    return "other"

def get_file_times(file_path: Path) -> tuple[datetime | None, datetime | None, datetime | None]:
    try:
        stat = file_path.stat()

        created_at = datetime.fromtimestamp(
            stat.st_ctime,
            tz=timezone.utc,
        )

        modified_at = datetime.fromtimestamp(
            stat.st_mtime,
            tz=timezone.utc,
        )

        accessed_at = datetime.fromtimestamp(
            stat.st_atime,
            tz=timezone.utc,
        )

        return created_at, modified_at, accessed_at

    except (OSError, PermissionError):
        return None, None, None

def scan_local_folder(
    db: Session,
    folder_path: str,
) -> dict:
    root = Path(folder_path).expanduser().resolve()

    if not root.exists():
        raise FileNotFoundError(f"Folder does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    source = "local_pc"
    scan_time = datetime.now(timezone.utc)

    discovered_paths: set[str] = set()

    files_scanned = 0
    files_added = 0
    files_updated = 0
    files_skipped = 0
    errors = []

    for current_root, directories, filenames in os.walk(root):
        # Avoid scanning hidden/system metadata directories where possible.
        directories[:] = [
            directory
            for directory in directories
            if directory not in {"$RECYCLE.BIN", "System Volume Information"}
        ]

        for filename in filenames:
            file_path = Path(current_root) / filename

            try:
                if not file_path.is_file():
                    continue

                normalized_path = str(file_path.resolve())
                discovered_paths.add(normalized_path)

                stat = file_path.stat()

                extension = file_path.suffix.lower() or None

                mime_type, _ = mimetypes.guess_type(str(file_path))

                file_type = classify_file_type(
                    extension or ""
                )

                created_at, modified_at, accessed_at = get_file_times(
                    file_path
                )

                existing_asset = db.scalar(
                    select(Asset).where(
                        Asset.source == source,
                        Asset.source_file_id == normalized_path,
                    )
                )

                if existing_asset:
                    existing_asset.name = file_path.name
                    existing_asset.path = normalized_path
                    existing_asset.extension = extension
                    existing_asset.mime_type = mime_type
                    existing_asset.file_type = file_type
                    existing_asset.size_bytes = stat.st_size
                    existing_asset.created_at = created_at
                    existing_asset.modified_at = modified_at
                    existing_asset.accessed_at = accessed_at
                    existing_asset.is_missing = False
                    existing_asset.last_scanned_at = scan_time

                    files_updated += 1

                else:
                    asset = Asset(
                        source=source,
                        source_file_id=normalized_path,
                        name=file_path.name,
                        path=normalized_path,
                        extension=extension,
                        mime_type=mime_type,
                        file_type=file_type,
                        size_bytes=stat.st_size,
                        created_at=created_at,
                        modified_at=modified_at,
                        accessed_at=accessed_at,
                        is_missing=False,
                        last_scanned_at=scan_time,
                    )

                    db.add(asset)

                    files_added += 1

                files_scanned += 1

            except (OSError, PermissionError) as exc:
                files_skipped += 1

                errors.append(
                    {
                        "path": str(file_path),
                        "error": str(exc),
                    }
                )

    # Mark previously indexed files under this scan root as missing
    # if they were not discovered during this scan.
    existing_assets = db.scalars(
        select(Asset).where(
            Asset.source == source,
        )
    ).all()

    assets_under_root = [
        asset
        for asset in existing_assets
        if Path(asset.path).resolve() == root
        or root in Path(asset.path).resolve().parents
    ]

    missing_files_marked = 0

    for asset in assets_under_root:
        if asset.path not in discovered_paths and not asset.is_missing:
            asset.is_missing = True
            asset.last_scanned_at = scan_time
            missing_files_marked += 1

    db.commit()

    return {
        "folder": str(root),
        "files_scanned": files_scanned,
        "files_added": files_added,
        "files_updated": files_updated,
        "files_skipped": files_skipped,
        "missing_files_marked": missing_files_marked,
        "errors": errors,
        "scanned_at": scan_time.isoformat(),
    }