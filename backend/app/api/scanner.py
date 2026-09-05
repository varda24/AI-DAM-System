from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.local_scanner import scan_local_folder

router = APIRouter(
    prefix="/api/scanner",
    tags=["Scanner"],
)

class ScanRequest(BaseModel):
    folder_path: str

@router.post("/local")
def scan_local(
    request: ScanRequest,
    db: Session = Depends(get_db),
):
    try:
        return scan_local_folder(
            db=db,
            folder_path=request.folder_path,
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except NotADirectoryError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )