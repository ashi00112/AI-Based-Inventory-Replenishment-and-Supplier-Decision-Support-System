import logging
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.models.inventory import Inventory
from app.models.inventory_transaction import (
    InventoryTransaction,
    InventoryTransactionType,
)
from app.models.product import Product
from app.models.sales_history import SalesHistory
from app.schemas.inventory_transaction import InventoryTransactionCreate

logger = logging.getLogger(__name__)


class InventoryTransactionError(Exception):
    """Base domain exception for inventory transaction processing failures."""
    pass


class InsufficientStockError(InventoryTransactionError):
    """Raised when a sale or deduction exceeds available unreserved stock."""
    pass


class InvalidTransactionError(InventoryTransactionError):
    """Raised when an operation would violate stock invariants (e.g. negative on-hand)."""
    pass


class ProductNotFoundError(InventoryTransactionError):
    """Raised when the specified product does not exist in catalog."""
    pass


class InventoryNotFoundError(InventoryTransactionError):
    """Raised when no inventory record exists for the product."""
    pass


class InventoryTransactionNotFoundError(InventoryTransactionError):
    """Raised when the requested transaction record does not exist."""
    pass


def process_inventory_transaction(
    db: Session,
    tx_in: InventoryTransactionCreate,
) -> InventoryTransaction:
    """
    Atomically processes an inventory transaction:
    1. Product and inventory are loaded.
    2. Transaction-specific stock rules are validated.
    3. Inventory on_hand is updated.
    4. InventoryTransaction audit record is created.
    5. For SALE transactions only, a SalesHistory record with price snapshot is created.
    6. Inventory update, InventoryTransaction, and when applicable SalesHistory are committed atomically in one database transaction.
    """
    # 1. Load Product
    product = db.get(Product, tx_in.product_id)
    if product is None:
        raise ProductNotFoundError(f"Product with ID {tx_in.product_id} not found.")

    # 2. Load Inventory (with row lock if supported, otherwise standard load)
    inventory = db.scalars(
        select(Inventory).where(Inventory.product_id == tx_in.product_id)
    ).first()

    if inventory is None:
        raise InventoryNotFoundError(
            f"Inventory record for product ID {tx_in.product_id} not found."
        )

    previous_on_hand = inventory.on_hand
    ttype = tx_in.transaction_type
    qty = tx_in.quantity

    # 3. Apply business rules per transaction type
    if ttype == InventoryTransactionType.SALE:
        if qty <= 0:
            raise InvalidTransactionError("Sale quantity must be strictly positive.")

        # Invariant: Sales must not consume reserved stock (available_stock = on_hand - reserved)
        available_stock = inventory.on_hand - inventory.reserved
        if qty > available_stock:
            raise InsufficientStockError(
                f"Insufficient available stock for this sale. "
                f"Requested: {qty}, Available: {available_stock} "
                f"(On Hand: {inventory.on_hand}, Reserved: {inventory.reserved})."
            )
        new_on_hand = previous_on_hand - qty

    elif ttype == InventoryTransactionType.RESTOCK:
        if qty <= 0:
            raise InvalidTransactionError("Restock quantity must be strictly positive.")
        new_on_hand = previous_on_hand + qty

    elif ttype == InventoryTransactionType.RETURN:
        if qty <= 0:
            raise InvalidTransactionError("Return quantity must be strictly positive.")
        new_on_hand = previous_on_hand + qty

    elif ttype == InventoryTransactionType.ADJUSTMENT:
        if qty == 0:
            raise InvalidTransactionError("Adjustment quantity cannot be zero.")
        new_on_hand = previous_on_hand + qty

        if new_on_hand < 0:
            raise InvalidTransactionError(
                f"Adjustment of {qty} would result in negative on-hand stock ({new_on_hand})."
            )
        if new_on_hand < inventory.reserved:
            raise InvalidTransactionError(
                f"Adjustment of {qty} would reduce on-hand stock ({new_on_hand}) below reserved stock ({inventory.reserved})."
            )
    else:
        raise InvalidTransactionError(f"Unsupported transaction type: {ttype}")

    # 4. Mutate inventory on_hand
    inventory.on_hand = new_on_hand

    # 5. Create immutable transaction record
    tx_record = InventoryTransaction(
        product_id=tx_in.product_id,
        transaction_type=ttype,
        quantity=qty,
        previous_on_hand=previous_on_hand,
        new_on_hand=new_on_hand,
        note=tx_in.note.strip() if tx_in.note else None,
    )
    db.add(tx_record)

    # 6. For SALE transactions, record historical sales entry
    if ttype == InventoryTransactionType.SALE:
        unit_price = (
            product.unit_price
            if isinstance(product.unit_price, Decimal)
            else Decimal(str(product.unit_price))
        )
        total_amount = Decimal(qty) * unit_price
        sales_record = SalesHistory(
            product_id=product.id,
            transaction=tx_record,
            quantity=qty,
            unit_price=unit_price,
            total_amount=total_amount,
        )
        db.add(sales_record)

    # 7. Commit atomically
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "Integrity violation processing transaction for product %d: %s",
            tx_in.product_id,
            exc,
        )
        raise InvalidTransactionError(
            "Database constraint violation recording inventory transaction."
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error(
            "Database failure processing transaction for product %d: %s",
            tx_in.product_id,
            type(exc).__name__,
        )
        raise InventoryTransactionError(
            "An internal database error occurred while processing inventory transaction."
        ) from exc

    db.refresh(tx_record)
    return tx_record


def list_inventory_transactions(
    db: Session,
    product_id: Optional[int] = None,
    transaction_type: Optional[InventoryTransactionType] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[InventoryTransaction]:
    """
    Retrieves transaction history ordered chronologically (most recent first).
    Supports filtering by product_id and transaction_type.
    Eagerly loads product to avoid N+1 queries.
    """
    try:
        query = (
            select(InventoryTransaction)
            .options(joinedload(InventoryTransaction.product))
            .order_by(InventoryTransaction.id.desc())
        )

        if product_id is not None:
            query = query.where(InventoryTransaction.product_id == product_id)

        if transaction_type is not None:
            query = query.where(InventoryTransaction.transaction_type == transaction_type)

        query = query.offset(skip).limit(limit)
        return list(db.scalars(query).all())
    except SQLAlchemyError as exc:
        logger.error("Database failure listing transactions: %s", type(exc).__name__)
        raise InventoryTransactionError(
            "An internal database error occurred while fetching transactions."
        ) from exc


def get_inventory_transaction(
    db: Session,
    transaction_id: int,
) -> InventoryTransaction:
    """
    Retrieves a single historical transaction record by ID.
    Raises InventoryTransactionNotFoundError if nonexistent.
    """
    try:
        tx = db.scalars(
            select(InventoryTransaction)
            .options(joinedload(InventoryTransaction.product))
            .where(InventoryTransaction.id == transaction_id)
        ).first()
    except SQLAlchemyError as exc:
        logger.error(
            "Database failure fetching transaction %d: %s",
            transaction_id,
            type(exc).__name__,
        )
        raise InventoryTransactionError(
            "An internal database error occurred while retrieving transaction."
        ) from exc

    if tx is None:
        raise InventoryTransactionNotFoundError(
            f"Inventory transaction with ID {transaction_id} not found."
        )

    return tx
