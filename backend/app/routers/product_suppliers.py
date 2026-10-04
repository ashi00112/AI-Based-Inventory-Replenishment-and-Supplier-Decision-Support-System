from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.product_supplier import (
    ProductSupplierCreate,
    ProductSupplierResponse,
    ProductSupplierUpdate,
)
from app.services.product_service import ProductNotFoundError
from app.services.product_supplier_service import (
    ProductSupplierAlreadyExistsError,
    ProductSupplierNotFoundError,
    ProductSupplierServiceError,
    ProductSupplierValidationError,
    create_product_supplier,
    delete_product_supplier,
    get_product_supplier,
    list_product_suppliers,
    update_product_supplier,
)
from app.dependencies.auth import require_catalog_access
from app.services.supplier_service import SupplierNotFoundError

router = APIRouter(dependencies=[Depends(require_catalog_access)])


@router.post(
    "",
    response_model=ProductSupplierResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create product-supplier commercial offer",
    description="Registers an active commercial supply offer for a product with unit cost, MOQ, and lead time.",
)
def create(
    offer_in: ProductSupplierCreate,
    db: Session = Depends(get_db),
) -> ProductSupplierResponse:
    try:
        return create_product_supplier(db=db, offer_in=offer_in)
    except (ProductNotFoundError, SupplierNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ProductSupplierAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except ProductSupplierValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except ProductSupplierServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "",
    response_model=List[ProductSupplierResponse],
    status_code=status.HTTP_200_OK,
    summary="List product-supplier offers",
    description="Returns a paginated list of commercial offers. Supports filtering by product_id, supplier_id, and is_active.",
)
def list_all(
    product_id: Optional[int] = Query(None, description="Filter offers by product ID"),
    supplier_id: Optional[int] = Query(None, description="Filter offers by supplier ID"),
    is_active: Optional[bool] = Query(None, description="Filter offers by active status"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    db: Session = Depends(get_db),
) -> List[ProductSupplierResponse]:
    try:
        return list_product_suppliers(
            db=db,
            product_id=product_id,
            supplier_id=supplier_id,
            is_active=is_active,
            skip=skip,
            limit=limit,
        )
    except ProductSupplierServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/{offer_id}",
    response_model=ProductSupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product-supplier offer by ID",
    description="Retrieves complete commercial details for a specific product-supplier relationship.",
)
def get_by_id(
    offer_id: int,
    db: Session = Depends(get_db),
) -> ProductSupplierResponse:
    try:
        return get_product_supplier(db=db, offer_id=offer_id)
    except ProductSupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ProductSupplierServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.patch(
    "/{offer_id}",
    response_model=ProductSupplierResponse,
    status_code=status.HTTP_200_OK,
    summary="Update product-supplier offer",
    description="Partially updates commercial terms (unit_cost, moq, lead_time_days, supplier_sku, is_active).",
)
def update(
    offer_id: int,
    offer_update: ProductSupplierUpdate,
    db: Session = Depends(get_db),
) -> ProductSupplierResponse:
    try:
        return update_product_supplier(
            db=db,
            offer_id=offer_id,
            offer_update=offer_update,
        )
    except ProductSupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ProductSupplierValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except ProductSupplierServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.delete(
    "/{offer_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete product-supplier offer",
    description="Removes a commercial link between a product and supplier. Does not delete product or supplier.",
)
def delete(
    offer_id: int,
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_product_supplier(db=db, offer_id=offer_id)
    except ProductSupplierNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ProductSupplierServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
