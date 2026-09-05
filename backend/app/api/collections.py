from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.asset import Asset
from app.models.collection import Collection, CollectionMember
from app.services.collection_engine import generate_all_suggestions


router = APIRouter(
    prefix="/api/collections",
    tags=["AI Collections"],
)


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    asset_ids: list[int] = Field(min_length=1)
    description: str | None = None


@router.get("/suggestions")
def get_suggestions(db: Session = Depends(get_db)):
    return generate_all_suggestions(db)


@router.post("/approve")
def approve_collection(
    request: CollectionCreateRequest,
    db: Session = Depends(get_db),
):
    assets = db.scalars(
        select(Asset).where(
            Asset.id.in_(request.asset_ids),
            Asset.is_missing.is_(False),
        )
    ).all()

    if not assets:
        raise HTTPException(
            status_code=400,
            detail="No valid assets were selected.",
        )

    collection = Collection(
        name=request.name,
        description=request.description,
        collection_type="ai_suggested",
        status="approved",
        created_at=datetime.now(timezone.utc),
    )

    db.add(collection)
    db.flush()

    added_at = datetime.now(timezone.utc)

    for asset in assets:
        db.add(
            CollectionMember(
                collection_id=collection.id,
                asset_id=asset.id,
                added_at=added_at,
            )
        )

    db.commit()
    db.refresh(collection)

    return {
        "id": collection.id,
        "name": collection.name,
        "status": collection.status,
        "asset_count": len(assets),
    }


@router.get("")
def list_collections(db: Session = Depends(get_db)):
    collections = db.scalars(
        select(Collection).order_by(Collection.created_at.desc())
    ).all()

    result = []

    for collection in collections:
        assets = db.scalars(
            select(Asset)
            .join(
                CollectionMember,
                CollectionMember.asset_id == Asset.id,
            )
            .where(
                CollectionMember.collection_id == collection.id,
                Asset.is_missing.is_(False),
            )
            .order_by(Asset.modified_at.desc().nullslast(), Asset.id.desc())
        ).all()

        result.append(
            {
                "id": collection.id,
                "name": collection.name,
                "description": collection.description,
                "collection_type": collection.collection_type,
                "status": collection.status,
                "confidence": collection.confidence,
                "asset_count": len(assets),
                "created_at": collection.created_at.isoformat(),
                "assets": [
                    {
                        "id": asset.id,
                        "source": asset.source,
                        "name": asset.name,
                        "path": asset.path,
                        "extension": asset.extension,
                        "mime_type": asset.mime_type,
                        "file_type": asset.file_type,
                        "size_bytes": asset.size_bytes,
                        "created_at": (
                            asset.created_at.isoformat()
                            if asset.created_at
                            else None
                        ),
                        "modified_at": (
                            asset.modified_at.isoformat()
                            if asset.modified_at
                            else None
                        ),
                        "accessed_at": (
                            asset.accessed_at.isoformat()
                            if asset.accessed_at
                            else None
                        ),
                        "is_missing": asset.is_missing,
                        "last_scanned_at": (
                            asset.last_scanned_at.isoformat()
                            if asset.last_scanned_at
                            else None
                        ),
                    }
                    for asset in assets
                ],
            }
        )

    return {
        "total": len(result),
        "items": result,
    }