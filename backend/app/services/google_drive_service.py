from __future__ import annotations

import hashlib
import mimetypes
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.asset import Asset
from app.services.image_similarity import calculate_perceptual_hash


SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

BACKEND_ROOT = Path(__file__).resolve().parents[2]
MAX_HASH_SIZE_BYTES = 50 * 1024 * 1024
HASH_CHUNK_SIZE = 1024 * 1024

_oauth_states: set[str] = set()


def get_client_secret_file() -> Path:
    path = Path(settings.GOOGLE_CLIENT_SECRET_FILE)

    if not path.is_absolute():
        path = BACKEND_ROOT / path

    return path


def get_token_file() -> Path:
    path = Path(settings.GOOGLE_DRIVE_TOKEN_FILE)

    if not path.is_absolute():
        path = BACKEND_ROOT / path

    return path


def get_redirect_uri() -> str:
    return settings.GOOGLE_REDIRECT_URI


def create_oauth_flow(state: str | None = None) -> Flow:
    client_secret_file = get_client_secret_file()

    if not client_secret_file.exists():
        raise FileNotFoundError(
            f"Google OAuth credentials file not found: {client_secret_file}"
        )

    flow = Flow.from_client_secrets_file(
        str(client_secret_file),
        scopes=SCOPES,
        state=state,
        autogenerate_code_verifier=False,
    )

    flow.redirect_uri = get_redirect_uri()
    return flow

def create_authorization_url() -> dict[str, str]:
    state = secrets.token_urlsafe(32)
    _oauth_states.add(state)

    flow = create_oauth_flow(state=state)

    authorization_url, returned_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    return {
        "authorization_url": authorization_url,
        "state": returned_state,
    }


def complete_authorization(code: str, state: str) -> None:
    if state not in _oauth_states:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state.",
        )

    _oauth_states.discard(state)

    flow = create_oauth_flow(state=state)
    flow.fetch_token(code=code)

    credentials = flow.credentials
    token_file = get_token_file()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_token_file = token_file.with_suffix(token_file.suffix + ".tmp")
    try:
        temporary_token_file.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )
        try:
            temporary_token_file.chmod(0o600)
        except OSError:
            pass
        temporary_token_file.replace(token_file)
    finally:
        temporary_token_file.unlink(missing_ok=True)


def load_credentials() -> Credentials | None:
    token_file = get_token_file()

    if not token_file.exists():
        return None

    try:
        credentials = Credentials.from_authorized_user_file(
            str(token_file),
            SCOPES,
        )
    except Exception:
        return None

    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            temporary_token_file = token_file.with_suffix(token_file.suffix + ".tmp")
            try:
                temporary_token_file.write_text(
                    credentials.to_json(),
                    encoding="utf-8",
                )
                try:
                    temporary_token_file.chmod(0o600)
                except OSError:
                    pass
                temporary_token_file.replace(token_file)
            finally:
                temporary_token_file.unlink(missing_ok=True)
        except Exception:
            return None

    if not credentials.valid:
        return None

    return credentials


def get_drive_service():
    credentials = load_credentials()

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Google Drive is not connected.",
        )

    return build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def get_connection_status() -> dict[str, Any]:
    credentials = load_credentials()

    return {
        "connected": credentials is not None,
        "source": "google_drive",
        "account": None,
        "scopes": SCOPES,
    }


def disconnect_google_drive() -> dict[str, str]:
    token_file = get_token_file()

    if token_file.exists():
        token_file.unlink()

    return {
        "message": "Google Drive disconnected successfully.",
    }


def list_drive_files(
    page_size: int = 100,
    page_token: str | None = None,
    parent_id: str | None = None,
    folders_only: bool = False,
) -> dict[str, Any]:
    service = get_drive_service()
    query_parts = ["trashed = false"]
    if parent_id:
        escaped_parent_id = parent_id.replace("\\", "\\\\").replace("'", "\\'")
        query_parts.append(f"'{escaped_parent_id}' in parents")
    if folders_only:
        query_parts.append("mimeType = 'application/vnd.google-apps.folder'")
    query = " and ".join(query_parts)

    response = (
        service.files()
        .list(
            pageSize=max(1, min(page_size, 1000)),
            pageToken=page_token,
            q=query,
            spaces="drive",
            fields=(
                "nextPageToken,"
                "files("
                "id,"
                "name,"
                "mimeType,"
                "size,"
                "createdTime,"
                "modifiedTime,"
                "parents,"
                "webViewLink,"
                "md5Checksum"
                ")"
            ),
            orderBy="folder,name",
        )
        .execute()
    )

    return response


def get_drive_about() -> dict[str, Any]:
    service = get_drive_service()

    response = (
        service.about()
        .get(
            fields="user(displayName,emailAddress,permissionId,photoLink),storageQuota"
        )
        .execute()
    )

    return response


def _account_key(about: dict[str, Any]) -> str:
    user = about.get("user") or {}
    account_key = user.get("permissionId") or user.get("emailAddress")
    if not account_key:
        raise HTTPException(
            status_code=502,
            detail="Google Drive did not return an account identifier.",
        )
    return str(account_key)


def _drive_file_type(mime_type: str, name: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith("audio/"):
        return "audio"
    if mime_type.startswith("application/vnd.google-apps."):
        return "document"
    guessed_type, _ = mimetypes.guess_type(name)
    if guessed_type:
        if guessed_type.startswith("image/"):
            return "image"
        if guessed_type.startswith("video/"):
            return "video"
        if guessed_type.startswith("audio/"):
            return "audio"
        if guessed_type.startswith("text/") or "document" in guessed_type:
            return "document"
    return "other"


def _drive_datetime(value: str | None):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _same_datetime(first: datetime | None, second: datetime | None) -> bool:
    if first is None or second is None:
        return first is second
    if first.tzinfo is None:
        first = first.replace(tzinfo=timezone.utc)
    if second.tzinfo is None:
        second = second.replace(tzinfo=timezone.utc)
    return first == second


def sync_drive_assets(
    db: Session,
    max_files: int = 100,
    page_token: str | None = None,
    parent_id: str | None = None,
) -> dict[str, Any]:
    service = get_drive_service()
    about = service.about().get(
        fields="user(displayName,emailAddress,permissionId)"
    ).execute()
    account_key = _account_key(about)

    files: list[dict[str, Any]] = []
    while len(files) < max_files:
        page_size = min(100, max_files - len(files))
        query_parts = [
            "trashed = false",
            "mimeType != 'application/vnd.google-apps.folder'",
        ]
        if parent_id:
            escaped_parent_id = parent_id.replace("\\", "\\\\").replace("'", "\\'")
            query_parts.append(f"'{escaped_parent_id}' in parents")
        response = service.files().list(
            pageSize=page_size,
            pageToken=page_token,
            q=" and ".join(query_parts),
            spaces="drive",
            fields=(
                "nextPageToken,files(id,name,mimeType,size,createdTime,"
                "modifiedTime,parents,webViewLink)"
            ),
            orderBy="folder,name",
        ).execute()
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    drive_ids = [str(item["id"]) for item in files if item.get("id")]
    indexed = {}
    if drive_ids:
        existing_assets = db.scalars(
            select(Asset).where(
                Asset.source == "google_drive",
                Asset.source_account_id == account_key,
                Asset.source_file_id.in_(drive_ids),
            )
        ).all()
        indexed = {asset.source_file_id: asset for asset in existing_assets}

    added = 0
    updated = 0
    unchanged = 0
    sync_time = datetime.now(timezone.utc)

    for drive_file in files:
        drive_id = str(drive_file.get("id", ""))
        name = str(drive_file.get("name") or drive_id)
        mime_type = str(drive_file.get("mimeType") or "application/octet-stream")
        file_key = drive_id
        parents = drive_file.get("parents") or []
        parent_id = str(parents[0]) if parents else None
        path = "Google Drive/" + name
        try:
            size_bytes = int(drive_file.get("size") or 0)
        except (TypeError, ValueError):
            size_bytes = 0
        created_at = _drive_datetime(drive_file.get("createdTime"))
        modified_at = _drive_datetime(drive_file.get("modifiedTime"))
        asset = indexed.get(file_key)

        if asset is None:
            asset = Asset(
                source="google_drive",
                source_account_id=account_key,
                source_file_id=file_key,
                source_folder_id=parent_id,
                web_view_link=drive_file.get("webViewLink"),
                name=name,
                path=path,
                extension=Path(name).suffix.lower() or None,
                mime_type=mime_type,
                file_type=_drive_file_type(mime_type, name),
                size_bytes=size_bytes,
                created_at=created_at,
                modified_at=modified_at,
                accessed_at=None,
                is_missing=False,
                last_scanned_at=sync_time,
            )
            db.add(asset)
            added += 1
            continue

        content_changed = (
            not _same_datetime(asset.modified_at, modified_at)
            or asset.size_bytes != size_bytes
        )
        metadata_changed = content_changed or any((
            asset.name != name,
            asset.path != path,
            asset.source_folder_id != parent_id,
            asset.mime_type != mime_type,
            asset.web_view_link != drive_file.get("webViewLink"),
        ))
        if content_changed:
            asset.sha256 = None
            asset.perceptual_hash = None
        if metadata_changed:
            updated += 1
        else:
            unchanged += 1
        asset.name = name
        asset.path = path
        asset.source_folder_id = parent_id
        asset.extension = Path(name).suffix.lower() or None
        asset.mime_type = mime_type
        asset.file_type = _drive_file_type(mime_type, name)
        asset.size_bytes = size_bytes
        asset.created_at = created_at
        asset.modified_at = modified_at
        asset.web_view_link = drive_file.get("webViewLink")
        asset.is_missing = False
        asset.last_scanned_at = sync_time

    db.commit()
    return {
        "source": "google_drive",
        "account": (about.get("user") or {}).get("emailAddress"),
        "source_account_id": account_key,
        "parent_id": parent_id,
        "files_seen": len(files),
        "files_added": added,
        "files_updated": updated,
        "files_unchanged": unchanged,
        "max_files": max_files,
        "limited": bool(page_token),
        "next_page_token": page_token,
        "content_downloaded": False,
    }


def hash_drive_asset(db: Session, asset_id: int) -> dict[str, Any]:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    if asset.source != "google_drive":
        raise HTTPException(
            status_code=400,
            detail="Content hashing is only available for Google Drive assets.",
        )

    account_key = asset.source_account_id
    drive_file_id = asset.source_file_id
    if not account_key or not drive_file_id:
        raise HTTPException(status_code=400, detail="Invalid Drive asset identifier.")

    service = get_drive_service()
    about = service.about().get(
        fields="user(displayName,emailAddress,permissionId)"
    ).execute()
    if _account_key(about) != account_key:
        raise HTTPException(
            status_code=403,
            detail="This asset belongs to a different Google Drive account.",
        )

    metadata = service.files().get(
        fileId=drive_file_id,
        fields="id,name,mimeType,size,modifiedTime",
    ).execute()
    mime_type = str(metadata.get("mimeType") or "")
    if mime_type.startswith("application/vnd.google-apps."):
        raise HTTPException(
            status_code=415,
            detail="Native Google Workspace files are not downloaded for hashing.",
        )
    try:
        expected_size = int(metadata.get("size"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=415,
            detail="Drive did not provide a file size; content fetch was skipped.",
        ) from None
    if expected_size > MAX_HASH_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="File exceeds the 50 MiB content-hashing limit.",
        )
    remote_modified_at = _drive_datetime(metadata.get("modifiedTime"))
    if (
        asset.sha256
        and asset.size_bytes == expected_size
        and _same_datetime(asset.modified_at, remote_modified_at)
    ):
        return {
            "asset_id": asset.id,
            "sha256": asset.sha256,
            "perceptual_hash": asset.perceptual_hash,
            "bytes_hashed": 0,
            "maximum_bytes": MAX_HASH_SIZE_BYTES,
            "cached": True,
        }

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="ai-dam-drive-",
            suffix=asset.extension or ".bin",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            downloader = MediaIoBaseDownload(
                temp_file,
                service.files().get_media(fileId=drive_file_id),
                chunksize=HASH_CHUNK_SIZE,
            )
            done = False
            while not done:
                _, done = downloader.next_chunk()
                if temp_file.tell() > MAX_HASH_SIZE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail="Downloaded content exceeds the 50 MiB limit.",
                    )

        digest = hashlib.sha256()
        with temp_path.open("rb") as content:
            while chunk := content.read(HASH_CHUNK_SIZE):
                digest.update(chunk)
        asset.sha256 = digest.hexdigest()
        if asset.file_type == "image":
            try:
                asset.perceptual_hash = calculate_perceptual_hash(temp_path)
            except Exception:
                asset.perceptual_hash = None
        db.commit()
        return {
            "asset_id": asset.id,
            "sha256": asset.sha256,
            "perceptual_hash": asset.perceptual_hash,
            "bytes_hashed": temp_path.stat().st_size,
            "maximum_bytes": MAX_HASH_SIZE_BYTES,
            "cached": False,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)