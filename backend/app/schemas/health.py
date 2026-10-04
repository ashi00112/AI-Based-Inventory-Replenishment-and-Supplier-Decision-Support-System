from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall service status, e.g. 'ok' or 'degraded'")
    environment: str = Field(..., description="Current running environment")
    project_name: str = Field(..., description="Application project title")
    database_connected: bool = Field(..., description="Indicates if Supabase PostgreSQL connection is operational")
    database_latency_ms: Optional[float] = Field(None, description="Database ping latency in milliseconds")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Server UTC timestamp")


class DocumentIRHealthResponse(BaseModel):
    status: str = Field(..., description="Overall health status: healthy | degraded | unhealthy")
    postgres_connected: bool = Field(..., description="PostgreSQL database connectivity flag")
    chroma_available: bool = Field(..., description="ChromaDB collection availability flag")
    embedding_available: bool = Field(..., description="Embedding model availability flag")
    active_document_count: int = Field(..., description="Number of active documents in PostgreSQL")
    indexed_document_count: int = Field(..., description="Number of documents verified as indexed")
    failed_document_count: int = Field(..., description="Number of documents with failed index status")
    missing_source_count: int = Field(0, description="Number of active documents whose source PDF is missing from storage")
    vector_count: int = Field(..., description="Total vector count in ChromaDB collection")
    index_version: str = Field(..., description="Active index configuration version")
    details: Optional[str] = Field(None, description="Diagnostic summary without sensitive paths or secrets")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Server UTC timestamp")

