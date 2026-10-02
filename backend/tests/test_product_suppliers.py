from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.supplier import Supplier
from app.schemas.product import ProductCreate
from app.schemas.product_supplier import (
    ProductSupplierCreate,
    ProductSupplierUpdate,
)
from app.schemas.supplier import SupplierCreate
from app.services.product_service import ProductNotFoundError, create_product
from app.services.product_supplier_service import (
    ProductSupplierAlreadyExistsError,
    ProductSupplierNotFoundError,
    ProductSupplierValidationError,
    create_product_supplier,
    delete_product_supplier,
    get_product_supplier,
    list_product_suppliers,
    update_product_supplier,
)
from app.services.supplier_service import (
    SupplierNotFoundError,
    create_supplier,
    delete_supplier,
)


@pytest.fixture(scope="function")
def test_db_session():
    """
    Isolated in-memory SQLite database using StaticPool with foreign keys enabled.
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


class TestProductSupplierService:
    """Unit test suite for ProductSupplier service layer."""

    def _setup_product(self, db, sku="TEST-PROD-1"):
        return create_product(
            db,
            ProductCreate(
                sku=sku,
                name=f"Product {sku}",
                unit_price=Decimal("1500.00"),
                reorder_point=10,
            ),
        )

    def _setup_supplier(self, db, code="SUP-TEST-1"):
        return create_supplier(
            db,
            SupplierCreate(
                supplier_code=code,
                name=f"Supplier {code}",
            ),
        )

    def test_create_product_supplier_offer_success(self, test_db_session):
        """1. Successfully create a product-supplier offer."""
        db, _ = test_db_session
        prod = self._setup_product(db, "PROD-1")
        sup = self._setup_supplier(db, "SUP-1")

        offer = create_product_supplier(
            db,
            ProductSupplierCreate(
                product_id=prod.id,
                supplier_id=sup.id,
                supplier_sku="VEND-SKU-99",
                unit_cost=Decimal("1200.50"),
                moq=25,
                lead_time_days=7,
                is_active=True,
            ),
        )

        assert offer.id is not None
        assert offer.product_id == prod.id
        assert offer.supplier_id == sup.id
        assert offer.supplier_sku == "VEND-SKU-99"
        assert offer.unit_cost == Decimal("1200.50")
        assert offer.moq == 25
        assert offer.lead_time_days == 7
        assert offer.is_active is True
        assert offer.product.sku == "PROD-1"
        assert offer.supplier.supplier_code == "SUP-1"

    def test_same_supplier_can_supply_multiple_products(self, test_db_session):
        """2. A single supplier can supply multiple distinct products."""
        db, _ = test_db_session
        sup = self._setup_supplier(db, "SUP-MULTI")
        prod1 = self._setup_product(db, "PROD-A")
        prod2 = self._setup_product(db, "PROD-B")

        offer1 = create_product_supplier(
            db,
            ProductSupplierCreate(
                product_id=prod1.id,
                supplier_id=sup.id,
                unit_cost=Decimal("500.00"),
                moq=10,
                lead_time_days=3,
            ),
        )
        offer2 = create_product_supplier(
            db,
            ProductSupplierCreate(
                product_id=prod2.id,
                supplier_id=sup.id,
                unit_cost=Decimal("750.00"),
                moq=5,
                lead_time_days=4,
            ),
        )

        offers = list_product_suppliers(db, supplier_id=sup.id)
        assert len(offers) == 2
        offer_ids = {o.id for o in offers}
        assert offer1.id in offer_ids
        assert offer2.id in offer_ids

    def test_same_product_can_have_multiple_suppliers(self, test_db_session):
        """3. A single product can have offers from multiple distinct suppliers."""
        db, _ = test_db_session
        prod = self._setup_product(db, "PROD-COMMON")
        sup1 = self._setup_supplier(db, "SUP-ALPHA")
        sup2 = self._setup_supplier(db, "SUP-BETA")

        create_product_supplier(
            db,
            ProductSupplierCreate(
                product_id=prod.id,
                supplier_id=sup1.id,
                unit_cost=Decimal("2400.00"),
                moq=30,
                lead_time_days=5,
            ),
        )
        create_product_supplier(
            db,
            ProductSupplierCreate(
                product_id=prod.id,
                supplier_id=sup2.id,
                unit_cost=Decimal("2550.00"),
                moq=20,
                lead_time_days=2,
            ),
        )

        offers = list_product_suppliers(db, product_id=prod.id)
        assert len(offers) == 2
        costs = {o.unit_cost for o in offers}
        assert Decimal("2400.00") in costs
        assert Decimal("2550.00") in costs

    def test_duplicate_product_and_supplier_pair_rejected(self, test_db_session):
        """4. Creating a second offer for the same product and supplier is rejected."""
        db, _ = test_db_session
        prod = self._setup_product(db, "PROD-DUP")
        sup = self._setup_supplier(db, "SUP-DUP")

        create_product_supplier(
            db,
            ProductSupplierCreate(
                product_id=prod.id,
                supplier_id=sup.id,
                unit_cost=Decimal("1000.00"),
                moq=10,
                lead_time_days=3,
            ),
        )

        with pytest.raises(ProductSupplierAlreadyExistsError):
            create_product_supplier(
                db,
                ProductSupplierCreate(
                    product_id=prod.id,
                    supplier_id=sup.id,
                    unit_cost=Decimal("950.00"),
                    moq=50,
                    lead_time_days=2,
                ),
            )

    def test_nonexistent_product_rejected(self, test_db_session):
        """5. Offer creation with invalid product_id is rejected."""
        db, _ = test_db_session
        sup = self._setup_supplier(db, "SUP-VALID")

        with pytest.raises(ProductNotFoundError):
            create_product_supplier(
                db,
                ProductSupplierCreate(
                    product_id=999999,
                    supplier_id=sup.id,
                    unit_cost=Decimal("100.00"),
                    moq=1,
                    lead_time_days=1,
                ),
            )

    def test_nonexistent_supplier_rejected(self, test_db_session):
        """6. Offer creation with invalid supplier_id is rejected."""
        db, _ = test_db_session
        prod = self._setup_product(db, "PROD-VALID")

        with pytest.raises(SupplierNotFoundError):
            create_product_supplier(
                db,
                ProductSupplierCreate(
                    product_id=prod.id,
                    supplier_id=999999,
                    unit_cost=Decimal("100.00"),
                    moq=1,
                    lead_time_days=1,
                ),
            )

    def test_unit_cost_cannot_be_negative(self, test_db_session):
        """7. Negative unit cost is rejected."""
        db, _ = test_db_session
        prod = self._setup_product(db, "PROD-NEG")
        sup = self._setup_supplier(db, "SUP-NEG")

        with pytest.raises((ValueError, ProductSupplierValidationError)):
            create_product_supplier(
                db,
                ProductSupplierCreate(
                    product_id=prod.id,
                    supplier_id=sup.id,
                    unit_cost=Decimal("-10.00"),
                    moq=5,
                    lead_time_days=2,
                ),
            )

    def test_moq_must_be_at_least_one(self, test_db_session):
        """8. MOQ less than 1 is rejected."""
        db, _ = test_db_session
        prod = self._setup_product(db, "PROD-MOQ")
        sup = self._setup_supplier(db, "SUP-MOQ")

        with pytest.raises((ValueError, ProductSupplierValidationError)):
            create_product_supplier(
                db,
                ProductSupplierCreate(
                    product_id=prod.id,
                    supplier_id=sup.id,
                    unit_cost=Decimal("100.00"),
                    moq=0,
                    lead_time_days=1,
                ),
            )

    def test_lead_time_cannot_be_negative(self, test_db_session):
        """9. Negative lead time is rejected."""
        db, _ = test_db_session
        prod = self._setup_product(db, "PROD-LEAD")
        sup = self._setup_supplier(db, "SUP-LEAD")

        with pytest.raises((ValueError, ProductSupplierValidationError)):
            create_product_supplier(
                db,
                ProductSupplierCreate(
                    product_id=prod.id,
                    supplier_id=sup.id,
                    unit_cost=Decimal("100.00"),
                    moq=10,
                    lead_time_days=-1,
                ),
            )

    def test_partial_update_works(self, test_db_session):
        """10. Partial update modifies specified commercial terms only."""
        db, _ = test_db_session
        prod = self._setup_product(db, "PROD-UP")
        sup = self._setup_supplier(db, "SUP-UP")

        offer = create_product_supplier(
            db,
            ProductSupplierCreate(
                product_id=prod.id,
                supplier_id=sup.id,
                unit_cost=Decimal("2000.00"),
                moq=10,
                lead_time_days=5,
            ),
        )

        updated = update_product_supplier(
            db,
            offer.id,
            ProductSupplierUpdate(
                unit_cost=Decimal("1850.00"),
                moq=15,
                supplier_sku="NEW-SKU",
                is_active=False,
            ),
        )

        assert updated.unit_cost == Decimal("1850.00")
        assert updated.moq == 15
        assert updated.supplier_sku == "NEW-SKU"
        assert updated.lead_time_days == 5  # Unchanged
        assert updated.is_active is False

    def test_list_and_filtering(self, test_db_session):
        """11, 12, 13. Listing offers by product_id, supplier_id, and is_active."""
        db, _ = test_db_session
        p1 = self._setup_product(db, "F-P1")
        p2 = self._setup_product(db, "F-P2")
        s1 = self._setup_supplier(db, "F-S1")
        s2 = self._setup_supplier(db, "F-S2")

        # p1 + s1 (active)
        create_product_supplier(db, ProductSupplierCreate(product_id=p1.id, supplier_id=s1.id, unit_cost=Decimal("10.00"), moq=1, lead_time_days=1, is_active=True))
        # p1 + s2 (inactive)
        create_product_supplier(db, ProductSupplierCreate(product_id=p1.id, supplier_id=s2.id, unit_cost=Decimal("12.00"), moq=2, lead_time_days=2, is_active=False))
        # p2 + s1 (active)
        create_product_supplier(db, ProductSupplierCreate(product_id=p2.id, supplier_id=s1.id, unit_cost=Decimal("20.00"), moq=5, lead_time_days=3, is_active=True))

        # Filter by product_id
        p1_offers = list_product_suppliers(db, product_id=p1.id)
        assert len(p1_offers) == 2

        # Filter by supplier_id
        s1_offers = list_product_suppliers(db, supplier_id=s1.id)
        assert len(s1_offers) == 2

        # Filter by both + active
        p1_s1_active = list_product_suppliers(db, product_id=p1.id, supplier_id=s1.id, is_active=True)
        assert len(p1_s1_active) == 1
        assert p1_s1_active[0].unit_cost == Decimal("10.00")

    def test_delete_offer_leaves_product_and_supplier_intact(self, test_db_session):
        """14, 15, 16. Deleting ProductSupplier removes offer but leaves Product & Supplier."""
        db, _ = test_db_session
        prod = self._setup_product(db, "PROD-KEEP")
        sup = self._setup_supplier(db, "SUP-KEEP")

        offer = create_product_supplier(
            db,
            ProductSupplierCreate(
                product_id=prod.id,
                supplier_id=sup.id,
                unit_cost=Decimal("300.00"),
                moq=10,
                lead_time_days=2,
            ),
        )

        delete_product_supplier(db, offer.id)

        # Offer is deleted
        with pytest.raises(ProductSupplierNotFoundError):
            get_product_supplier(db, offer.id)

        # Product is intact
        assert db.get(Product, prod.id) is not None

        # Supplier is intact
        assert db.get(Supplier, sup.id) is not None

    def test_supplier_deletion_cascades_dependent_offers(self, test_db_session):
        """17. Deleting Supplier cascades to delete its dependent ProductSupplier offers safely."""
        db, _ = test_db_session
        prod = self._setup_product(db, "PROD-CASC")
        sup = self._setup_supplier(db, "SUP-CASC")

        offer = create_product_supplier(
            db,
            ProductSupplierCreate(
                product_id=prod.id,
                supplier_id=sup.id,
                unit_cost=Decimal("450.00"),
                moq=5,
                lead_time_days=4,
            ),
        )
        offer_id = offer.id

        # Delete supplier
        delete_supplier(db, sup.id)

        # Offer should be deleted
        with pytest.raises(ProductSupplierNotFoundError):
            get_product_supplier(db, offer_id)

        # Product still exists
        assert db.get(Product, prod.id) is not None


class TestProductSupplierAPI:
    """Integration test suite for ProductSupplier REST API."""

    def test_api_crud_flow(self, client: TestClient):
        # Create product
        p_res = client.post(
            "/api/v1/products",
            json={"sku": "API-P-1", "name": "API Prod", "unit_price": 500.0, "reorder_point": 5},
        )
        pid = p_res.json()["id"]

        # Create supplier
        s_res = client.post(
            "/api/v1/suppliers",
            json={"supplier_code": "API-S-1", "name": "API Sup"},
        )
        sid = s_res.json()["id"]

        # POST /api/v1/product-suppliers
        create_payload = {
            "product_id": pid,
            "supplier_id": sid,
            "supplier_sku": "SKU-XYZ",
            "unit_cost": 380.0,
            "moq": 20,
            "lead_time_days": 4,
            "is_active": True,
        }
        resp = client.post("/api/v1/product-suppliers", json=create_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["unit_cost"] == "380.00"
        assert data["moq"] == 20
        assert data["product"]["sku"] == "API-P-1"
        assert data["supplier"]["supplier_code"] == "API-S-1"
        offer_id = data["id"]

        # GET /api/v1/product-suppliers/{offer_id}
        get_resp = client.get(f"/api/v1/product-suppliers/{offer_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == offer_id

        # Duplicate returns 409
        dup_resp = client.post("/api/v1/product-suppliers", json=create_payload)
        assert dup_resp.status_code == 409

        # PATCH /api/v1/product-suppliers/{offer_id}
        patch_resp = client.patch(
            f"/api/v1/product-suppliers/{offer_id}",
            json={"unit_cost": 360.0, "moq": 30},
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["unit_cost"] == "360.00"
        assert patch_resp.json()["moq"] == 30

        # DELETE /api/v1/product-suppliers/{offer_id}
        del_resp = client.delete(f"/api/v1/product-suppliers/{offer_id}")
        assert del_resp.status_code == 204

        # Verify 404
        assert client.get(f"/api/v1/product-suppliers/{offer_id}").status_code == 404
