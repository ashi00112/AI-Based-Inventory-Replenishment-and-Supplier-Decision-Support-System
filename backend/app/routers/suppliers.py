from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.supplier import (
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
from app.services.supplier_service import (
    SupplierAlreadyExistsError,
    SupplierNotFoundError,
    SupplierServiceError,
    create_supplier,
    delete_supplier,
    get_supplier,
    list_suppliers,
    update_supplier,
)

router = APIRouter()


@router.post(
    "",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new supplier",
    description="Registers a new merchandise vendor with a unique supplier_code, contact details, and active status.",
)
def create(
    supplier_in: SupplierCreate,
    db: Session = Depends(get_db),
) -> SupplierResponse:
    try:
        return create_supplier(db=db, supplier_in=supplier_in)
    except SupplierAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except SupplierServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "",
    response_model=List[SupplierResponse],
    status_code=status.HTTP_200_OK,
    summary="List suppliers",
    description="Returns a paginated list of suppliers, with optional filters for active status and text search.",
)
def list_all(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search query across code, name, or contact"),
    db: Session = Depends(get_db),
) -> List[SupplierResponse]:
    try:
        return list_suppliers(
            db=db,
            skip=skip,
            limit=limit,
            is_active=is_active,
            search=search,
        )
    except SupplierServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Get supplier by ID",
    description="Retrieves complete profile details for a single supplier.",
)
def get_by_id(
    supplier_id: int,
    db: Session = Depends(get_db),
) -> SupplierResponse:
    try:
        return get_supplier(db=db, supplier_id=supplier_id)
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except SupplierServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.patch(
    "/{supplier_id}",
    response_model=SupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Update supplier details",
    description="Partially updates an existing supplier. Guarantees supplier_code uniqueness if updated.",
)
def update(
    supplier_id: int,
    supplier_update: SupplierUpdate,
    db: Session = Depends(get_db),
) -> SupplierResponse:
    try:
        return update_supplier(
            db=db,
            supplier_id=supplier_id,
            supplier_update=supplier_update,
        )
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except SupplierAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except SupplierServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.delete(
    "/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete supplier",
    description="Deletes a supplier record by ID. Automatically cascades dependent commercial offers.",
)
def delete(
    supplier_id: int,
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_supplier(db=db, supplier_id=supplier_id)
    except SupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except SupplierServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
