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
