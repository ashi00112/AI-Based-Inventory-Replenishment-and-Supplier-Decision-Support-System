import os
from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Based Inventory Replenishment & Supplier Decision Support System"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    # CORS origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    # Supabase PostgreSQL Database
    DATABASE_URL: Union[str, None] = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
    )

    # JWT Authentication
    JWT_SECRET_KEY: str = "smartsupply-dev-secret-key-at-least-32-bytes-long-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Document Storage & Upload Limits
    DOCUMENT_STORAGE_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "documents"
    )
    MAX_PDF_UPLOAD_SIZE_MB: int = 10
    # Embedding and vector store configuration
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    CHROMA_PERSIST_DIR: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "chroma"
    )
    CHROMA_COLLECTION_NAME: str = "smartsupply_documents"
    DOCUMENT_INDEX_VERSION: str = "v1"

    # LLM & Member 3 Supplier Agent configuration
    GEMINI_API_KEY: Union[str, None] = None
    LLM_MODEL_NAME: str = "gemini-1.5-flash"
    LLM_TIMEOUT_SECONDS: int = 15
    FUZZY_MATCH_THRESHOLD: float = 75.0
    FUZZY_AMBIGUITY_MARGIN: float = 5.0


    @property
    def sync_database_url(self) -> str:
        """
        Returns the SQLAlchemy database connection URL.
        Automatically normalizes postgresql:// to postgresql+psycopg:// for Psycopg 3,
        and ensures sslmode=require is configured for Supabase cloud hosts.
        """
        url = self.DATABASE_URL or ""
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        if ("supabase.co" in url or "supabase.com" in url) and "sslmode" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode=require"
        return url

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
