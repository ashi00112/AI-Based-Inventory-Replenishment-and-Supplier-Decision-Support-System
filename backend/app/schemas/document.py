from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.document import DocumentType


class SupplierSummary(BaseModel):
    """
    Compact supplier representation nested inside DocumentResponse.
    """
    id: int
    supplier_code: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    """
    Public response schema for Document metadata.
    Does NOT leak internal filesystem paths or storage directories.
    """
    id: int
    title: str
    document_type: str
    supplier_id: Optional[int] = None
    supplier: Optional[SupplierSummary] = None
    original_filename: str
    mime_type: str
    file_size_bytes: int
    sha256_checksum: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    indexed: Optional[bool] = None
    index_status: Optional[str] = "not_indexed"
    last_indexed_at: Optional[datetime] = None
    index_version: Optional[str] = None
    index_error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentUpdate(BaseModel):
    """
    Payload for updating document metadata.
    Protects immutable file storage attributes (storage_key, file_size, checksum, original_filename).
    """
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    document_type: Optional[DocumentType] = None
    supplier_id: Optional[int] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(extra="forbid")
