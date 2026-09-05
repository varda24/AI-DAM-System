from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assets import router as assets_router
from app.api.cleanup import router as cleanup_router
from app.api.collections import router as collections_router
from app.api.duplicates import router as duplicates_router
from app.api.image_analysis import router as image_analysis_router
from app.api.people import router as people_router
from app.api.scanner import router as scanner_router
from app.api.similarity import router as similarity_router
from app.api.storage import router as storage_router
from app.core.config import settings


app = FastAPI(
    title="AI-Powered Digital Asset Management System",
    description=(
        "Cross-platform digital asset management "
        "and storage optimization system."
    ),
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(scanner_router)
app.include_router(assets_router)
app.include_router(duplicates_router)
app.include_router(image_analysis_router)
app.include_router(people_router)
app.include_router(cleanup_router)
app.include_router(collections_router)
app.include_router(storage_router)
app.include_router(similarity_router)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
    }