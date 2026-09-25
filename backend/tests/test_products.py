from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.product import Product


@pytest.fixture(scope="function")
def test_db_session():
    """
    Creates an isolated in-memory SQLite database using StaticPool.
    Ensures zero modification of any cloud Supabase database.
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
def product_client(test_db_session):
    """
    TestClient with get_db overridden to use the isolated in-memory test database.
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


class TestProductCRUD:
    """Comprehensive test suite for Product Management CRUD API."""

    def test_create_valid_product_returns_201(self, product_client: TestClient):
        """1. Creating a valid product returns HTTP 201 Created."""
        payload = {
            "sku": "WM-001",
            "name": "Wireless Mouse",
            "category": "Accessories",
            "description": "Ergonomic 2.4GHz optical wireless mouse",
            "unit_price": 2500.00,
            "reorder_point": 25,
        }
        response = product_client.post("/api/v1/products", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["sku"] == "WM-001"
        assert data["name"] == "Wireless Mouse"
        assert data["category"] == "Accessories"
        assert float(data["unit_price"]) == 2500.00
        assert data["reorder_point"] == 25
        assert data["is_active"] is True
        assert "id" in data

    def test_product_persists_in_database(self, product_client: TestClient, test_db_session):
        """2. Created product actually persists in database."""
        db, _ = test_db_session
        payload = {
            "sku": "KB-100",
            "name": "Mechanical Keyboard",
            "category": "Accessories",
            "unit_price": 12500.50,
            "reorder_point": 10,
        }
        response = product_client.post("/api/v1/products", json=payload)
        assert response.status_code == 201
        product_id = response.json()["id"]

        # Directly query isolated DB
        db_product = db.get(Product, product_id)
        assert db_product is not None
        assert db_product.sku == "KB-100"
        assert db_product.name == "Mechanical Keyboard"
        assert db_product.unit_price == Decimal("12500.50")
        assert db_product.reorder_point == 10

    def test_duplicate_sku_returns_409(self, product_client: TestClient):
        """3. Creating a product with an existing SKU returns HTTP 409 Conflict."""
        payload = {
            "sku": "DUP-001",
            "name": "Original Item",
            "unit_price": 100.00,
            "reorder_point": 5,
        }
        res1 = product_client.post("/api/v1/products", json=payload)
        assert res1.status_code == 201

        # Second creation with identical SKU
        payload_dup = {
            "sku": "DUP-001",
            "name": "Duplicate Item",
            "unit_price": 150.00,
            "reorder_point": 10,
        }
        res2 = product_client.post("/api/v1/products", json=payload_dup)
        assert res2.status_code == 409
        assert "already exists" in res2.json()["detail"].lower()

    def test_blank_sku_rejected(self, product_client: TestClient):
        """4. Blank or whitespace-only SKU is rejected with 422 Unprocessable Entity."""
        payload = {
            "sku": "   ",
            "name": "Valid Name",
            "unit_price": 100.00,
            "reorder_point": 5,
        }
        response = product_client.post("/api/v1/products", json=payload)
        assert response.status_code == 422

    def test_blank_name_rejected(self, product_client: TestClient):
        """5. Blank or whitespace-only product name is rejected with 422."""
        payload = {
            "sku": "VALID-SKU",
            "name": "   ",
            "unit_price": 100.00,
            "reorder_point": 5,
        }
        response = product_client.post("/api/v1/products", json=payload)
        assert response.status_code == 422

    def test_negative_price_rejected(self, product_client: TestClient):
        """6. Negative unit price is rejected with 422."""
        payload = {
            "sku": "NEG-P",
            "name": "Negative Price Item",
            "unit_price": -10.50,
            "reorder_point": 5,
        }
        response = product_client.post("/api/v1/products", json=payload)
        assert response.status_code == 422

    def test_negative_reorder_point_rejected(self, product_client: TestClient):
        """7. Negative reorder point is rejected with 422."""
        payload = {
            "sku": "NEG-ROP",
            "name": "Negative ROP Item",
            "unit_price": 50.00,
            "reorder_point": -1,
        }
        response = product_client.post("/api/v1/products", json=payload)
        assert response.status_code == 422

    def test_list_products_returns_products(self, product_client: TestClient):
        """8. GET /api/v1/products returns all catalog products."""
        product_client.post(
            "/api/v1/products",
            json={"sku": "LST-1", "name": "Item 1", "unit_price": 10, "reorder_point": 2},
        )
        product_client.post(
            "/api/v1/products",
            json={"sku": "LST-2", "name": "Item 2", "unit_price": 20, "reorder_point": 4},
        )

        response = product_client.get("/api/v1/products")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        skus = [p["sku"] for p in data]
        assert "LST-1" in skus
        assert "LST-2" in skus

    def test_get_product_by_id_works(self, product_client: TestClient):
        """9. GET /api/v1/products/{id} returns the specific product details."""
        created = product_client.post(
            "/api/v1/products",
            json={"sku": "GET-1", "name": "Get Specific", "unit_price": 75.0, "reorder_point": 15},
        ).json()

        response = product_client.get(f"/api/v1/products/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]
        assert response.json()["sku"] == "GET-1"

    def test_nonexistent_product_returns_404(self, product_client: TestClient):
        """10. Requesting nonexistent product ID returns HTTP 404 Not Found."""
        response = product_client.get("/api/v1/products/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_product_works(self, product_client: TestClient):
        """11. PATCH /api/v1/products/{id} updates product fields."""
        created = product_client.post(
            "/api/v1/products",
            json={"sku": "UPD-1", "name": "Old Name", "unit_price": 100, "reorder_point": 10},
        ).json()

        update_payload = {
            "name": "New Updated Name",
            "unit_price": 120.50,
            "reorder_point": 30,
        }
        response = product_client.patch(f"/api/v1/products/{created['id']}", json=update_payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Updated Name"
        assert float(data["unit_price"]) == 120.50
        assert data["reorder_point"] == 30
        assert data["sku"] == "UPD-1"  # preserved

    def test_partial_update_preserves_unspecified_fields(self, product_client: TestClient):
        """12. Partial update preserves unspecified fields without overwriting with defaults."""
        created = product_client.post(
            "/api/v1/products",
            json={
                "sku": "PARTIAL-1",
                "name": "Steady Product",
                "category": "Electronics",
                "description": "Important description",
                "unit_price": 300,
                "reorder_point": 50,
            },
        ).json()

        # Update only reorder_point
        response = product_client.patch(
            f"/api/v1/products/{created['id']}",
            json={"reorder_point": 65},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reorder_point"] == 65
        assert data["name"] == "Steady Product"
        assert data["category"] == "Electronics"
        assert data["description"] == "Important description"
        assert float(data["unit_price"]) == 300.00

    def test_duplicate_sku_update_returns_409(self, product_client: TestClient):
        """13. Updating a product's SKU to an existing SKU on another product returns 409."""
        p1 = product_client.post(
            "/api/v1/products",
            json={"sku": "TAKEN-1", "name": "Product 1", "unit_price": 10, "reorder_point": 1},
        ).json()
        p2 = product_client.post(
            "/api/v1/products",
            json={"sku": "TAKEN-2", "name": "Product 2", "unit_price": 20, "reorder_point": 2},
        ).json()

        # Try to change p2's SKU to TAKEN-1
        response = product_client.patch(
            f"/api/v1/products/{p2['id']}",
            json={"sku": "TAKEN-1"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_delete_works(self, product_client: TestClient, test_db_session):
        """14. DELETE /api/v1/products/{id} deletes product returning 204 No Content."""
        db, _ = test_db_session
        created = product_client.post(
            "/api/v1/products",
            json={"sku": "DEL-1", "name": "To Delete", "unit_price": 15, "reorder_point": 5},
        ).json()
        product_id = created["id"]

        del_response = product_client.delete(f"/api/v1/products/{product_id}")
        assert del_response.status_code == 204

        # Confirm deleted from DB
        assert db.get(Product, product_id) is None

    def test_deleted_or_nonexistent_product_returns_404(self, product_client: TestClient):
        """15. Attempting to get or delete nonexistent product returns 404."""
        get_res = product_client.get("/api/v1/products/88888")
        assert get_res.status_code == 404

        del_res = product_client.delete("/api/v1/products/88888")
        assert del_res.status_code == 404

    def test_response_contains_no_sensitive_or_inventory_fields(self, product_client: TestClient):
        """16. Response contains expected public fields and NO inventory quantity fields."""
        created = product_client.post(
            "/api/v1/products",
            json={"sku": "CLEAN-1", "name": "Clean Model", "unit_price": 50, "reorder_point": 10},
        ).json()

        expected_fields = {
            "id",
            "sku",
            "name",
            "category",
            "description",
            "unit_price",
            "reorder_point",
            "is_active",
            "created_at",
            "updated_at",
        }
        assert set(created.keys()) == expected_fields
        # Explicit check that inventory quantities are absent
        assert "on_hand" not in created
        assert "available_stock" not in created
        assert "incoming" not in created
        assert "reserved" not in created

    def test_database_rollback_on_write_failure(self, test_db_session):
        """17. Database rollback occurs on integrity violation without leaving connection broken."""
        from app.services.product_service import ProductAlreadyExistsError, create_product
        from app.schemas.product import ProductCreate

        db, _ = test_db_session
        item1 = ProductCreate(sku="ROLL-1", name="Item 1", unit_price=Decimal("10"), reorder_point=1)
        create_product(db, item1)

        # Attempt to insert identical item via service
        item2 = ProductCreate(sku="ROLL-1", name="Duplicate", unit_price=Decimal("20"), reorder_point=2)
        with pytest.raises(ProductAlreadyExistsError):
            create_product(db, item2)

        # Confirm DB session is healthy and can execute subsequent transactions
        item3 = ProductCreate(sku="ROLL-2", name="Item 3", unit_price=Decimal("30"), reorder_point=3)
        res = create_product(db, item3)
        assert res.id is not None
