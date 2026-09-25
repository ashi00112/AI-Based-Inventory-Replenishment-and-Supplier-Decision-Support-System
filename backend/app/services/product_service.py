import logging
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate

logger = logging.getLogger(__name__)


class ProductNotFoundError(Exception):
    """Raised when a product with the requested ID does not exist."""
    pass


class ProductAlreadyExistsError(Exception):
    """Raised when attempting to create or update a product with an existing SKU."""
    pass


class ProductServiceError(Exception):
    """Raised when an unexpected database error occurs during product operations."""
    pass


def create_product(db: Session, product_in: ProductCreate) -> Product:
    """
    Creates a new product record in the database.
    Enforces SKU uniqueness before and during database insert.
    Atomically initializes an associated inventory record with 0 stock.
    """
    normalized_sku = product_in.sku.strip()

    # Pre-check for duplicate SKU
    existing = db.scalars(
        select(Product).where(Product.sku == normalized_sku)
    ).first()
    if existing is not None:
        raise ProductAlreadyExistsError(f"A product with SKU '{normalized_sku}' already exists.")

    new_product = Product(
        sku=normalized_sku,
        name=product_in.name.strip(),
        category=product_in.category,
        description=product_in.description,
        unit_price=product_in.unit_price,
        reorder_point=product_in.reorder_point,
        is_active=True,
        inventory=Inventory(on_hand=0, reserved=0, incoming=0),
    )

    db.add(new_product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Integrity conflict creating product SKU '%s'", normalized_sku)
        raise ProductAlreadyExistsError(f"A product with SKU '{normalized_sku}' already exists.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure creating product: %s", type(exc).__name__)
        raise ProductServiceError("An internal database error occurred while creating product.") from exc

    db.refresh(new_product)
    return new_product


def get_product(db: Session, product_id: int) -> Product:
    """
    Retrieves a single product by its integer ID.
    Raises ProductNotFoundError if nonexistent.
    """
    try:
        product = db.get(Product, product_id)
    except SQLAlchemyError as exc:
        logger.error("Database failure getting product %d: %s", product_id, type(exc).__name__)
        raise ProductServiceError("An internal database error occurred while retrieving product.") from exc

    if product is None:
        raise ProductNotFoundError(f"Product with ID {product_id} not found.")
    return product


def list_products(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
) -> List[Product]:
    """
    Retrieves a paginated list of products ordered by ID.
    Optionally filters by is_active status.
    """
    try:
        query = select(Product)
        if is_active is not None:
            query = query.where(Product.is_active == is_active)
        query = query.order_by(Product.id.asc()).offset(skip).limit(limit)

        return list(db.scalars(query).all())
    except SQLAlchemyError as exc:
        logger.error("Database failure listing products: %s", type(exc).__name__)
        raise ProductServiceError("An internal database error occurred while fetching products.") from exc



def update_product(
    db: Session,
    product_id: int,
    product_update: ProductUpdate,
) -> Product:
    """
    Applies partial updates to an existing product.
    Guarantees SKU uniqueness across products when changing SKU.
    """
    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError(f"Product with ID {product_id} not found.")

    update_data = product_update.model_dump(exclude_unset=True)

    # Check for SKU conflict if sku is being updated
    if "sku" in update_data and update_data["sku"] is not None:
        new_sku = update_data["sku"].strip()
        if new_sku != product.sku:
            existing = db.scalars(
                select(Product).where(Product.sku == new_sku, Product.id != product_id)
            ).first()
            if existing is not None:
                raise ProductAlreadyExistsError(f"A product with SKU '{new_sku}' already exists.")
            update_data["sku"] = new_sku

    # Apply updates
    for field, value in update_data.items():
        setattr(product, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ProductAlreadyExistsError(f"A product with this SKU already exists.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure updating product %d: %s", product_id, type(exc).__name__)
        raise ProductServiceError("An internal database error occurred while updating product.") from exc

    db.refresh(product)
    return product


def delete_product(db: Session, product_id: int) -> None:
    """
    Deletes an existing product by its ID.
    Raises ProductNotFoundError if nonexistent.
    """
    product = db.get(Product, product_id)
    if product is None:
        raise ProductNotFoundError(f"Product with ID {product_id} not found.")

    db.delete(product)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure deleting product %d: %s", product_id, type(exc).__name__)
        raise ProductServiceError("An internal database error occurred while deleting product.") from exc
