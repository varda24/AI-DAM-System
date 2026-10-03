from datetime import datetime, timezone
from pathlib import Path
import mimetypes
import os
import ctypes

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.asset import Asset

SYSTEM_DIRECTORIES = {"$RECYCLE.BIN", "SYSTEM VOLUME INFORMATION"}


def _canonical_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _is_within(path: str | Path, parent: str | Path) -> bool:
    normalized_path = os.path.normcase(str(_canonical_path(path)))
    normalized_parent = os.path.normcase(str(_canonical_path(parent)))
    try:
        return os.path.commonpath((normalized_path, normalized_parent)) == normalized_parent
    except ValueError:
        return False


def _directory_query(roots: list[Path]):
    conditions = []
    for root in roots:
        root_path = str(root)
        prefix = root_path.rstrip("\\/") + os.sep
        conditions.extend((
            Asset.path == root_path,
            Asset.path.startswith(prefix, autoescape=True),
        ))
    return or_(*conditions)


def list_local_roots() -> list[dict[str, str]]:
    if os.name == "nt":
        drive_mask = ctypes.windll.kernel32.GetLogicalDrives()
        roots = [
            f"{chr(ord('A') + index)}:\\"
            for index in range(26)
            if drive_mask & (1 << index)
        ]
    else:
        roots = [os.path.abspath(os.sep)]
    return [
        {"path": root, "name": root}
        for root in roots
        if Path(root).exists() and Path(root).is_dir()
    ]


def list_local_subdirectories(parent_path: str) -> list[dict[str, str]]:
    parent = _canonical_path(parent_path)
    if not parent.exists() or not parent.is_dir():
        raise NotADirectoryError(f"Path is not an accessible directory: {parent}")
    result = []
    try:
        with os.scandir(parent) as entries:
            for entry in entries:
                if entry.name.upper() in SYSTEM_DIRECTORIES:
                    continue
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    result.append({
                        "path": str(Path(entry.path).resolve()),
                        "name": entry.name,
                    })
                except OSError:
                    continue
    except OSError as exc:
        raise PermissionError(f"Cannot list directory: {parent}") from exc
    return sorted(result, key=lambda item: item["name"].casefold())


def search_local_directories(query: str, max_results: int = 100) -> dict:
    term = query.strip().casefold()
    if not term:
        return {"folders": [], "truncated": False}
    matches = []
    visited = 0
    max_visited = 30000
    for root_info in list_local_roots():
        for current_root, directories, _ in os.walk(root_info["path"], topdown=True):
            directories[:] = [
                name for name in directories
                if name.upper() not in SYSTEM_DIRECTORIES
            ]
            for name in directories:
                visited += 1
                if term in name.casefold():
                    path = str((Path(current_root) / name).resolve())
                    matches.append({"path": path, "name": name})
                    if len(matches) >= max_results:
                        return {"folders": matches, "truncated": True}
                if visited >= max_visited:
                    return {"folders": matches, "truncated": True}
    return {"folders": matches, "truncated": False}


def estimate_local_scan(db: Session, included_paths: list[str], excluded_paths: list[str]) -> dict:
    roots = [_canonical_path(path) for path in included_paths]
    exclusions = [_canonical_path(path) for path in excluded_paths]
    if not roots:
        return {"estimated_files": 0, "estimated_bytes": 0, "basis": "indexed assets"}
    assets = db.scalars(
        select(Asset).where(
            Asset.source == "local_pc",
            _directory_query(roots),
        )
    ).all()
    included_assets = [
        asset for asset in assets
        if not any(_is_within(asset.path, exclusion) for exclusion in exclusions)
    ]
    return {
        "estimated_files": len(included_assets),
        "estimated_bytes": sum(asset.size_bytes for asset in included_assets),
        "basis": "currently indexed assets",
    }

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
    folder_path: str | list[str],
    excluded_paths: list[str] | None = None,
) -> dict:
    requested_roots = [folder_path] if isinstance(folder_path, str) else folder_path
    roots = []
    for path in requested_roots:
        root = _canonical_path(path)
        if not root.exists():
            raise FileNotFoundError(f"Folder does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {root}")
        if not any(_is_within(root, existing_root) for existing_root in roots):
            roots.append(root)

    if not roots:
        raise ValueError("At least one included folder is required.")

    exclusions = list(dict.fromkeys(
        _canonical_path(path) for path in (excluded_paths or [])
    ))
    invalid_exclusions = [
        exclusion for exclusion in exclusions
        if not any(_is_within(exclusion, root) for root in roots)
    ]
    if invalid_exclusions:
        raise ValueError(
            "Excluded folders must be inside an included folder: "
            + ", ".join(str(path) for path in invalid_exclusions)
        )

    source = "local_pc"
    scan_time = datetime.now(timezone.utc)

    discovered_paths: set[str] = set()

    files_scanned = 0
    files_added = 0
    files_updated = 0
    files_unchanged = 0
    files_skipped = 0
    errors = []
    analysis_asset_ids: list[int] = []

    for root in roots:
        for current_root, directories, filenames in os.walk(root, topdown=True):
            current_path = _canonical_path(current_root)
            directories[:] = [
                directory
                for directory in directories
                if directory.upper() not in SYSTEM_DIRECTORIES
                and not any(
                    _is_within(current_path / directory, exclusion)
                    for exclusion in exclusions
                )
            ]

            for filename in filenames:
                file_path = Path(current_root) / filename
                try:
                    if file_path.is_symlink() or not file_path.is_file():
                        continue
                    normalized_path = str(file_path.resolve())
                    if any(_is_within(normalized_path, exclusion) for exclusion in exclusions):
                        continue
                    discovered_paths.add(normalized_path)
                    stat = file_path.stat()
                    extension = file_path.suffix.lower() or None
                    mime_type, _ = mimetypes.guess_type(str(file_path))
                    file_type = classify_file_type(extension or "")
                    created_at, modified_at, accessed_at = get_file_times(file_path)
                    existing_asset = db.scalar(
                        select(Asset).where(
                            Asset.source == source,
                            Asset.source_file_id == normalized_path,
                        )
                    )

                    if existing_asset:
                        content_changed = (
                            existing_asset.size_bytes != stat.st_size
                            or existing_asset.modified_at != modified_at
                            or existing_asset.is_missing
                        )
                        analysis_asset_ids.append(existing_asset.id)
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
                        if content_changed:
                            existing_asset.sha256 = None
                            existing_asset.perceptual_hash = None
                            files_updated += 1
                        else:
                            files_unchanged += 1
                    else:
                        new_asset = Asset(
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
                        db.add(new_asset)
                        db.flush()
                        analysis_asset_ids.append(new_asset.id)
                        files_added += 1
                    files_scanned += 1
                except (OSError, PermissionError) as exc:
                    files_skipped += 1
                    errors.append({"path": str(file_path), "error": str(exc)})

    # Mark previously indexed files under this scan root as missing
    # if they were not discovered during this scan.
    assets_under_root = db.scalars(
        select(Asset).where(
            Asset.source == source,
            _directory_query(roots),
        )
    ).all()

    missing_files_marked = 0

    for asset in assets_under_root:
        if (
            any(_is_within(asset.path, root) for root in roots)
            and not any(_is_within(asset.path, exclusion) for exclusion in exclusions)
            and asset.path not in discovered_paths
            and not asset.is_missing
        ):
            asset.is_missing = True
            asset.last_scanned_at = scan_time
            missing_files_marked += 1

    db.commit()

    return {
        "folder": str(roots[0]) if len(roots) == 1 else None,
        "included_paths": [str(root) for root in roots],
        "excluded_paths": [str(path) for path in exclusions],
        "files_scanned": files_scanned,
        "files_added": files_added,
        "files_updated": files_updated,
        "files_unchanged": files_unchanged,
        "files_skipped": files_skipped,
        "missing_files_marked": missing_files_marked,
        "errors": errors,
        "analysis_asset_ids": analysis_asset_ids,
        "scanned_at": scan_time.isoformat(),
    }
