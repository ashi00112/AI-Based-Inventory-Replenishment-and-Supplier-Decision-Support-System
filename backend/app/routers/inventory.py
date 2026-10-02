from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agents.inventory import InventoryMonitoringAgent
from app.database.session import get_db
from app.schemas.inventory import (
    InventoryMonitoringItem,
    InventoryMonitoringReport,
    InventoryResponse,
    InventoryUpdate,
)
from app.services.inventory_service import (
    InventoryNotFoundError,
    InvalidInventoryStateError,
    InventoryServiceError,
    get_inventory_by_product,
    list_inventory,
    update_inventory,
)

router = APIRouter()
monitoring_agent = InventoryMonitoringAgent()


@router.get(
    "",
    response_model=List[InventoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List all inventory records",
    description="Returns a paginated list of product stock levels with embedded product metadata.",
)
def list_all_inventory(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    db: Session = Depends(get_db),
) -> List[InventoryResponse]:
    try:
        return list_inventory(db=db, skip=skip, limit=limit)
    except InventoryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/monitor",
    response_model=InventoryMonitoringReport,
    status_code=status.HTTP_200_OK,
    summary="Monitor full inventory collection",
    description="Evaluates all catalog products for stock health (OUT_OF_STOCK, LOW_STOCK, HEALTHY) using InventoryMonitoringAgent.",
)
def monitor_all_inventory(
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    db: Session = Depends(get_db),
) -> InventoryMonitoringReport:
    try:
        return monitoring_agent.monitor_inventory(db=db, skip=skip, limit=limit)
    except InventoryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/monitor/{product_id}",
    response_model=InventoryMonitoringItem,
    status_code=status.HTTP_200_OK,
    summary="Monitor inventory status for a single product",
    description="Evaluates stock health (OUT_OF_STOCK, LOW_STOCK, HEALTHY) for a single product using InventoryMonitoringAgent.",
)
def monitor_product_by_id(
    product_id: int,
    db: Session = Depends(get_db),
) -> InventoryMonitoringItem:
    try:
        return monitoring_agent.monitor_product(db=db, product_id=product_id)
    except InventoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except InventoryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/products/{product_id}",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get inventory by product ID",
    description="Returns current stock levels (on-hand, reserved, incoming, available) for a product.",
)
def get_by_product_id(
    product_id: int,
    db: Session = Depends(get_db),
) -> InventoryResponse:
    try:
        return get_inventory_by_product(db=db, product_id=product_id)
    except InventoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except InventoryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.patch(
    "/products/{product_id}",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update inventory stock for product",
    description="Updates on-hand, reserved, and/or incoming quantities. Enforces non-negative values and reserved <= on_hand.",
)
def patch_inventory(
    product_id: int,
    inventory_in: InventoryUpdate,
    db: Session = Depends(get_db),
) -> InventoryResponse:
    try:
        return update_inventory(
            db=db,
            product_id=product_id,
            inventory_update=inventory_in,
        )
    except InventoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except InvalidInventoryStateError as exc:
        # 422 Unprocessable Entity for business invariant violation
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except InventoryServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
