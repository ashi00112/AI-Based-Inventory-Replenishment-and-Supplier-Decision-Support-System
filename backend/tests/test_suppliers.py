import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierUpdate
from app.services.supplier_service import (
    SupplierAlreadyExistsError,
    SupplierNotFoundError,
    create_supplier,
    delete_supplier,
    get_supplier,
    get_supplier_by_code,
    list_suppliers,
    update_supplier,
)


@pytest.fixture(scope="function")
def test_db_session():
    """
    Isolated in-memory SQLite database using StaticPool with FK enforcement.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
    TestClient with get_db overridden to use isolated in-memory DB.
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


class TestSupplierService:
    """Unit tests for Supplier Service Layer."""

    def test_create_supplier_success(self, test_db_session):
        db, _ = test_db_session
        sup = create_supplier(
            db,
            SupplierCreate(
                supplier_code="sup-001",
                name="Lanka Tech Distributors",
                contact_name="Sunil Perera",
                email="sunil@lankatech.lk",
                phone="+94 11 234 5678",
                address="123 Galle Road, Colombo 03",
            ),
        )
        assert sup.id is not None
        assert sup.supplier_code == "SUP-001"  # Normalized to uppercase
        assert sup.name == "Lanka Tech Distributors"
        assert sup.is_active is True
        assert sup.created_at is not None

    def test_duplicate_supplier_code_rejected(self, test_db_session):
        db, _ = test_db_session
        create_supplier(
            db,
            SupplierCreate(supplier_code="SUP-002", name="First Supplier"),
        )
        with pytest.raises(SupplierAlreadyExistsError):
            create_supplier(
                db,
                SupplierCreate(supplier_code="sup-002", name="Duplicate Supplier"),
            )

    def test_get_supplier_and_get_by_code(self, test_db_session):
        db, _ = test_db_session
        created = create_supplier(
            db,
            SupplierCreate(supplier_code="SUP-003", name="Colombo IT Hub"),
        )
        fetched = get_supplier(db, created.id)
        assert fetched.name == "Colombo IT Hub"

        by_code = get_supplier_by_code(db, "sup-003")
        assert by_code.id == created.id

    def test_get_nonexistent_supplier_raises_404(self, test_db_session):
        db, _ = test_db_session
        with pytest.raises(SupplierNotFoundError):
            get_supplier(db, 99999)

        with pytest.raises(SupplierNotFoundError):
            get_supplier_by_code(db, "NONEXISTENT")

    def test_list_suppliers_and_filters(self, test_db_session):
        db, _ = test_db_session
        create_supplier(db, SupplierCreate(supplier_code="SUP-A", name="Alpha Tech", is_active=True))
        create_supplier(db, SupplierCreate(supplier_code="SUP-B", name="Beta Peripherals", is_active=False))
        create_supplier(db, SupplierCreate(supplier_code="SUP-C", name="Gamma Cables", is_active=True))

        all_sups = list_suppliers(db)
        assert len(all_sups) == 3

        active_sups = list_suppliers(db, is_active=True)
        assert len(active_sups) == 2
        assert all(s.is_active is True for s in active_sups)

        search_sups = list_suppliers(db, search="Beta")
        assert len(search_sups) == 1
        assert search_sups[0].supplier_code == "SUP-B"

    def test_update_supplier_success(self, test_db_session):
        db, _ = test_db_session
        sup = create_supplier(
            db,
            SupplierCreate(supplier_code="SUP-UPD", name="Original Name"),
        )
        updated = update_supplier(
            db,
            sup.id,
            SupplierUpdate(name="Updated Name", phone="+94 77 123 4567"),
        )
        assert updated.name == "Updated Name"
        assert updated.phone == "+94 77 123 4567"
        assert updated.supplier_code == "SUP-UPD"

    def test_update_supplier_duplicate_code_rejected(self, test_db_session):
        db, _ = test_db_session
        create_supplier(db, SupplierCreate(supplier_code="SUP-1", name="Sup 1"))
        sup2 = create_supplier(db, SupplierCreate(supplier_code="SUP-2", name="Sup 2"))

        with pytest.raises(SupplierAlreadyExistsError):
            update_supplier(db, sup2.id, SupplierUpdate(supplier_code="SUP-1"))

    def test_delete_supplier_success(self, test_db_session):
        db, _ = test_db_session
        sup = create_supplier(db, SupplierCreate(supplier_code="SUP-DEL", name="Delete Me"))
        delete_supplier(db, sup.id)

        with pytest.raises(SupplierNotFoundError):
            get_supplier(db, sup.id)


class TestSupplierAPI:
    """Integration tests for Supplier REST API."""

    def test_create_supplier_api(self, client: TestClient):
        payload = {
            "supplier_code": "SUP-API-1",
            "name": "API Distributor",
            "email": "contact@apidist.com",
            "phone": "+94 11 999 8888",
        }
        res = client.post("/api/v1/suppliers", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["supplier_code"] == "SUP-API-1"
        assert data["name"] == "API Distributor"
        assert data["email"] == "contact@apidist.com"
        assert data["is_active"] is True

    def test_create_supplier_duplicate_code_returns_409(self, client: TestClient):
        payload = {"supplier_code": "SUP-DUP", "name": "Dist 1"}
        client.post("/api/v1/suppliers", json=payload)

        res = client.post("/api/v1/suppliers", json={"supplier_code": "sup-dup", "name": "Dist 2"})
        assert res.status_code == 409
        assert "already exists" in res.json()["detail"]

    def test_invalid_email_format_returns_422(self, client: TestClient):
        payload = {
            "supplier_code": "SUP-BAD-MAIL",
            "name": "Bad Mail",
            "email": "not-an-email",
        }
        res = client.post("/api/v1/suppliers", json=payload)
        assert res.status_code == 422

    def test_get_and_list_suppliers_api(self, client: TestClient):
        res1 = client.post("/api/v1/suppliers", json={"supplier_code": "SUP-L1", "name": "List 1"}).json()
        client.post("/api/v1/suppliers", json={"supplier_code": "SUP-L2", "name": "List 2", "is_active": False})

        # Get by ID
        get_res = client.get(f"/api/v1/suppliers/{res1['id']}")
        assert get_res.status_code == 200
        assert get_res.json()["supplier_code"] == "SUP-L1"

        # List all
        list_res = client.get("/api/v1/suppliers")
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 2

        # Filter active
        active_res = client.get("/api/v1/suppliers?is_active=true")
        assert all(s["is_active"] is True for s in active_res.json())

    def test_patch_supplier_api(self, client: TestClient):
        created = client.post("/api/v1/suppliers", json={"supplier_code": "SUP-P1", "name": "Orig"}).json()
        sid = created["id"]

        patch_res = client.patch(f"/api/v1/suppliers/{sid}", json={"name": "Patched Name", "is_active": False})
        assert patch_res.status_code == 200
        assert patch_res.json()["name"] == "Patched Name"
        assert patch_res.json()["is_active"] is False

    def test_delete_supplier_api(self, client: TestClient):
        created = client.post("/api/v1/suppliers", json={"supplier_code": "SUP-D1", "name": "Del"}).json()
        sid = created["id"]

        del_res = client.delete(f"/api/v1/suppliers/{sid}")
        assert del_res.status_code == 204

        # Nonexistent returns 404
        assert client.get(f"/api/v1/suppliers/{sid}").status_code == 404
