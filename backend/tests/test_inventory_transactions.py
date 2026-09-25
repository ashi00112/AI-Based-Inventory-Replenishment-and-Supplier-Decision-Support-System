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
from app.schemas.inventory_transaction import InventoryTransactionCreate
from app.services.inventory_transaction_service import (
    InsufficientStockError,
    InvalidTransactionError,
    process_inventory_transaction,
)
from app.services.product_service import create_product
from app.schemas.product import ProductCreate


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


class TestInventoryTransactions:
    """Comprehensive test suite for Inventory Stock Movement Transactions."""

    def _setup_product_with_stock(self, client: TestClient, sku: str, on_hand: int, reserved: int = 0) -> int:
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": sku, "name": f"Product {sku}", "unit_price": 50.0, "reorder_point": 10},
        )
        assert p_resp.status_code == 201
        pid = p_resp.json()["id"]

        if on_hand > 0 or reserved > 0:
            inv_resp = client.patch(
                f"/api/v1/inventory/products/{pid}",
                json={"on_hand": on_hand, "reserved": reserved},
            )
            assert inv_resp.status_code == 200
        return pid

    def test_sale_decreases_on_hand_and_creates_transaction(self, client: TestClient):
        """1 & 2. SALE decreases on_hand and creates an audit transaction record."""
        pid = self._setup_product_with_stock(client, "SALE-1", on_hand=100, reserved=20)

        resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "sale", "quantity": 30, "note": "Order #101"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["product_id"] == pid
        assert data["transaction_type"] == "sale"
        assert data["quantity"] == 30
        assert data["previous_on_hand"] == 100
        assert data["new_on_hand"] == 70
        assert data["note"] == "Order #101"

        # Verify inventory record
        inv = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv["on_hand"] == 70
        assert inv["reserved"] == 20
        assert inv["available_stock"] == 50

    def test_sale_cannot_exceed_available_stock(self, client: TestClient):
        """3. SALE quantity cannot exceed available_stock (on_hand - reserved)."""
        pid = self._setup_product_with_stock(client, "SALE-2", on_hand=100, reserved=30)
        # Available stock is 100 - 30 = 70. Requesting 80 must fail.
        resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "sale", "quantity": 80},
        )
        assert resp.status_code == 422
        assert "Insufficient available stock" in resp.text

        # Inventory must remain intact
        inv = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv["on_hand"] == 100
        assert inv["available_stock"] == 70

    def test_sale_equal_to_available_stock_succeeds(self, client: TestClient):
        """4. SALE exactly equal to available_stock succeeds."""
        pid = self._setup_product_with_stock(client, "SALE-3", on_hand=100, reserved=30)
        # Available stock is 70. Selling exactly 70 leaves on_hand == reserved == 30.
        resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "sale", "quantity": 70},
        )
        assert resp.status_code == 201
        assert resp.json()["new_on_hand"] == 30

        inv = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv["on_hand"] == 30
        assert inv["reserved"] == 30
        assert inv["available_stock"] == 0

    def test_restock_increases_on_hand(self, client: TestClient):
        """5. RESTOCK increases on_hand and records transaction."""
        pid = self._setup_product_with_stock(client, "RESTOCK-1", on_hand=70)

        resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "restock", "quantity": 50, "note": "PO-991"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["previous_on_hand"] == 70
        assert data["new_on_hand"] == 120

        inv = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv["on_hand"] == 120

    def test_return_increases_on_hand(self, client: TestClient):
        """6. RETURN increases on_hand."""
        pid = self._setup_product_with_stock(client, "RET-1", on_hand=120)

        resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "return", "quantity": 5, "note": "Customer RMA"},
        )
        assert resp.status_code == 201
        assert resp.json()["previous_on_hand"] == 120
        assert resp.json()["new_on_hand"] == 125

        inv = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv["on_hand"] == 125

    def test_positive_adjustment_increases_on_hand(self, client: TestClient):
        """7. Positive ADJUSTMENT increases on_hand."""
        pid = self._setup_product_with_stock(client, "ADJ-1", on_hand=100)

        resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "adjustment", "quantity": 10, "note": "Found extra unit"},
        )
        assert resp.status_code == 201
        assert resp.json()["previous_on_hand"] == 100
        assert resp.json()["new_on_hand"] == 110

        inv = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv["on_hand"] == 110

    def test_negative_adjustment_decreases_on_hand(self, client: TestClient):
        """8. Negative ADJUSTMENT decreases on_hand."""
        pid = self._setup_product_with_stock(client, "ADJ-2", on_hand=100)

        resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "adjustment", "quantity": -5, "note": "Damaged goods"},
        )
        assert resp.status_code == 201
        assert resp.json()["previous_on_hand"] == 100
        assert resp.json()["new_on_hand"] == 95

        inv = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv["on_hand"] == 95

    def test_negative_adjustment_cannot_make_on_hand_negative(self, client: TestClient):
        """9. Negative adjustment cannot cause on_hand < 0."""
        pid = self._setup_product_with_stock(client, "ADJ-3", on_hand=10)

        resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "adjustment", "quantity": -15},
        )
        assert resp.status_code == 422
        assert "negative on-hand stock" in resp.text

        inv = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv["on_hand"] == 10

    def test_negative_adjustment_cannot_make_on_hand_less_than_reserved(self, client: TestClient):
        """10. Negative adjustment cannot reduce on_hand below reserved."""
        pid = self._setup_product_with_stock(client, "ADJ-4", on_hand=50, reserved=40)

        # On-hand 50, reserved 40. Reducing by 15 would make on_hand 35 (< 40). Must fail.
        resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "adjustment", "quantity": -15},
        )
        assert resp.status_code == 422
        assert "below reserved stock" in resp.text

        inv = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv["on_hand"] == 50

    def test_zero_quantity_rejected_for_all_types(self, client: TestClient):
        """11, 12, 13, 14. Zero quantity is rejected for SALE, RESTOCK, RETURN, and ADJUSTMENT."""
        pid = self._setup_product_with_stock(client, "ZERO-1", on_hand=50)

        for ttype in ["sale", "restock", "return", "adjustment"]:
            resp = client.post(
                "/api/v1/inventory-transactions",
                json={"product_id": pid, "transaction_type": ttype, "quantity": 0},
            )
            assert resp.status_code == 422

    def test_negative_quantity_rejected_for_sale_restock_return(self, client: TestClient):
        """Negative quantity is rejected for SALE, RESTOCK, and RETURN (only allowed for ADJUSTMENT)."""
        pid = self._setup_product_with_stock(client, "NEG-TYPES", on_hand=50)

        for ttype in ["sale", "restock", "return"]:
            resp = client.post(
                "/api/v1/inventory-transactions",
                json={"product_id": pid, "transaction_type": ttype, "quantity": -10},
            )
            assert resp.status_code == 422

    def test_transaction_audit_fields_correct(self, client: TestClient):
        """15 & 16. Transaction audit records accurate previous_on_hand and new_on_hand."""
        pid = self._setup_product_with_stock(client, "AUDIT-1", on_hand=200)

        resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "sale", "quantity": 45},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["previous_on_hand"] == 200
        assert data["new_on_hand"] == 155
        assert data["created_at"] is not None

    def test_failed_transaction_leaves_inventory_and_history_clean(self, client: TestClient):
        """17 & 18. Failed transaction does not modify inventory or leave historical records."""
        pid = self._setup_product_with_stock(client, "CLEAN-1", on_hand=10, reserved=5)

        # Initial transaction count
        initial_txs = client.get(f"/api/v1/inventory-transactions?product_id={pid}").json()
        assert len(initial_txs) == 0

        # Attempt invalid sale of 20 (available is only 5)
        resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "sale", "quantity": 20},
        )
        assert resp.status_code == 422

        # Inventory must be unmodified
        inv = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv["on_hand"] == 10
        assert inv["reserved"] == 5

        # No transaction history created
        after_txs = client.get(f"/api/v1/inventory-transactions?product_id={pid}").json()
        assert len(after_txs) == 0

    def test_list_transactions_and_filtering(self, client: TestClient):
        """19, 20, 21. Transaction listing works with product and type filtering."""
        pid1 = self._setup_product_with_stock(client, "FILTER-A", on_hand=100)
        pid2 = self._setup_product_with_stock(client, "FILTER-B", on_hand=100)

        # Create 3 transactions
        client.post("/api/v1/inventory-transactions", json={"product_id": pid1, "transaction_type": "sale", "quantity": 10})
        client.post("/api/v1/inventory-transactions", json={"product_id": pid1, "transaction_type": "restock", "quantity": 20})
        client.post("/api/v1/inventory-transactions", json={"product_id": pid2, "transaction_type": "sale", "quantity": 5})

        # All transactions
        all_txs = client.get("/api/v1/inventory-transactions").json()
        assert len(all_txs) == 3

        # Filter by product_id
        p1_txs = client.get(f"/api/v1/inventory-transactions?product_id={pid1}").json()
        assert len(p1_txs) == 2
        assert all(t["product_id"] == pid1 for t in p1_txs)

        # Filter by transaction_type
        sale_txs = client.get("/api/v1/inventory-transactions?transaction_type=sale").json()
        assert len(sale_txs) == 2
        assert all(t["transaction_type"] == "sale" for t in sale_txs)

        # Filter by both
        p1_restock = client.get(f"/api/v1/inventory-transactions?product_id={pid1}&transaction_type=restock").json()
        assert len(p1_restock) == 1
        assert p1_restock[0]["quantity"] == 20

    def test_get_transaction_by_id(self, client: TestClient):
        """22 & 23. Retrieve transaction by ID works and nonexistent ID returns 404."""
        pid = self._setup_product_with_stock(client, "GET-TX", on_hand=50)
        created = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "return", "quantity": 8, "note": "Receipt #404"},
        ).json()
        tx_id = created["id"]

        resp = client.get(f"/api/v1/inventory-transactions/{tx_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == tx_id
        assert resp.json()["quantity"] == 8
        assert resp.json()["product"]["sku"] == "GET-TX"

        # Nonexistent
        not_found = client.get("/api/v1/inventory-transactions/999999")
        assert not_found.status_code == 404

    def test_product_and_inventory_regression_remains_passing(self, client: TestClient):
        """24. Product CRUD and Inventory endpoints continue to work seamlessly."""
        # Create product
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "REG-TX", "name": "Regression Product", "unit_price": 99.0, "reorder_point": 5},
        )
        assert p_resp.status_code == 201
        pid = p_resp.json()["id"]

        # Inventory check
        inv = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv["on_hand"] == 0
        assert inv["available_stock"] == 0

        # Restock via transaction
        tx_resp = client.post(
            "/api/v1/inventory-transactions",
            json={"product_id": pid, "transaction_type": "restock", "quantity": 100},
        )
        assert tx_resp.status_code == 201

        # Check inventory is 100
        inv_after = client.get(f"/api/v1/inventory/products/{pid}").json()
        assert inv_after["on_hand"] == 100

        # Delete product cascades and removes transactions
        del_resp = client.delete(f"/api/v1/products/{pid}")
        assert del_resp.status_code == 204

        # Verify transaction is cascaded
        tx_list = client.get(f"/api/v1/inventory-transactions?product_id={pid}").json()
        assert len(tx_list) == 0

    def test_database_atomicity_and_rollback(self, test_db_session):
        """25. Service rolls back atomically on failure without modifying inventory."""
        db, _ = test_db_session
        product = create_product(
            db,
            ProductCreate(sku="ATOMIC-1", name="Atomic Product", unit_price=20.0, reorder_point=5),
        )
        inv = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).first()
        inv.on_hand = 50
        inv.reserved = 10
        db.commit()

        # Attempt an invalid transaction directly through service
        with pytest.raises(InsufficientStockError):
            process_inventory_transaction(
                db,
                InventoryTransactionCreate(
                    product_id=product.id,
                    transaction_type=InventoryTransactionType.SALE,
                    quantity=45,  # available is only 40
                ),
            )

        # Verify DB state: on_hand is still 50, and 0 transactions
        db.refresh(inv)
        assert inv.on_hand == 50
        assert inv.reserved == 10
        txs = db.scalars(select(InventoryTransaction).where(InventoryTransaction.product_id == product.id)).all()
        assert len(txs) == 0
