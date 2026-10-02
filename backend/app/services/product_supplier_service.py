import logging
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier
from app.schemas.product_supplier import (
    ProductSupplierCreate,
    ProductSupplierUpdate,
)
from app.services.product_service import ProductNotFoundError
from app.services.supplier_service import SupplierNotFoundError

logger = logging.getLogger(__name__)


class ProductSupplierError(Exception):
    """Base domain exception for product-supplier management failures."""
    pass


class ProductSupplierNotFoundError(ProductSupplierError):
    """Raised when the specified product-supplier relationship does not exist."""
    pass


class ProductSupplierAlreadyExistsError(ProductSupplierError):
    """Raised when an offer for this product and supplier pair already exists."""
    pass


class ProductSupplierValidationError(ProductSupplierError):
    """Raised when commercial constraints (unit_cost, moq, lead_time_days) are violated."""
    pass


class ProductSupplierServiceError(ProductSupplierError):
    """Raised when an unexpected database error occurs during product-supplier operations."""
    pass


def create_product_supplier(
    db: Session,
    offer_in: ProductSupplierCreate,
) -> ProductSupplier:
    """
    Creates a new commercial offer linking a product to a supplier.
    Enforces existence of both product and supplier, uniqueness of the pair,
    and business invariants on commercial terms.
    """
    # 1. Validate Product exists
    product = db.get(Product, offer_in.product_id)
    if product is None:
        raise ProductNotFoundError(f"Product with ID {offer_in.product_id} not found.")

    # 2. Validate Supplier exists
    supplier = db.get(Supplier, offer_in.supplier_id)
    if supplier is None:
        raise SupplierNotFoundError(f"Supplier with ID {offer_in.supplier_id} not found.")

    # 3. Check for duplicate product-supplier relationship
    existing = db.scalars(
        select(ProductSupplier).where(
            ProductSupplier.product_id == offer_in.product_id,
            ProductSupplier.supplier_id == offer_in.supplier_id,
        )
    ).first()
    if existing is not None:
        raise ProductSupplierAlreadyExistsError(
            f"Supplier '{supplier.supplier_code}' already has an active offer for product '{product.sku}'."
        )

    # 4. Validate commercial invariants
    if offer_in.unit_cost < Decimal("0.00"):
        raise ProductSupplierValidationError("Unit cost cannot be negative.")
    if offer_in.moq < 1:
        raise ProductSupplierValidationError("Minimum order quantity (MOQ) must be at least 1.")
    if offer_in.lead_time_days < 0:
        raise ProductSupplierValidationError("Lead time days cannot be negative.")

    new_offer = ProductSupplier(
        product_id=offer_in.product_id,
        supplier_id=offer_in.supplier_id,
        supplier_sku=offer_in.supplier_sku,
        unit_cost=offer_in.unit_cost,
        moq=offer_in.moq,
        lead_time_days=offer_in.lead_time_days,
        is_active=offer_in.is_active,
    )

    db.add(new_offer)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Integrity error creating product supplier offer: %s", exc)
        raise ProductSupplierAlreadyExistsError(
            "An offer linking this product and supplier already exists."
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure creating product supplier offer: %s", type(exc).__name__)
        raise ProductSupplierServiceError(
            "An internal database error occurred while creating product-supplier offer."
        ) from exc

    # Refresh with eager relationships
    return get_product_supplier(db, new_offer.id)


def get_product_supplier(
    db: Session,
    offer_id: int,
) -> ProductSupplier:
    """
    Retrieves a single product-supplier relationship by ID, eagerly loading product and supplier.
    Raises ProductSupplierNotFoundError if nonexistent.
    """
    try:
        offer = db.scalars(
            select(ProductSupplier)
            .options(
                joinedload(ProductSupplier.product),
                joinedload(ProductSupplier.supplier),
            )
            .where(ProductSupplier.id == offer_id)
        ).first()
    except SQLAlchemyError as exc:
        logger.error("Database failure fetching product supplier %d: %s", offer_id, type(exc).__name__)
        raise ProductSupplierServiceError(
            "An internal database error occurred while retrieving product-supplier offer."
        ) from exc

    if offer is None:
        raise ProductSupplierNotFoundError(f"Product-supplier offer with ID {offer_id} not found.")

    return offer


def list_product_suppliers(
    db: Session,
    product_id: Optional[int] = None,
    supplier_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[ProductSupplier]:
    """
    Retrieves a paginated list of product-supplier offers.
    Supports filtering by product_id, supplier_id, and is_active status.
    Eagerly loads related product and supplier to prevent N+1 queries.
    """
    try:
        query = (
            select(ProductSupplier)
            .options(
                joinedload(ProductSupplier.product),
                joinedload(ProductSupplier.supplier),
            )
            .order_by(ProductSupplier.id.asc())
        )

        if product_id is not None:
            query = query.where(ProductSupplier.product_id == product_id)

        if supplier_id is not None:
            query = query.where(ProductSupplier.supplier_id == supplier_id)

        if is_active is not None:
            query = query.where(ProductSupplier.is_active == is_active)

        query = query.offset(skip).limit(limit)
        return list(db.scalars(query).all())
    except SQLAlchemyError as exc:
        logger.error("Database failure listing product suppliers: %s", type(exc).__name__)
        raise ProductSupplierServiceError(
            "An internal database error occurred while fetching product-supplier offers."
        ) from exc


def update_product_supplier(
    db: Session,
    offer_id: int,
    offer_update: ProductSupplierUpdate,
) -> ProductSupplier:
    """
    Applies partial updates to commercial terms of an existing product-supplier relationship.
    Enforces business invariants on unit_cost, moq, and lead_time_days.
    """
    offer = get_product_supplier(db, offer_id)
    update_data = offer_update.model_dump(exclude_unset=True)

    if "unit_cost" in update_data and update_data["unit_cost"] is not None:
        if update_data["unit_cost"] < Decimal("0.00"):
            raise ProductSupplierValidationError("Unit cost cannot be negative.")

    if "moq" in update_data and update_data["moq"] is not None:
        if update_data["moq"] < 1:
            raise ProductSupplierValidationError("Minimum order quantity (MOQ) must be at least 1.")

    if "lead_time_days" in update_data and update_data["lead_time_days"] is not None:
        if update_data["lead_time_days"] < 0:
            raise ProductSupplierValidationError("Lead time days cannot be negative.")

    for field, value in update_data.items():
        setattr(offer, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ProductSupplierValidationError("Database constraint violation updating offer terms.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure updating product supplier %d: %s", offer_id, type(exc).__name__)
        raise ProductSupplierServiceError(
            "An internal database error occurred while updating product-supplier offer."
        ) from exc

    db.refresh(offer)
    return offer


def delete_product_supplier(
    db: Session,
    offer_id: int,
) -> None:
    """
    Deletes a product-supplier commercial offer.
    Leaves the associated Product and Supplier completely intact.
    """
    offer = get_product_supplier(db, offer_id)
    db.delete(offer)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure deleting product supplier %d: %s", offer_id, type(exc).__name__)
        raise ProductSupplierServiceError(
            "An internal database error occurred while deleting product-supplier offer."
        ) from exc
