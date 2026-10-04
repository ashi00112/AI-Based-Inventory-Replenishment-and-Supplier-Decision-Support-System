from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import health
from app.routers.api import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Lightweight startup reconciliation check
    try:
        from app.database.session import SessionLocal
        from app.services.chroma_service import reconcile_index_state
        db = SessionLocal()
        try:
            summary = reconcile_index_state(db=db, repair=False)
            unindexed = summary.get("active_unindexed", 0)
            missing_source = summary.get("missing_source_count", 0)
            if unindexed > 0 or missing_source > 0:
                logger.warning(
                    "Document IR startup check: index mismatch detected (%d active unindexed, %d missing source files). "
                    "Run reconciliation/bootstrap to restore index.",
                    unindexed,
                    missing_source,
                )
            else:
                logger.info(
                    "Document IR startup check: %d active documents verified in sync.",
                    summary.get("active_indexed", 0),
                )
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Startup document IR check skipped or non-fatal error: %s", exc)
    yield


def create_application() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Set up Cross-Origin Resource Sharing (CORS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root health endpoint (accessible at GET /health)
    app.include_router(health.router)

    # Versioned API routes (accessible at GET /api/v1/...)
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/", tags=["Root"])
    def root():
        return {
            "message": f"Welcome to {settings.PROJECT_NAME}",
            "docs": "/docs",
            "health": "/health",
            "api_version": settings.API_V1_STR,
        }

    return app


app = create_application()
