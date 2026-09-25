from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.models.inventory_transaction import InventoryTransactionType
from app.schemas.inventory_transaction import (
    InventoryTransactionCreate,
    InventoryTransactionResponse,
)
from app.services.inventory_transaction_service import (
    InsufficientStockError,
    InvalidTransactionError,
    InventoryNotFoundError,
    InventoryTransactionError,
    InventoryTransactionNotFoundError,
    ProductNotFoundError,
    get_inventory_transaction,
    list_inventory_transactions,
    process_inventory_transaction,
)

router = APIRouter()


@router.post(
    "",
    response_model=InventoryTransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an inventory transaction",
    description="Processes an atomic stock movement event (SALE, RESTOCK, RETURN, ADJUSTMENT) and updates on-hand stock.",
)
def create_transaction(
    tx_in: InventoryTransactionCreate,
    db: Session = Depends(get_db),
) -> InventoryTransactionResponse:
    try:
        return process_inventory_transaction(db=db, tx_in=tx_in)
    except (ProductNotFoundError, InventoryNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except (InsufficientStockError, InvalidTransactionError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except InventoryTransactionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "",
    response_model=List[InventoryTransactionResponse],
    status_code=status.HTTP_200_OK,
    summary="List inventory transactions",
    description="Returns chronological transaction history. Supports filtering by product_id and transaction_type.",
)
def list_transactions(
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    transaction_type: Optional[InventoryTransactionType] = Query(None, description="Filter by transaction type"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    db: Session = Depends(get_db),
) -> List[InventoryTransactionResponse]:
    try:
        return list_inventory_transactions(
            db=db,
            product_id=product_id,
            transaction_type=transaction_type,
            skip=skip,
            limit=limit,
        )
    except InventoryTransactionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


@router.get(
    "/{transaction_id}",
    response_model=InventoryTransactionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transaction by ID",
    description="Returns full audit details for a single historical inventory transaction.",
)
def get_transaction_by_id(
    transaction_id: int,
    db: Session = Depends(get_db),
) -> InventoryTransactionResponse:
    try:
        return get_inventory_transaction(db=db, transaction_id=transaction_id)
    except InventoryTransactionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except InventoryTransactionError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
