import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.inventory import Inventory
from app.models.product import Product
from app.schemas.inventory import InventoryUpdate
from app.services.inventory_service import (
    InventoryNotFoundError,
    InvalidInventoryStateError,
    get_inventory_by_product,
    update_inventory,
)
from app.services.product_service import create_product
from app.schemas.product import ProductCreate


@pytest.fixture(scope="function")
def test_db_session():
    """
    Creates an isolated in-memory SQLite database using StaticPool.
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


class TestInventoryManagement:
    """Comprehensive test suite for Inventory/Stock Management."""

    def test_product_auto_creates_inventory_initialized_to_zero(self, client: TestClient):
        """1. Creating a product automatically initializes an inventory record with 0 stock."""
        resp = client.post(
            "/api/v1/products",
            json={
                "sku": "WM-001",
                "name": "Wireless Mouse",
                "unit_price": 25.00,
                "reorder_point": 25,
            },
        )
        assert resp.status_code == 201
        product_id = resp.json()["id"]

        # Check inventory for this product
        inv_resp = client.get(f"/api/v1/inventory/products/{product_id}")
        assert inv_resp.status_code == 200
        inv_data = inv_resp.json()
        assert inv_data["product_id"] == product_id
        assert inv_data["on_hand"] == 0
        assert inv_data["reserved"] == 0
        assert inv_data["incoming"] == 0
        assert inv_data["available_stock"] == 0
        assert inv_data["product"]["sku"] == "WM-001"
        assert inv_data["product"]["reorder_point"] == 25

    def test_list_inventory_returns_all_records(self, client: TestClient):
        """2. Inventory listing returns all records with product information."""
        client.post(
            "/api/v1/products",
            json={"sku": "SKU-A", "name": "Item A", "unit_price": 10.0, "reorder_point": 5},
        )
        client.post(
            "/api/v1/products",
            json={"sku": "SKU-B", "name": "Item B", "unit_price": 20.0, "reorder_point": 10},
        )

        resp = client.get("/api/v1/inventory")
        assert resp.status_code == 200
        records = resp.json()
        assert len(records) == 2
        skus = [r["product"]["sku"] for r in records]
        assert "SKU-A" in skus
        assert "SKU-B" in skus

    def test_get_inventory_by_product_id(self, client: TestClient):
        """3. Inventory lookup by product ID returns accurate stock details."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "KB-100", "name": "Mechanical Keyboard", "unit_price": 75.0, "reorder_point": 15},
        )
        product_id = p_resp.json()["id"]

        resp = client.get(f"/api/v1/inventory/products/{product_id}")
        assert resp.status_code == 200
        assert resp.json()["product_id"] == product_id
        assert resp.json()["product"]["name"] == "Mechanical Keyboard"

    def test_update_on_hand_successfully(self, client: TestClient):
        """4. on_hand updates successfully."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "UPD-1", "name": "Item 1", "unit_price": 5.0, "reorder_point": 10},
        )
        product_id = p_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/inventory/products/{product_id}",
            json={"on_hand": 100},
        )
        assert resp.status_code == 200
        assert resp.json()["on_hand"] == 100
        assert resp.json()["available_stock"] == 100

    def test_update_reserved_successfully(self, client: TestClient):
        """5. reserved updates successfully when reserved <= on_hand."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "UPD-2", "name": "Item 2", "unit_price": 5.0, "reorder_point": 10},
        )
        product_id = p_resp.json()["id"]

        # First set on_hand
        client.patch(f"/api/v1/inventory/products/{product_id}", json={"on_hand": 50})
        # Now update reserved
        resp = client.patch(f"/api/v1/inventory/products/{product_id}", json={"reserved": 20})
        assert resp.status_code == 200
        assert resp.json()["reserved"] == 20
        assert resp.json()["available_stock"] == 30

    def test_update_incoming_successfully(self, client: TestClient):
        """6. incoming updates successfully."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "UPD-3", "name": "Item 3", "unit_price": 5.0, "reorder_point": 10},
        )
        product_id = p_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/inventory/products/{product_id}",
            json={"incoming": 45},
        )
        assert resp.status_code == 200
        assert resp.json()["incoming"] == 45

    def test_available_stock_calculates_correctly(self, client: TestClient):
        """7. available_stock equals (on_hand - reserved). Example: 100 - 25 = 75."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "CALC-1", "name": "Calculated Stock", "unit_price": 10.0, "reorder_point": 10},
        )
        product_id = p_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/inventory/products/{product_id}",
            json={"on_hand": 100, "reserved": 25, "incoming": 40},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["on_hand"] == 100
        assert data["reserved"] == 25
        assert data["incoming"] == 40
        assert data["available_stock"] == 75

    def test_negative_on_hand_rejected(self, client: TestClient):
        """8. Negative on_hand rejected with 422 Unprocessable Entity."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "NEG-1", "name": "Neg On Hand", "unit_price": 10.0, "reorder_point": 5},
        )
        product_id = p_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/inventory/products/{product_id}",
            json={"on_hand": -10},
        )
        assert resp.status_code == 422

    def test_negative_reserved_rejected(self, client: TestClient):
        """9. Negative reserved rejected with 422 Unprocessable Entity."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "NEG-2", "name": "Neg Reserved", "unit_price": 10.0, "reorder_point": 5},
        )
        product_id = p_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/inventory/products/{product_id}",
            json={"reserved": -5},
        )
        assert resp.status_code == 422

    def test_negative_incoming_rejected(self, client: TestClient):
        """10. Negative incoming rejected with 422 Unprocessable Entity."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "NEG-3", "name": "Neg Incoming", "unit_price": 10.0, "reorder_point": 5},
        )
        product_id = p_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/inventory/products/{product_id}",
            json={"incoming": -1},
        )
        assert resp.status_code == 422

    def test_reserved_greater_than_on_hand_rejected_in_payload(self, client: TestClient):
        """11. reserved > on_hand rejected in single update payload."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "INV-BAL-1", "name": "Balance Test 1", "unit_price": 10.0, "reorder_point": 5},
        )
        product_id = p_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/inventory/products/{product_id}",
            json={"on_hand": 10, "reserved": 15},
        )
        assert resp.status_code == 422
        assert "Reserved stock cannot exceed on-hand stock" in resp.text

    def test_reserved_greater_than_existing_on_hand_rejected(self, client: TestClient):
        """11b. reserved > existing on_hand rejected when updating only reserved."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "INV-BAL-2", "name": "Balance Test 2", "unit_price": 10.0, "reorder_point": 5},
        )
        product_id = p_resp.json()["id"]

        # on_hand is 0 initially. Trying to set reserved = 5 without increasing on_hand
        resp = client.patch(
            f"/api/v1/inventory/products/{product_id}",
            json={"reserved": 5},
        )
        assert resp.status_code == 422
        assert "Reserved stock (5) cannot exceed on-hand stock (0)" in resp.text

    def test_available_stock_cannot_be_supplied_by_client(self, client: TestClient):
        """12. available_stock cannot be supplied/overridden by client (extra field forbidden)."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "EXTRA-1", "name": "Extra Field", "unit_price": 10.0, "reorder_point": 5},
        )
        product_id = p_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/inventory/products/{product_id}",
            json={"on_hand": 50, "available_stock": 999},
        )
        assert resp.status_code == 422

    def test_nonexistent_product_returns_404(self, client: TestClient):
        """13. Nonexistent product/inventory lookup and patch return 404."""
        get_resp = client.get("/api/v1/inventory/products/99999")
        assert get_resp.status_code == 404

        patch_resp = client.patch("/api/v1/inventory/products/99999", json={"on_hand": 10})
        assert patch_resp.status_code == 404

    def test_duplicate_inventory_record_prevented_by_unique_constraint(self, test_db_session):
        """14. One product cannot have duplicate inventory records."""
        db, _ = test_db_session
        product = create_product(
            db,
            ProductCreate(sku="DUP-INV", name="Dup Test", unit_price=10.0, reorder_point=5),
        )

        # Attempt to insert a second inventory record for same product
        second_inv = Inventory(product_id=product.id, on_hand=10, reserved=0, incoming=0)
        db.add(second_inv)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_update_persists_correctly_across_requests(self, client: TestClient):
        """15. Updated inventory persists and is returned on subsequent GETs."""
        p_resp = client.post(
            "/api/v1/products",
            json={"sku": "PERSIST-1", "name": "Persist Item", "unit_price": 10.0, "reorder_point": 5},
        )
        product_id = p_resp.json()["id"]

        client.patch(
            f"/api/v1/inventory/products/{product_id}",
            json={"on_hand": 120, "reserved": 20, "incoming": 60},
        )

        get_resp = client.get(f"/api/v1/inventory/products/{product_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["on_hand"] == 120
        assert data["reserved"] == 20
        assert data["incoming"] == 60
        assert data["available_stock"] == 100

    def test_database_check_constraints_enforced(self, test_db_session):
        """16. Database check constraints reject negative values at DB level."""
        db, _ = test_db_session
        product = create_product(
            db,
            ProductCreate(sku="CK-TEST", name="Constraint Test", unit_price=10.0, reorder_point=5),
        )

        # Direct violation of on_hand >= 0
        inv = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).first()
        inv.on_hand = -5
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_product_crud_regression_remains_working(self, client: TestClient):
        """17. Product CRUD continues to function flawlessly with inventory attached."""
        create_resp = client.post(
            "/api/v1/products",
            json={"sku": "REGR-1", "name": "Regression Item", "unit_price": 50.0, "reorder_point": 10},
        )
        assert create_resp.status_code == 201
        pid = create_resp.json()["id"]

        # Update product
        update_resp = client.patch(f"/api/v1/products/{pid}", json={"name": "Updated Regression Item"})
        assert update_resp.status_code == 200
        assert update_resp.json()["name"] == "Updated Regression Item"

        # Delete product also cascades and deletes inventory
        del_resp = client.delete(f"/api/v1/products/{pid}")
        assert del_resp.status_code == 204

        # Verify inventory is gone
        inv_resp = client.get(f"/api/v1/inventory/products/{pid}")
        assert inv_resp.status_code == 404

    def test_failed_writes_rollback_safely(self, test_db_session):
        """18. Failed writes rollback cleanly without leaving session dirty."""
        db, _ = test_db_session
        product = create_product(
            db,
            ProductCreate(sku="RB-TEST", name="Rollback Test", unit_price=10.0, reorder_point=5),
        )

        with pytest.raises(InvalidInventoryStateError):
            update_inventory(db, product.id, InventoryUpdate(reserved=10))

        # Check that original inventory is intact (0, 0, 0)
        inv = get_inventory_by_product(db, product.id)
        assert inv.on_hand == 0
        assert inv.reserved == 0
        assert inv.available_stock == 0
