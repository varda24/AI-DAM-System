from __future__ import annotations

import logging
from pathlib import PureWindowsPath
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import desc, select

from app.models.asset import Asset
from app.api.assets import serialize_asset
from app.services.google_drive_service import (
    complete_authorization,
    create_authorization_url,
    disconnect_google_drive,
    get_connection_status,
    get_drive_about,
    _account_key,
    hash_drive_asset,
    list_drive_files,
    sync_drive_assets,
)
from app.core.database import get_db
from sqlalchemy.orm import Session


router = APIRouter(
    prefix="/api/google-drive",
    tags=["Google Drive"],
)
logger = logging.getLogger(__name__)


@router.get("/status")
def google_drive_status() -> dict[str, Any]:
    return get_connection_status()


@router.get("/connect")
def connect_google_drive() -> RedirectResponse:
    try:
        authorization_data = create_authorization_url()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return RedirectResponse(
        url=authorization_data["authorization_url"],
        status_code=307,
    )


@router.get("/oauth/callback")
def google_drive_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    if error:
        return {
            "connected": False,
            "error": error,
        }

    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing OAuth code or state.",
        )

    try:
        complete_authorization(
            code=code,
            state=state,
        )
    except Exception as exc:
        logger.exception("Google Drive OAuth callback failed.")
        raise HTTPException(
            status_code=400,
            detail="Google Drive authorization failed. Check backend logs for details.",
        ) from exc

    return {
        "connected": True,
        "message": (
            "Google Drive connected successfully. "
            "You may close this browser tab."
        ),
    }


@router.get("/about")
def google_drive_about() -> dict[str, Any]:
    return get_drive_about()


@router.get("/assets")
def google_drive_assets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=200),
    parent_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    account_key = _account_key(get_drive_about())
    query = select(Asset).where(
        Asset.source == "google_drive",
        Asset.source_account_id == account_key,
        Asset.is_missing.is_(False),
    )
    if parent_id:
        query = query.where(Asset.source_folder_id == parent_id)
    all_assets = db.scalars(query.order_by(desc(Asset.modified_at), Asset.id)).all()
    # Never surface a Windows filesystem path as a Drive location, even if an
    # earlier buggy sync wrote a malformed Drive row.
    all_assets = [
        asset for asset in all_assets
        if not PureWindowsPath(asset.path).is_absolute()
    ]
    total = len(all_assets)
    start = (page - 1) * page_size
    assets = all_assets[start:start + page_size]
    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
        "items": [serialize_asset(asset) for asset in assets],
    }


@router.get("/folders")
def google_drive_folders(
    parent_id: str | None = Query(default=None),
) -> dict[str, Any]:
    return list_drive_files(
        page_size=100,
        parent_id=parent_id or "root",
        folders_only=True,
    )


@router.get("/files")
def google_drive_files(
    page_size: int = Query(default=100, ge=1, le=1000),
    page_token: str | None = Query(default=None),
    parent_id: str | None = Query(default=None),
) -> dict[str, Any]:
    return list_drive_files(
        page_size=page_size,
        page_token=page_token,
        parent_id=parent_id,
    )


@router.post("/sync")
def google_drive_sync(
    max_files: int = Query(default=100, ge=1, le=200),
    page_token: str | None = Query(default=None),
    parent_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return sync_drive_assets(
        db=db,
        max_files=max_files,
        page_token=page_token,
        parent_id=parent_id,
    )


@router.post("/assets/{asset_id}/hash")
def google_drive_hash_asset(
    asset_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return hash_drive_asset(db=db, asset_id=asset_id)


@router.post("/disconnect")
def google_drive_disconnect() -> dict[str, str]:
    return disconnect_google_drive()