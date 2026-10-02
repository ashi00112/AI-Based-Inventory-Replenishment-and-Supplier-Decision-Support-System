import logging
from typing import List, Optional
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierUpdate

logger = logging.getLogger(__name__)


class SupplierError(Exception):
    """Base domain exception for supplier management failures."""
    pass


class SupplierNotFoundError(SupplierError):
    """Raised when a supplier with the requested ID or code does not exist."""
    pass


class SupplierAlreadyExistsError(SupplierError):
    """Raised when attempting to create or update a supplier with an existing supplier_code."""
    pass


class SupplierServiceError(SupplierError):
    """Raised when an unexpected database error occurs during supplier operations."""
    pass


def create_supplier(db: Session, supplier_in: SupplierCreate) -> Supplier:
    """
    Creates a new supplier record in the database.
    Enforces supplier_code uniqueness before and during database insert.
    """
    normalized_code = supplier_in.supplier_code.strip().upper()

    # Pre-check for duplicate code
    existing = db.scalars(
        select(Supplier).where(Supplier.supplier_code == normalized_code)
    ).first()
    if existing is not None:
        raise SupplierAlreadyExistsError(
            f"A supplier with code '{normalized_code}' already exists."
        )

    new_supplier = Supplier(
        supplier_code=normalized_code,
        name=supplier_in.name.strip(),
        contact_name=supplier_in.contact_name.strip() if supplier_in.contact_name else None,
        email=str(supplier_in.email) if supplier_in.email else None,
        phone=supplier_in.phone.strip() if supplier_in.phone else None,
        address=supplier_in.address.strip() if supplier_in.address else None,
        is_active=supplier_in.is_active,
    )

    db.add(new_supplier)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Integrity conflict creating supplier code '%s': %s", normalized_code, exc)
        raise SupplierAlreadyExistsError(
            f"A supplier with code '{normalized_code}' already exists."
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure creating supplier: %s", type(exc).__name__)
        raise SupplierServiceError("An internal database error occurred while creating supplier.") from exc

    db.refresh(new_supplier)
    return new_supplier


def get_supplier(db: Session, supplier_id: int) -> Supplier:
    """
    Retrieves a single supplier by integer ID.
    Raises SupplierNotFoundError if nonexistent.
    """
    try:
        supplier = db.get(Supplier, supplier_id)
    except SQLAlchemyError as exc:
        logger.error("Database failure getting supplier %d: %s", supplier_id, type(exc).__name__)
        raise SupplierServiceError("An internal database error occurred while retrieving supplier.") from exc

    if supplier is None:
        raise SupplierNotFoundError(f"Supplier with ID {supplier_id} not found.")
    return supplier


def get_supplier_by_code(db: Session, supplier_code: str) -> Supplier:
    """
    Retrieves a single supplier by code (case-insensitive search).
    Raises SupplierNotFoundError if nonexistent.
    """
    normalized_code = supplier_code.strip().upper()
    try:
        supplier = db.scalars(
            select(Supplier).where(Supplier.supplier_code == normalized_code)
        ).first()
    except SQLAlchemyError as exc:
        logger.error("Database failure getting supplier '%s': %s", normalized_code, type(exc).__name__)
        raise SupplierServiceError("An internal database error occurred while retrieving supplier.") from exc

    if supplier is None:
        raise SupplierNotFoundError(f"Supplier with code '{normalized_code}' not found.")
    return supplier


def list_suppliers(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
) -> List[Supplier]:
    """
    Retrieves a paginated list of suppliers ordered by ID.
    Supports filtering by is_active status and text search on code, name, or contact.
    """
    try:
        query = select(Supplier)

        if is_active is not None:
            query = query.where(Supplier.is_active == is_active)

        if search:
            search_pattern = f"%{search.strip()}%"
            query = query.where(
                or_(
                    Supplier.name.ilike(search_pattern),
                    Supplier.supplier_code.ilike(search_pattern),
                    Supplier.contact_name.ilike(search_pattern),
                )
            )

        query = query.order_by(Supplier.id.asc()).offset(skip).limit(limit)
        return list(db.scalars(query).all())
    except SQLAlchemyError as exc:
        logger.error("Database failure listing suppliers: %s", type(exc).__name__)
        raise SupplierServiceError("An internal database error occurred while fetching suppliers.") from exc


def update_supplier(
    db: Session,
    supplier_id: int,
    supplier_update: SupplierUpdate,
) -> Supplier:
    """
    Applies partial updates to an existing supplier.
    Guarantees supplier_code uniqueness across other suppliers.
    """
    supplier = get_supplier(db, supplier_id)
    update_data = supplier_update.model_dump(exclude_unset=True)

    # Check for code conflict if supplier_code is being modified
    if "supplier_code" in update_data and update_data["supplier_code"] is not None:
        new_code = update_data["supplier_code"].strip().upper()
        if new_code != supplier.supplier_code:
            existing = db.scalars(
                select(Supplier).where(Supplier.supplier_code == new_code, Supplier.id != supplier_id)
            ).first()
            if existing is not None:
                raise SupplierAlreadyExistsError(f"A supplier with code '{new_code}' already exists.")
            update_data["supplier_code"] = new_code

    if "name" in update_data and update_data["name"] is not None:
        update_data["name"] = update_data["name"].strip()

    if "contact_name" in update_data and update_data["contact_name"] is not None:
        update_data["contact_name"] = update_data["contact_name"].strip() or None

    if "email" in update_data and update_data["email"] is not None:
        update_data["email"] = str(update_data["email"]).strip()

    if "phone" in update_data and update_data["phone"] is not None:
        update_data["phone"] = update_data["phone"].strip() or None

    if "address" in update_data and update_data["address"] is not None:
        update_data["address"] = update_data["address"].strip() or None

    for field, value in update_data.items():
        setattr(supplier, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SupplierAlreadyExistsError("A supplier with this code already exists.") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure updating supplier %d: %s", supplier_id, type(exc).__name__)
        raise SupplierServiceError("An internal database error occurred while updating supplier.") from exc

    db.refresh(supplier)
    return supplier


def delete_supplier(db: Session, supplier_id: int) -> None:
    """
    Deletes a supplier by ID.
    Dependent ProductSupplier records are automatically cascaded.
    """
    supplier = get_supplier(db, supplier_id)
    db.delete(supplier)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Database failure deleting supplier %d: %s", supplier_id, type(exc).__name__)
        raise SupplierServiceError("An internal database error occurred while deleting supplier.") from exc
