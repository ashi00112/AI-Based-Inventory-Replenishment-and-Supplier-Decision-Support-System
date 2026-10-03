import time
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.database.session import get_db
from app.schemas.health import HealthResponse, DocumentIRHealthResponse
from app.services.chroma_service import check_document_ir_health

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System and Database Health Check",
    description="Validates that the FastAPI application is running and performs a ping query to Supabase PostgreSQL.",
)
def get_health(db: Session = Depends(get_db)) -> HealthResponse:
    db_connected = False
    latency_ms = None

    try:
        start_time = time.perf_counter()
        # Perform lightweight connectivity probe
        db.execute(text("SELECT 1"))
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        db_connected = True
    except Exception:
        db_connected = False
        latency_ms = None

    overall_status = "ok" if db_connected else "degraded"

    return HealthResponse(
        status=overall_status,
        environment=settings.ENVIRONMENT,
        project_name=settings.PROJECT_NAME,
        database_connected=db_connected,
        database_latency_ms=latency_ms,
    )


@router.get(
    "/health/document-ir",
    response_model=DocumentIRHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Document IR and Vector Store Health Check",
    description="Operational readiness probe for PostgreSQL document metadata, ChromaDB vector collection, and embedding service.",
)
def get_document_ir_health(db: Session = Depends(get_db)) -> DocumentIRHealthResponse:
    health_data = check_document_ir_health(db=db)
    return DocumentIRHealthResponse(**health_data)

