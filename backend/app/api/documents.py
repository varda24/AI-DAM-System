from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.analysis_job import AnalysisJob
from app.models.asset import Asset
from app.models.document_analysis import DocumentAnalysis
from app.services.document_analyzer import analyze_document
from app.services.document_analyzer import ocr_diagnostics
from app.services.document_status import (
    EXPIRED,
    EXPIRING_SOON,
    UNKNOWN,
    VALID,
    calculate_document_status,
    days_until_expiry,
)


router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)


class BatchAnalyzeRequest(BaseModel):
    asset_ids: list[int] = Field(
        min_length=1,
        max_length=20,
        description="Document asset IDs to analyze. Maximum 20 per request.",
    )


def _serialize_analysis(
    analysis: DocumentAnalysis,
) -> dict:
    current_status = calculate_document_status(
        analysis.expiry_date,
    )

    remaining_days = days_until_expiry(
        analysis.expiry_date,
    )

    return {
        "id": analysis.id,
        "asset_id": analysis.asset_id,
        "document_type": analysis.document_type,
        "confidence": analysis.confidence,
        "extracted_text": analysis.extracted_text,
        "extracted_name": analysis.extracted_name,
        "issue_date": (
            analysis.issue_date.isoformat()
            if analysis.issue_date
            else None
        ),
        "document_date": (
            analysis.document_date.isoformat()
            if analysis.document_date
            else None
        ),
        "expiry_date": (
            analysis.expiry_date.isoformat()
            if analysis.expiry_date
            else None
        ),
        "issue_date_source": analysis.issue_date_source,
        "expiry_date_source": analysis.expiry_date_source,
        "expiry_confidence": analysis.expiry_confidence,
        "issuing_organization": analysis.issuing_organization,
        "document_status": current_status,
        "days_until_expiry": remaining_days,
        "ocr_used": analysis.ocr_used,
        "page_count": analysis.page_count,
        "status": analysis.status,
        "error_message": analysis.error_message,
        "analyzed_at": (
            analysis.analyzed_at.isoformat()
            if analysis.analyzed_at
            else None
        ),
    }


@router.post("/{asset_id}/analyze")
def analyze_document_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found.",
        )

    if asset.file_type not in {"document", "image"}:
        raise HTTPException(
            status_code=400,
            detail="The selected asset is not classified as a document.",
        )

    if asset.is_missing:
        raise HTTPException(
            status_code=400,
            detail="The document file is missing from disk.",
        )

    try:
        analysis = analyze_document(
            db=db,
            asset_id=asset.id,
        )

        return _serialize_analysis(analysis)

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document analysis failed: {exc}",
        )


@router.post("/{asset_id}/reanalyze")
def reanalyze_document_asset(
    asset_id: int,
    db: Session = Depends(get_db),
):
    asset = db.query(Asset).filter(Asset.id == asset_id).first()

    if asset is None:
        raise HTTPException(
            status_code=404,
            detail="Asset not found.",
        )

    if asset.file_type not in {"document", "image"}:
        raise HTTPException(
            status_code=400,
            detail="The selected asset is not classified as a document.",
        )

    if asset.is_missing:
        raise HTTPException(
            status_code=400,
            detail="The document file is missing from disk.",
        )

    try:
        analysis = analyze_document(
            db=db,
            asset_id=asset.id,
            force=True,
        )

        return _serialize_analysis(analysis)

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Document re-analysis failed: {exc}",
        )


@router.get("/summary")
def document_summary(
    warning_days: int = Query(
        30,
        ge=1,
        le=365,
        description="Number of days used for EXPIRING SOON.",
    ),
    db: Session = Depends(get_db),
):
    analyses = (
        db.query(DocumentAnalysis)
        .join(
            Asset,
            Asset.id == DocumentAnalysis.asset_id,
        )
        .filter(
            Asset.is_missing.is_(False),
        )
        .all()
    )

    counts = {
        VALID: 0,
        EXPIRING_SOON: 0,
        EXPIRED: 0,
        UNKNOWN: 0,
    }

    for analysis in analyses:
        status = calculate_document_status(
            analysis.expiry_date,
            warning_days=warning_days,
        )

        counts[status] += 1

    return {
        "total_analyzed": len(analyses),
        "valid": counts[VALID],
        "expiring_soon": counts[EXPIRING_SOON],
        "expired": counts[EXPIRED],
        "unknown": counts[UNKNOWN],
        "warning_days": warning_days,
    }


@router.get("/expiry")
def document_expiry_list(
    status: str | None = Query(
        None,
        description="VALID, EXPIRING SOON, EXPIRED, or UNKNOWN",
    ),
    warning_days: int = Query(
        30,
        ge=1,
        le=365,
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
):
    analyses = (
        db.query(DocumentAnalysis)
        .join(
            Asset,
            Asset.id == DocumentAnalysis.asset_id,
        )
        .filter(
            Asset.is_missing.is_(False),
        )
        .all()
    )

    requested_status = status.upper() if status else None

    allowed_statuses = {
        VALID,
        EXPIRING_SOON,
        EXPIRED,
        UNKNOWN,
    }

    if requested_status and requested_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid status. Use VALID, EXPIRING SOON, "
                "EXPIRED, or UNKNOWN."
            ),
        )

    results = []

    for analysis in analyses:
        current_status = calculate_document_status(
            analysis.expiry_date,
            warning_days=warning_days,
        )

        if requested_status and current_status != requested_status:
            continue

        asset = db.query(Asset).filter(
            Asset.id == analysis.asset_id
        ).first()

        if asset is None:
            continue

        item = _serialize_analysis(analysis)

        item["name"] = asset.name
        item["path"] = asset.path
        item["size_bytes"] = asset.size_bytes
        item["file_type"] = asset.file_type

        results.append(item)

    def sort_key(item: dict):
        days = item.get("days_until_expiry")

        if days is None:
            return 10**9

        return days

    results.sort(key=sort_key)

    return {
        "warning_days": warning_days,
        "status": requested_status,
        "total": len(results),
        "documents": results[:limit],
    }


@router.post("/analyze-batch")
def analyze_document_batch(
    request: BatchAnalyzeRequest,
    db: Session = Depends(get_db),
):
    """
    Analyze a controlled set of document assets.

    Maximum: 20 documents per request.
    """

    unique_ids = list(dict.fromkeys(request.asset_ids))

    if len(unique_ids) > 20:
        raise HTTPException(
            status_code=400,
            detail="A maximum of 20 documents can be analyzed per batch.",
        )

    assets = (
        db.query(Asset)
        .filter(Asset.id.in_(unique_ids))
        .all()
    )

    asset_map = {
        asset.id: asset
        for asset in assets
    }

    results = []
    skipped = []

    for asset_id in unique_ids:
        asset = asset_map.get(asset_id)

        if asset is None:
            skipped.append(
                {
                    "asset_id": asset_id,
                    "reason": "Asset not found.",
                }
            )
            continue

        if asset.file_type not in {"document", "image"}:
            skipped.append(
                {
                    "asset_id": asset_id,
                    "name": asset.name,
                    "reason": "Asset is not classified as a document.",
                }
            )
            continue

        if asset.is_missing:
            skipped.append(
                {
                    "asset_id": asset_id,
                    "name": asset.name,
                    "reason": "Document file is missing from disk.",
                }
            )
            continue

        try:
            analysis = analyze_document(
                db=db,
                asset_id=asset.id,
            )

            results.append(
                _serialize_analysis(analysis)
            )

        except Exception as exc:
            skipped.append(
                {
                    "asset_id": asset_id,
                    "name": asset.name,
                    "reason": str(exc),
                }
            )

    return {
        "requested": len(unique_ids),
        "analyzed": len(results),
        "skipped": len(skipped),
        "results": results,
        "skipped_items": skipped,
    }


@router.get("/ocr-status")
def get_ocr_status():
    return ocr_diagnostics()


@router.get("/{asset_id}")
def get_document_analysis(
    asset_id: int,
    db: Session = Depends(get_db),
):
    analysis = (
        db.query(DocumentAnalysis)
        .filter(
            DocumentAnalysis.asset_id == asset_id,
        )
        .first()
    )

    if analysis is None:
        raise HTTPException(
            status_code=404,
            detail="Document analysis not found.",
        )

    return _serialize_analysis(analysis)


@router.get("")
def list_document_analyses(
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    latest_document_job_id = (
        select(func.max(AnalysisJob.id))
        .where(
            AnalysisJob.asset_id == Asset.id,
            AnalysisJob.job_type == "DOCUMENT_ANALYSIS",
        )
        .correlate(Asset)
        .scalar_subquery()
    )
    query = (
        select(Asset, DocumentAnalysis, AnalysisJob)
        .outerjoin(DocumentAnalysis, DocumentAnalysis.asset_id == Asset.id)
        .outerjoin(AnalysisJob, AnalysisJob.id == latest_document_job_id)
        .where(
            Asset.source == "local_pc",
            Asset.is_missing.is_(False),
            or_(
                Asset.file_type == "document",
                DocumentAnalysis.id.is_not(None),
                AnalysisJob.id.is_not(None),
            ),
        )
    )

    if status:
        requested_status = status.upper().replace("_", " ")
        query = query.where(
            func.upper(func.replace(DocumentAnalysis.document_status, "_", " "))
            == requested_status
        )

    rows = db.execute(
        query.order_by(
            func.coalesce(
                AnalysisJob.created_at,
                DocumentAnalysis.analyzed_at,
                Asset.modified_at,
            ).desc().nullslast(),
            Asset.id.desc(),
        ).offset(offset).limit(limit)
    ).all()

    results = []
    for asset, analysis, job in rows:
        if analysis is not None:
            item = _serialize_analysis(analysis)
        else:
            item = {
                "id": None,
                "asset_id": asset.id,
                "document_type": None,
                "confidence": None,
                "extracted_text": None,
                "extracted_name": None,
                "issue_date": None,
                "document_date": None,
                "expiry_date": None,
                "issue_date_source": None,
                "expiry_date_source": None,
                "expiry_confidence": None,
                "issuing_organization": None,
                "document_status": "UNKNOWN",
                "days_until_expiry": None,
                "ocr_used": False,
                "page_count": None,
                "status": "PENDING",
                "error_message": None,
                "analyzed_at": None,
            }

        item["name"] = asset.name
        item["path"] = asset.path
        item["size_bytes"] = asset.size_bytes
        item["source"] = asset.source
        item["file_type"] = asset.file_type
        item["analysis_status"] = (
            job.status if job else analysis.status if analysis else "NOT_QUEUED"
        )
        item["analysis_error"] = job.error_message if job else item["error_message"]
        results.append(item)

    return {
        "total": len(results),
        "limit": limit,
        "offset": offset,
        "documents": results,
    }
