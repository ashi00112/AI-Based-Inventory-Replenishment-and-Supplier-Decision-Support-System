from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.inventory import Inventory
from app.models.inventory_transaction import (
    InventoryTransaction,
    InventoryTransactionType,
)
from app.models.product import Product
from app.models.sales_history import SalesHistory
from app.schemas.inventory_transaction import InventoryTransactionCreate
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.inventory_transaction_service import (
    InsufficientStockError,
    process_inventory_transaction,
)
from app.services.product_service import create_product, update_product


@pytest.fixture(scope="function")
def test_db_session():
    """
    Isolated in-memory SQLite database using StaticPool.
    Ensures zero interaction with any cloud Supabase database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    db = TestingSessionLocal()
    try:
        yield db, TestingSessionLocal
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db_session):
    """
    FastAPI TestClient with get_db overridden to use isolated in-memory DB.
    """
    _, TestingSessionLocal = test_db_session

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestSalesHistory:
    """Comprehensive test suite for SalesHistory creation, snapshot preservation, and atomicity."""

    def _setup_product_and_inventory(
        self,
        db: Session,
        sku: str = "TEST-SKU-1",
        unit_price: Decimal = Decimal("45.50"),
        on_hand: int = 100,
        reserved: int = 10,
    ) -> Product:
        product = create_product(
            db,
            ProductCreate(
                sku=sku,
                name=f"Product {sku}",
                unit_price=unit_price,
                reorder_point=5,
            ),
        )
        inv = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).first()
        inv.on_hand = on_hand
        inv.reserved = reserved
        db.commit()
        db.refresh(product)
        return product

    def test_successful_sale_creates_exactly_one_sales_history_record(self, test_db_session):
        """1. Successful SALE creates exactly one SalesHistory record with accurate snapshot fields."""
        db, _ = test_db_session
        product = self._setup_product_and_inventory(
            db, sku="SH-SALE-1", unit_price=Decimal("45.50"), on_hand=100, reserved=10
        )

        tx = process_inventory_transaction(
            db,
            InventoryTransactionCreate(
                product_id=product.id,
                transaction_type=InventoryTransactionType.SALE,
                quantity=15,
                note="Order #1001",
            ),
        )

        sales = db.scalars(select(SalesHistory).where(SalesHistory.product_id == product.id)).all()
        assert len(sales) == 1
        record = sales[0]

        assert record.product_id == product.id
        assert record.transaction_id == tx.id
        assert record.quantity == 15
        assert record.unit_price == Decimal("45.50")
        assert record.total_amount == Decimal("682.50")
        assert record.sale_date is not None

    def test_successful_sale_decreases_inventory_on_hand(self, test_db_session):
        """2. Successful SALE decreases inventory.on_hand correctly while recording SalesHistory."""
        db, _ = test_db_session
        product = self._setup_product_and_inventory(
            db, sku="SH-SALE-2", unit_price=Decimal("25.00"), on_hand=100, reserved=20
        )

        process_inventory_transaction(
            db,
            InventoryTransactionCreate(
                product_id=product.id,
                transaction_type=InventoryTransactionType.SALE,
                quantity=30,
            ),
        )

        inv = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).first()
        db.refresh(inv)
        assert inv.on_hand == 70
        assert inv.reserved == 20
        assert inv.available_stock == 50

        sales = db.scalars(select(SalesHistory).where(SalesHistory.product_id == product.id)).all()
        assert len(sales) == 1
        assert sales[0].quantity == 30
        assert sales[0].total_amount == Decimal("750.00")

    def test_restock_does_not_create_sales_history(self, test_db_session):
        """3. RESTOCK increases inventory but does NOT create SalesHistory records."""
        db, _ = test_db_session
        product = self._setup_product_and_inventory(
            db, sku="SH-RESTOCK", unit_price=Decimal("50.00"), on_hand=50, reserved=0
        )

        process_inventory_transaction(
            db,
            InventoryTransactionCreate(
                product_id=product.id,
                transaction_type=InventoryTransactionType.RESTOCK,
                quantity=40,
                note="Supplier restock",
            ),
        )

        sales = db.scalars(select(SalesHistory).where(SalesHistory.product_id == product.id)).all()
        assert len(sales) == 0

        inv = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).first()
        db.refresh(inv)
        assert inv.on_hand == 90

    def test_return_does_not_create_sales_history(self, test_db_session):
        """4. RETURN increases inventory but does NOT create SalesHistory records."""
        db, _ = test_db_session
        product = self._setup_product_and_inventory(
            db, sku="SH-RETURN", unit_price=Decimal("30.00"), on_hand=50, reserved=0
        )

        process_inventory_transaction(
            db,
            InventoryTransactionCreate(
                product_id=product.id,
                transaction_type=InventoryTransactionType.RETURN,
                quantity=5,
                note="Customer return",
            ),
        )

        sales = db.scalars(select(SalesHistory).where(SalesHistory.product_id == product.id)).all()
        assert len(sales) == 0

        inv = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).first()
        db.refresh(inv)
        assert inv.on_hand == 55

    def test_adjustment_does_not_create_sales_history(self, test_db_session):
        """5. ADJUSTMENT (both positive and negative) does NOT create SalesHistory records."""
        db, _ = test_db_session
        product = self._setup_product_and_inventory(
            db, sku="SH-ADJUST", unit_price=Decimal("15.00"), on_hand=50, reserved=10
        )

        # Positive adjustment
        process_inventory_transaction(
            db,
            InventoryTransactionCreate(
                product_id=product.id,
                transaction_type=InventoryTransactionType.ADJUSTMENT,
                quantity=10,
                note="Found extra stock",
            ),
        )

        # Negative adjustment
        process_inventory_transaction(
            db,
            InventoryTransactionCreate(
                product_id=product.id,
                transaction_type=InventoryTransactionType.ADJUSTMENT,
                quantity=-5,
                note="Damaged item",
            ),
        )

        sales = db.scalars(select(SalesHistory).where(SalesHistory.product_id == product.id)).all()
        assert len(sales) == 0

        inv = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).first()
        db.refresh(inv)
        assert inv.on_hand == 55

    def test_failed_sale_creates_no_sales_history_or_transaction(self, test_db_session):
        """6. Failed SALE due to insufficient available stock leaves inventory, transactions, and sales history clean."""
        db, _ = test_db_session
        product = self._setup_product_and_inventory(
            db, sku="SH-FAIL", unit_price=Decimal("100.00"), on_hand=50, reserved=40
        )
        # Available stock is 50 - 40 = 10. Attempting to sell 15 must fail.

        with pytest.raises(InsufficientStockError):
            process_inventory_transaction(
                db,
                InventoryTransactionCreate(
                    product_id=product.id,
                    transaction_type=InventoryTransactionType.SALE,
                    quantity=15,
                ),
            )

        sales = db.scalars(select(SalesHistory).where(SalesHistory.product_id == product.id)).all()
        assert len(sales) == 0

        txs = db.scalars(select(InventoryTransaction).where(InventoryTransaction.product_id == product.id)).all()
        assert len(txs) == 0

        inv = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).first()
        db.refresh(inv)
        assert inv.on_hand == 50
        assert inv.reserved == 40

    def test_price_snapshot_preserved_after_product_price_update(self, test_db_session):
        """7. Price snapshot in SalesHistory remains immutable after updating Product.unit_price."""
        db, _ = test_db_session
        product = self._setup_product_and_inventory(
            db, sku="SH-SNAPSHOT", unit_price=Decimal("20.00"), on_hand=100, reserved=0
        )

        # Perform sale of 4 units @ 20.00
        process_inventory_transaction(
            db,
            InventoryTransactionCreate(
                product_id=product.id,
                transaction_type=InventoryTransactionType.SALE,
                quantity=4,
            ),
        )

        # Change product catalog unit_price to 35.00
        update_product(
            db,
            product.id,
            ProductUpdate(unit_price=Decimal("35.00")),
        )
        db.refresh(product)
        assert product.unit_price == Decimal("35.00")

        # Verify historical record still reflects the original snapshot (20.00 and 80.00)
        sales = db.scalars(select(SalesHistory).where(SalesHistory.product_id == product.id)).all()
        assert len(sales) == 1
        historical_record = sales[0]

        assert historical_record.unit_price == Decimal("20.00")
        assert historical_record.total_amount == Decimal("80.00")
        assert historical_record.quantity == 4
