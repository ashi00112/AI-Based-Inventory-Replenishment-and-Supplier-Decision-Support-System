from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import require_catalog_access
from app.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from app.services.product_service import (
    ProductAlreadyExistsError,
    ProductNotFoundError,
    ProductServiceError,
    create_product,
    delete_product,
    get_product,
    list_products,
    update_product,
)

router = APIRouter(dependencies=[Depends(require_catalog_access)])


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product",
    description="Adds a new product to the catalog with unique SKU, pricing, and reorder point.",
)
def create(
    product_in: ProductCreate,
    db: Session = Depends(get_db),
) -> ProductResponse:
    try:
        return create_product(db=db, product_in=product_in)
    except ProductAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except ProductServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "",
    response_model=List[ProductResponse],
    status_code=status.HTTP_200_OK,
    summary="List products",
    description="Returns a paginated list of catalog products, optionally filtered by is_active.",
)
def list_all(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: Session = Depends(get_db),
) -> List[ProductResponse]:
    return list_products(db=db, skip=skip, limit=limit, is_active=is_active)


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product by ID",
    description="Returns full catalog details for a single product.",
)
def get_by_id(
    product_id: int,
    db: Session = Depends(get_db),
) -> ProductResponse:
    try:
        return get_product(db=db, product_id=product_id)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )


@router.patch(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Update product details",
    description="Partially updates an existing product. Ensures SKU uniqueness across other products.",
)
def update(
    product_id: int,
    product_update: ProductUpdate,
    db: Session = Depends(get_db),
) -> ProductResponse:
    try:
        return update_product(db=db, product_id=product_id, product_update=product_update)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ProductAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )
    except ProductServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete product",
    description="Deletes a product from the catalog by its ID.",
)
def delete(
    product_id: int,
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_product(db=db, product_id=product_id)
    except ProductNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except ProductServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
