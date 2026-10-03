from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.analysis_job import AnalysisJob
from app.services.analysis_jobs import PENDING, analysis_progress, start_analysis_worker


router = APIRouter(prefix="/api/analysis-jobs", tags=["Analysis Jobs"])


@router.get("/progress")
def get_analysis_progress(db: Session = Depends(get_db)):
    return analysis_progress(db)


@router.get("")
def list_analysis_jobs(limit: int = 100, db: Session = Depends(get_db)):
    jobs = db.scalars(
        select(AnalysisJob).order_by(AnalysisJob.created_at.desc()).limit(min(max(limit, 1), 500))
    ).all()
    return {"items": [{
        "id": job.id,
        "asset_id": job.asset_id,
        "job_type": job.job_type,
        "status": job.status,
        "error_message": job.error_message,
        "retry_count": job.retry_count,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    } for job in jobs]}


@router.post("/{job_id}/retry")
def retry_analysis_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(AnalysisJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Analysis job not found.")
    job.status = PENDING
    job.error_message = None
    job.started_at = None
    job.completed_at = None
    db.commit()
    start_analysis_worker()
    return {"id": job.id, "status": job.status}
