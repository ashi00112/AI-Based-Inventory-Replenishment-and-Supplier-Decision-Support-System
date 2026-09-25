import logging
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.models.inventory import Inventory
from app.models.product import Product
from app.schemas.inventory import InventoryUpdate

logger = logging.getLogger(__name__)


class InventoryNotFoundError(Exception):
    """Raised when inventory for the specified product does not exist."""
    pass


class InvalidInventoryStateError(Exception):
    """Raised when an inventory operation violates stock business invariants (e.g. reserved > on_hand)."""
    pass


class InventoryServiceError(Exception):
    """Raised when an unexpected database error occurs during inventory operations."""
    pass


def get_inventory_by_product(db: Session, product_id: int) -> Inventory:
    """
    Retrieves the inventory record for a specific product ID.
    Eagerly loads the associated product.
    Raises InventoryNotFoundError if nonexistent.
    """
    try:
        inventory = db.scalars(
            select(Inventory)
            .options(joinedload(Inventory.product))
            .where(Inventory.product_id == product_id)
        ).first()
    except SQLAlchemyError as exc:
        logger.error("Database failure fetching inventory for product %d: %s", product_id, type(exc).__name__)
        raise InventoryServiceError("An internal database error occurred while fetching inventory.") from exc

    if inventory is None:
        raise InventoryNotFoundError(f"Inventory record for product ID {product_id} not found.")

    return inventory


def list_inventory(
    db: Session,
    skip: int = 0,
    limit: int = 100,
) -> List[Inventory]:
    """
    Retrieves a paginated list of inventory records with their products eagerly loaded.
    Prevents N+1 queries.
    """
    try:
        query = (
            select(Inventory)
            .options(joinedload(Inventory.product))
            .order_by(Inventory.product_id.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(query).all())
    except SQLAlchemyError as exc:
        logger.error("Database failure listing inventory: %s", type(exc).__name__)
        raise InventoryServiceError("An internal database error occurred while fetching inventory list.") from exc


def update_inventory(
    db: Session,
    product_id: int,
    inventory_update: InventoryUpdate,
) -> Inventory:
    """
    Safely modifies stock values on an existing inventory record.
    Enforces the following invariants:
    - on_hand >= 0
    - reserved >= 0
    - incoming >= 0
    - reserved <= on_hand (available_stock >= 0)
    """
    # Fetch existing inventory with lock if desired, or standard fetch
    inventory = get_inventory_by_product(db, product_id)

    # Determine prospective merged values
    new_on_hand = (
        inventory_update.on_hand
        if inventory_update.on_hand is not None
        else inventory.on_hand
    )
    new_reserved = (
        inventory_update.reserved
        if inventory_update.reserved is not None
        else inventory.reserved
    )
    new_incoming = (
        inventory_update.incoming
        if inventory_update.incoming is not None
        else inventory.incoming
    )

    # Invariant validation
    if new_on_hand < 0 or new_reserved < 0 or new_incoming < 0:
        raise InvalidInventoryStateError("Stock quantities cannot be negative.")

    if new_reserved > new_on_hand:
        raise InvalidInventoryStateError(
            f"Reserved stock ({new_reserved}) cannot exceed on-hand stock ({new_on_hand})."
        )

    # Apply changes
    inventory.on_hand = new_on_hand
    inventory.reserved = new_reserved
    inventory.incoming = new_incoming

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Integrity constraint violation updating inventory for product %d: %s", product_id, exc)
        raise InvalidInventoryStateError("Database constraint violation: invalid stock quantities.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure updating inventory for product %d: %s", product_id, type(exc).__name__)
        raise InventoryServiceError("An internal database error occurred while updating inventory.") from exc

    db.refresh(inventory)
    return inventory


def initialize_inventory_for_product(
    db: Session,
    product_id: int,
    on_hand: int = 0,
    reserved: int = 0,
    incoming: int = 0,
    auto_commit: bool = True,
) -> Inventory:
    """
    Initializes an inventory record for a product.
    If auto_commit is False, leaves commit to the calling transaction.
    """
    if reserved > on_hand:
        raise InvalidInventoryStateError("Reserved stock cannot exceed on-hand stock.")

    new_inventory = Inventory(
        product_id=product_id,
        on_hand=on_hand,
        reserved=reserved,
        incoming=incoming,
    )
    db.add(new_inventory)

    if auto_commit:
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise InvalidInventoryStateError(f"Inventory already exists for product ID {product_id}.") from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise InventoryServiceError("An internal database error occurred while initializing inventory.") from exc

        db.refresh(new_inventory)

    return new_inventory
