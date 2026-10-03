from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.analysis_job import AnalysisJob
from app.models.asset import Asset
from app.models.image_analysis import ImageAnalysis


IMAGE_ANALYSIS = "IMAGE_ANALYSIS"
DOCUMENT_ANALYSIS = "DOCUMENT_ANALYSIS"
VIDEO_ANALYSIS = "VIDEO_ANALYSIS"
FACE_ANALYSIS = "FACE_ANALYSIS"

PENDING = "PENDING"
PROCESSING = "PROCESSING"
ANALYZED = "ANALYZED"
FAILED = "FAILED"

DOCUMENT_NAME_HINTS = (
    "aadhaar", "aadhar", "certificate", "marksheet", "mark sheet", "invoice",
    "receipt", "bill", "passport", "license", "licence", "pan", "insurance",
)

_worker_lock = threading.Lock()
_worker_running = False


def asset_signature(asset: Asset) -> str:
    modified = asset.modified_at.isoformat() if asset.modified_at else ""
    return f"{asset.size_bytes}:{modified}:{asset.sha256 or ''}"


def _document_image_candidate(asset: Asset) -> bool:
    name = asset.name.casefold()
    return any(hint in name for hint in DOCUMENT_NAME_HINTS)


def eligible_job_types(asset: Asset) -> tuple[str, ...]:
    if asset.source != "local_pc" or asset.is_missing:
        return ()
    if asset.file_type == "image":
        jobs = [IMAGE_ANALYSIS, FACE_ANALYSIS]
        if _document_image_candidate(asset):
            jobs.append(DOCUMENT_ANALYSIS)
        return tuple(jobs)
    if asset.file_type == "document":
        return (DOCUMENT_ANALYSIS,)
    if asset.file_type == "video":
        return (VIDEO_ANALYSIS,)
    return ()


def enqueue_asset_jobs(db: Session, assets: list[Asset]) -> dict[str, int]:
    queued = 0
    skipped = 0
    now = datetime.now(timezone.utc)
    for asset in assets:
        signature = asset_signature(asset)
        for job_type in eligible_job_types(asset):
            existing = db.scalar(
                select(AnalysisJob.id).where(
                    AnalysisJob.asset_id == asset.id,
                    AnalysisJob.job_type == job_type,
                    AnalysisJob.asset_signature == signature,
                )
            )
            if existing is not None:
                skipped += 1
                continue
            db.add(AnalysisJob(
                asset_id=asset.id,
                job_type=job_type,
                status=PENDING,
                asset_signature=signature,
                created_at=now,
            ))
            queued += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent scan won the unique insert race. Its job is sufficient.
        skipped += queued
        queued = 0
    return {"queued": queued, "already_current": skipped}


def _persist_image_analysis(db: Session, asset: Asset) -> None:
    from app.services.image_analyzer import get_image_analyzer

    result = get_image_analyzer().analyze(asset.path)
    analysis = db.scalar(
        select(ImageAnalysis).where(ImageAnalysis.asset_id == asset.id)
    )
    if analysis is None:
        analysis = ImageAnalysis(
            asset_id=asset.id,
            model_name=result["model_name"],
            analyzed_at=datetime.now(timezone.utc),
        )
        db.add(analysis)
    analysis.caption = result["caption"]
    analysis.category = result["category"]
    analysis.tags = result["tags"]
    analysis.model_name = result["model_name"]
    analysis.processing_time_ms = result["processing_time_ms"]
    analysis.analyzed_at = datetime.now(timezone.utc)


def _process_job(db: Session, job: AnalysisJob) -> None:
    asset = db.get(Asset, job.asset_id)
    if asset is None or asset.is_missing:
        raise FileNotFoundError("The indexed asset is missing.")
    if job.asset_signature != asset_signature(asset):
        raise RuntimeError("The asset changed after this job was queued.")

    if job.job_type == IMAGE_ANALYSIS:
        _persist_image_analysis(db, asset)
    elif job.job_type == DOCUMENT_ANALYSIS:
        from app.services.document_analyzer import analyze_document
        analyze_document(db=db, asset_id=asset.id, force=True)
    elif job.job_type == VIDEO_ANALYSIS:
        from app.services.video_analyzer import analyze_video
        analyze_video(db=db, asset_id=asset.id)
    elif job.job_type == FACE_ANALYSIS:
        from app.services.face_analyzer import analyze_asset_faces
        analyze_asset_faces(db, asset)
    else:
        raise ValueError(f"Unsupported analysis job type: {job.job_type}")


def process_pending_jobs(limit: int = 10) -> int:
    processed = 0
    while processed < limit:
        db = SessionLocal()
        try:
            job = db.scalar(
                select(AnalysisJob)
                .where(AnalysisJob.status == PENDING)
                .order_by(
                    case(
                        (AnalysisJob.job_type == DOCUMENT_ANALYSIS, 0),
                        (AnalysisJob.job_type == VIDEO_ANALYSIS, 1),
                        (AnalysisJob.job_type == IMAGE_ANALYSIS, 2),
                        else_=3,
                    ),
                    AnalysisJob.created_at.asc(),
                    AnalysisJob.id.asc(),
                )
                .limit(1)
            )
            if job is None:
                return processed
            job.status = PROCESSING
            job.started_at = datetime.now(timezone.utc)
            job.error_message = None
            db.commit()
            try:
                _process_job(db, job)
                job.status = ANALYZED
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception as exc:
                db.rollback()
                job = db.get(AnalysisJob, job.id)
                if job is not None:
                    job.status = FAILED
                    job.retry_count += 1
                    job.error_message = str(exc)[:4000]
                    job.completed_at = datetime.now(timezone.utc)
                    db.commit()
            processed += 1
        finally:
            db.close()
    return processed


def drain_pending_jobs(batch_size: int = 100) -> int:
    processed_total = 0
    while True:
        processed = process_pending_jobs(limit=batch_size)
        processed_total += processed
        if processed < batch_size:
            return processed_total


def start_analysis_worker(limit: int = 100) -> None:
    global _worker_running
    with _worker_lock:
        if _worker_running:
            return
        _worker_running = True

    def run() -> None:
        global _worker_running
        try:
            drain_pending_jobs(batch_size=limit)
        finally:
            with _worker_lock:
                _worker_running = False

    threading.Thread(target=run, name="ai-dam-analysis-worker", daemon=True).start()


def recover_interrupted_jobs(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    jobs = db.scalars(
        select(AnalysisJob).where(
            AnalysisJob.status == PROCESSING,
            AnalysisJob.started_at.is_not(None),
            AnalysisJob.started_at < cutoff,
        )
    ).all()
    for job in jobs:
        job.status = PENDING
        job.error_message = "Recovered after an interrupted worker."
        job.started_at = None
    if jobs:
        db.commit()
    return len(jobs)


def analysis_progress(db: Session) -> dict:
    rows = db.execute(
        select(AnalysisJob.job_type, AnalysisJob.status, func.count(AnalysisJob.id))
        .group_by(AnalysisJob.job_type, AnalysisJob.status)
    ).all()
    by_type: dict[str, dict[str, int]] = {}
    for job_type, status, count in rows:
        bucket = by_type.setdefault(job_type, {PENDING: 0, PROCESSING: 0, ANALYZED: 0, FAILED: 0})
        bucket[status] = count
    totals = {PENDING: 0, PROCESSING: 0, ANALYZED: 0, FAILED: 0}
    for bucket in by_type.values():
        for status in totals:
            totals[status] += bucket.get(status, 0)
    return {"totals": totals, "by_type": by_type, "worker_running": _worker_running}
