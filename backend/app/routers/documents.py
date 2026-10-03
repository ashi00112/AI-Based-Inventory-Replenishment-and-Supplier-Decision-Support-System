from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.document import DocumentResponse, DocumentUpdate
from app.schemas.document_processing import (
    DocumentExtractionResponse,
    DocumentChunksListResponse,
)
from app.services.document_service import (
    DocumentNotFoundError,
    DocumentServiceError,
    DocumentValidationError,
    SupplierNotFoundError,
    create_document,
    delete_document,
    get_document,
    get_document_file_path,
    list_documents,
    update_document,
)
from app.services.document_processing_service import (
    DocumentProcessingError,
    CorruptedPDFError,
    EncryptedPDFError,
    extract_document_text,
    process_document,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CHUNK_OVERLAP,
)

router = APIRouter()



@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload procurement or supplier PDF document",
    description="Uploads a PDF file, validates magic bytes and size, stores file with a UUID storage key, and creates metadata record.",
)
def upload(
    title: str = Form(..., description="Human-readable title of the document"),
    document_type: str = Form(..., description="Controlled document type identifier"),
    supplier_id: Optional[int] = Form(None, description="Linked supplier ID (required for supplier-specific types)"),
    file: UploadFile = File(..., description="PDF file binary upload"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    try:
        doc = create_document(
            db=db,
            title=title,
            document_type=document_type,
            file=file,
            supplier_id=supplier_id,
        )
        from app.services.chroma_service import is_document_indexed
        resp = DocumentResponse.model_validate(doc)
        resp.indexed = is_document_indexed(doc.id)
        return resp
    except DocumentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except DocumentServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "",
    response_model=List[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List documents",
    description="Returns filtered list of documents with supplier metadata.",
)
def list_all(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    supplier_id: Optional[int] = Query(None, description="Filter by supplier ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search term matching title or filename"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[DocumentResponse]:
    return list_documents(
        db=db,
        skip=skip,
        limit=limit,
        document_type=document_type,
        supplier_id=supplier_id,
        is_active=is_active,
        search=search,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document details",
    description="Returns metadata for a specific document by ID.",
)
def get_one(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    try:
        doc = get_document(db=db, document_id=document_id)
        from app.services.chroma_service import is_document_indexed
        resp = DocumentResponse.model_validate(doc)
        resp.indexed = is_document_indexed(doc.id)
        return resp
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update document metadata",
    description="Updates title, document type, supplier association, or active status.",
)
def update(
    document_id: int,
    payload: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    try:
        doc = update_document(db=db, document_id=document_id, payload=payload)
        from app.services.chroma_service import is_document_indexed
        resp = DocumentResponse.model_validate(doc)
        resp.indexed = is_document_indexed(doc.id)
        return resp
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except DocumentValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except DocumentServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/{document_id}/download",
    response_class=FileResponse,
    status_code=status.HTTP_200_OK,
    summary="Download document PDF",
    description="Streams stored PDF file binary with appropriate Content-Disposition and original filename.",
)
def download(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        doc = get_document(db=db, document_id=document_id)
        file_path = get_document_file_path(doc)
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=doc.original_filename,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except DocumentServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Removes document metadata from database and deletes stored PDF file from filesystem.",
)
def remove(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        delete_document(db=db, document_id=document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except DocumentServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/{document_id}/extracted-text",
    response_model=DocumentExtractionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document extracted text by page",
    description="Extracts normalized text page-by-page from stored PDF using PyMuPDF.",
)
def get_extracted_text(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentExtractionResponse:
    try:
        return extract_document_text(db=db, document_id=document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (CorruptedPDFError, EncryptedPDFError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except (DocumentServiceError, DocumentProcessingError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunksListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document deterministic chunks",
    description="Segments extracted document text into deterministic, paragraph-aware chunks.",
)
def get_document_chunks(
    document_id: int,
    chunk_size: int = Query(DEFAULT_CHUNK_SIZE, ge=100, le=5000, description="Target chunk character size"),
    overlap: int = Query(DEFAULT_CHUNK_OVERLAP, ge=0, le=1000, description="Chunk overlap character length"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentChunksListResponse:
    if overlap >= chunk_size:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"overlap ({overlap}) must be strictly less than chunk_size ({chunk_size}).",
        )
    try:
        return process_document(db=db, document_id=document_id, chunk_size=chunk_size, overlap=overlap)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (CorruptedPDFError, EncryptedPDFError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except (DocumentServiceError, DocumentProcessingError) as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

