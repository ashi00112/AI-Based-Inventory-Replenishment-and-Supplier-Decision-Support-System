from decimal import Decimal
from typing import List, Tuple
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.inventory.agent import InventoryMonitoringAgent
from app.database.base import Base
from app.database.session import get_db
from app.main import app
from app.models.inventory import Inventory
from app.models.product import Product
from app.schemas.inventory import (
    InventoryMonitoringItem,
    InventoryMonitoringReport,
    InventoryStatus,
    InventoryUpdate,
)
from app.schemas.product import ProductCreate
from app.services.inventory_service import (
    InventoryNotFoundError,
    update_inventory,
)
from app.services.product_service import create_product


@pytest.fixture(scope="function")
def test_db_session():
    """
    Isolated in-memory SQLite database using StaticPool.
    Guarantees absolute test isolation without touching external databases.
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
    FastAPI TestClient with get_db dependency overridden to use isolated SQLite session.
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


class TestInventoryMonitoringAgent:
    """Comprehensive test suite for the deterministic Inventory Monitoring Agent and its API integration."""

    @pytest.fixture(autouse=True)
    def setup_agent(self):
        self.agent = InventoryMonitoringAgent()

    def _setup_product_and_inventory(
        self,
        db: Session,
        sku: str = "MON-SKU-1",
        name: str = "Monitoring Test Product",
        reorder_point: int = 10,
        unit_price: Decimal = Decimal("25.00"),
        on_hand: int = 100,
        reserved: int = 10,
        incoming: int = 0,
    ) -> Product:
        product = create_product(
            db,
            ProductCreate(
                sku=sku,
                name=name,
                unit_price=unit_price,
                reorder_point=reorder_point,
            ),
        )
        update_inventory(
            db=db,
            product_id=product.id,
            inventory_update=InventoryUpdate(
                on_hand=on_hand,
                reserved=reserved,
                incoming=incoming,
            ),
        )
        db.refresh(product)
        return product

    # =========================================================================
    # A. STATUS CLASSIFICATION RULES
    # =========================================================================

    def test_status_out_of_stock_when_available_stock_is_zero(self):
        """1. available_stock == 0 evaluates to OUT_OF_STOCK regardless of reorder_point."""
        assert self.agent.evaluate_stock_status(available_stock=0, reorder_point=10) == InventoryStatus.OUT_OF_STOCK
        assert self.agent.evaluate_stock_status(available_stock=0, reorder_point=0) == InventoryStatus.OUT_OF_STOCK

    def test_status_low_stock_when_available_stock_below_reorder_point(self):
        """2. available_stock < reorder_point (and > 0) evaluates to LOW_STOCK."""
        assert self.agent.evaluate_stock_status(available_stock=4, reorder_point=10) == InventoryStatus.LOW_STOCK
        assert self.agent.evaluate_stock_status(available_stock=1, reorder_point=5) == InventoryStatus.LOW_STOCK

    def test_status_low_stock_when_available_stock_equals_reorder_point(self):
        """3. available_stock == reorder_point (threshold edge) evaluates to LOW_STOCK."""
        assert self.agent.evaluate_stock_status(available_stock=10, reorder_point=10) == InventoryStatus.LOW_STOCK
        assert self.agent.evaluate_stock_status(available_stock=5, reorder_point=5) == InventoryStatus.LOW_STOCK

    def test_status_healthy_when_available_stock_greater_than_reorder_point(self):
        """4. available_stock > reorder_point evaluates to HEALTHY."""
        assert self.agent.evaluate_stock_status(available_stock=11, reorder_point=10) == InventoryStatus.HEALTHY
        assert self.agent.evaluate_stock_status(available_stock=100, reorder_point=20) == InventoryStatus.HEALTHY

    def test_reserved_stock_correctly_affects_available_stock_and_status(self, test_db_session):
        """5. Reserved stock reduces available_stock, ensuring status classification uses (on_hand - reserved)."""
        db, _ = test_db_session
        # on_hand = 20, reserved = 5 -> available_stock = 15
        # With reorder_point = 10 -> 15 > 10 -> HEALTHY
        product_healthy = self._setup_product_and_inventory(
            db, sku="RSV-HEALTHY", reorder_point=10, on_hand=20, reserved=5
        )
        item_healthy = self.agent.monitor_product(db, product_healthy.id)
        assert item_healthy.available_stock == 15
        assert item_healthy.status == InventoryStatus.HEALTHY

        # With reorder_point = 15 -> 15 <= 15 -> LOW_STOCK
        product_low = self._setup_product_and_inventory(
            db, sku="RSV-LOW", reorder_point=15, on_hand=20, reserved=5
        )
        item_low = self.agent.monitor_product(db, product_low.id)
        assert item_low.available_stock == 15
        assert item_low.status == InventoryStatus.LOW_STOCK

        # on_hand = 20, reserved = 20 -> available_stock = 0 -> OUT_OF_STOCK
        product_oos = self._setup_product_and_inventory(
            db, sku="RSV-OOS", reorder_point=0, on_hand=20, reserved=20
        )
        item_oos = self.agent.monitor_product(db, product_oos.id)
        assert item_oos.available_stock == 0
        assert item_oos.status == InventoryStatus.OUT_OF_STOCK

    # =========================================================================
    # B. SINGLE PRODUCT MONITORING
    # =========================================================================

    def test_monitor_product_returns_accurate_structured_item(self, test_db_session):
        """6. monitor_product returns InventoryMonitoringItem with all expected fields and metadata."""
        db, _ = test_db_session
        product = self._setup_product_and_inventory(
            db,
            sku="SINGLE-PROD",
            name="Precision Sensor",
            reorder_point=15,
            on_hand=50,
            reserved=10,
            incoming=25,
        )

        item = self.agent.monitor_product(db, product.id)
        assert isinstance(item, InventoryMonitoringItem)
        assert item.product_id == product.id
        assert item.product_name == "Precision Sensor"
        assert item.sku == "SINGLE-PROD"
        assert item.reorder_point == 15
        assert item.on_hand == 50
        assert item.reserved == 10
        assert item.incoming == 25
        assert item.available_stock == 40
        assert item.status == InventoryStatus.HEALTHY

    def test_monitor_product_nonexistent_product_raises_not_found(self, test_db_session):
        """7. monitor_product raises InventoryNotFoundError when queried for a nonexistent product ID."""
        db, _ = test_db_session
        with pytest.raises(InventoryNotFoundError):
            self.agent.monitor_product(db, 99999)

    # =========================================================================
    # C. COLLECTION MONITORING & REPORT GENERATION
    # =========================================================================

    def test_monitor_inventory_generates_accurate_aggregated_report(self, test_db_session):
        """8. monitor_inventory calculates accurate counts and aggregates for full catalog."""
        db, _ = test_db_session

        # 1. Out of stock item (available = 0)
        self._setup_product_and_inventory(
            db, sku="COLL-OOS", name="Item OOS", reorder_point=10, on_hand=5, reserved=5, incoming=10
        )
        # 2. Low stock item (available = 8 <= 10)
        self._setup_product_and_inventory(
            db, sku="COLL-LOW", name="Item Low", reorder_point=10, on_hand=8, reserved=0, incoming=0
        )
        # 3. Healthy item (available = 90 > 20)
        self._setup_product_and_inventory(
            db, sku="COLL-HEALTHY", name="Item Healthy", reorder_point=20, on_hand=100, reserved=10, incoming=50
        )

        report = self.agent.monitor_inventory(db)
        assert isinstance(report, InventoryMonitoringReport)
        assert report.total_items == 3
        assert report.out_of_stock_count == 1
        assert report.low_stock_count == 1
        assert report.healthy_count == 1
        assert len(report.items) == 3

        statuses = {item.sku: item.status for item in report.items}
        assert statuses["COLL-OOS"] == InventoryStatus.OUT_OF_STOCK
        assert statuses["COLL-LOW"] == InventoryStatus.LOW_STOCK
        assert statuses["COLL-HEALTHY"] == InventoryStatus.HEALTHY

    def test_monitor_inventory_empty_catalog(self, test_db_session):
        """9. monitor_inventory returns an empty report with 0 counts on an empty catalog."""
        db, _ = test_db_session
        report = self.agent.monitor_inventory(db)
        assert report.total_items == 0
        assert report.healthy_count == 0
        assert report.low_stock_count == 0
        assert report.out_of_stock_count == 0
        assert report.items == []

    def test_generate_report_from_items_list(self):
        """10. generate_report creates an accurate summary report directly from an item list."""
        items: List[InventoryMonitoringItem] = [
            InventoryMonitoringItem(
                product_id=1,
                product_name="P1",
                sku="P1",
                reorder_point=5,
                on_hand=0,
                reserved=0,
                incoming=0,
                available_stock=0,
                status=InventoryStatus.OUT_OF_STOCK,
            ),
            InventoryMonitoringItem(
                product_id=2,
                product_name="P2",
                sku="P2",
                reorder_point=10,
                on_hand=5,
                reserved=0,
                incoming=0,
                available_stock=5,
                status=InventoryStatus.LOW_STOCK,
            ),
            InventoryMonitoringItem(
                product_id=3,
                product_name="P3",
                sku="P3",
                reorder_point=10,
                on_hand=50,
                reserved=0,
                incoming=0,
                available_stock=50,
                status=InventoryStatus.HEALTHY,
            ),
        ]
        report = self.agent.generate_report(items)
        assert report.total_items == 3
        assert report.out_of_stock_count == 1
        assert report.low_stock_count == 1
        assert report.healthy_count == 1

    # =========================================================================
    # D. BASE AGENT CONTRACT (run(context))
    # =========================================================================

    def test_agent_run_with_single_product_context(self, test_db_session):
        """11. BaseAgent.run() evaluates a single product when passed db and product_id."""
        db, _ = test_db_session
        product = self._setup_product_and_inventory(
            db, sku="RUN-PROD", reorder_point=10, on_hand=30, reserved=0
        )

        result = self.agent.run({"db": db, "product_id": product.id})
        assert result["status"] == "success"
        assert result["agent"] == "inventory_monitoring_agent"
        assert result["inventory_status"] == "healthy"
        assert result["item"]["product_id"] == product.id

    def test_agent_run_with_db_collection_context(self, test_db_session):
        """12. BaseAgent.run() evaluates the full catalog when passed db without product_id."""
        db, _ = test_db_session
        self._setup_product_and_inventory(db, sku="RUN-COL-1", on_hand=0, reserved=0)
        self._setup_product_and_inventory(db, sku="RUN-COL-2", on_hand=50, reserved=0)

        result = self.agent.run({"db": db})
        assert result["status"] == "success"
        assert result["agent"] == "inventory_monitoring_agent"
        assert result["report"]["total_items"] == 2
        assert result["report"]["out_of_stock_count"] == 1
        assert result["report"]["healthy_count"] == 1

    def test_agent_run_with_preloaded_inventory_instance(self, test_db_session):
        """13. BaseAgent.run() evaluates a preloaded Inventory ORM instance directly."""
        db, _ = test_db_session
        product = self._setup_product_and_inventory(
            db, sku="RUN-INV", reorder_point=20, on_hand=15, reserved=0
        )
        inv = db.scalars(select(Inventory).where(Inventory.product_id == product.id)).first()

        result = self.agent.run({"inventory": inv})
        assert result["status"] == "success"
        assert result["inventory_status"] == "low_stock"
        assert result["item"]["available_stock"] == 15

    def test_agent_run_with_preloaded_inventory_list(self, test_db_session):
        """14. BaseAgent.run() evaluates a preloaded list of Inventory instances."""
        db, _ = test_db_session
        p1 = self._setup_product_and_inventory(db, sku="RUN-L1", on_hand=0, reserved=0)
        p2 = self._setup_product_and_inventory(db, sku="RUN-L2", on_hand=100, reserved=0)
        invs = list(db.scalars(select(Inventory)).all())

        result = self.agent.run({"inventories": invs})
        assert result["status"] == "success"
        assert result["report"]["total_items"] == 2

    def test_agent_run_with_empty_or_invalid_context(self):
        """15. BaseAgent.run() returns structured error dict when insufficient context is provided."""
        result = self.agent.run({})
        assert result["status"] == "error"
        assert "Insufficient context" in result["message"]

    # =========================================================================
    # E. FASTAPI API INTEGRATION TESTS
    # =========================================================================

    def test_api_get_inventory_monitor_collection_endpoint(self, client, test_db_session):
        """16. GET /api/v1/inventory/monitor returns 200 OK with accurate aggregated report."""
        db, _ = test_db_session
        self._setup_product_and_inventory(
            db, sku="API-1", name="Product 1", reorder_point=10, on_hand=0, reserved=0
        )
        self._setup_product_and_inventory(
            db, sku="API-2", name="Product 2", reorder_point=10, on_hand=5, reserved=0
        )
        self._setup_product_and_inventory(
            db, sku="API-3", name="Product 3", reorder_point=10, on_hand=50, reserved=0
        )

        response = client.get("/api/v1/inventory/monitor")
        assert response.status_code == 200

        data = response.json()
        assert data["total_items"] == 3
        assert data["out_of_stock_count"] == 1
        assert data["low_stock_count"] == 1
        assert data["healthy_count"] == 1
        assert len(data["items"]) == 3

    def test_api_get_inventory_monitor_pagination(self, client, test_db_session):
        """17. GET /api/v1/inventory/monitor respects skip and limit pagination parameters."""
        db, _ = test_db_session
        for i in range(5):
            self._setup_product_and_inventory(
                db, sku=f"PAG-{i}", name=f"Product {i}", reorder_point=5, on_hand=20, reserved=0
            )

        response = client.get("/api/v1/inventory/monitor?skip=1&limit=2")
        assert response.status_code == 200

        data = response.json()
        assert len(data["items"]) == 2
        assert data["total_items"] == 2

    def test_api_get_inventory_monitor_single_product_endpoint(self, client, test_db_session):
        """18. GET /api/v1/inventory/monitor/{product_id} returns 200 OK with correct item details."""
        db, _ = test_db_session
        product = self._setup_product_and_inventory(
            db, sku="API-SINGLE", name="Single Monitored Item", reorder_point=10, on_hand=8, reserved=0
        )

        response = client.get(f"/api/v1/inventory/monitor/{product.id}")
        assert response.status_code == 200

        data = response.json()
        assert data["product_id"] == product.id
        assert data["product_name"] == "Single Monitored Item"
        assert data["sku"] == "API-SINGLE"
        assert data["available_stock"] == 8
        assert data["status"] == "low_stock"

    def test_api_get_inventory_monitor_nonexistent_product_returns_404(self, client):
        """19. GET /api/v1/inventory/monitor/{product_id} returns 404 NOT FOUND for missing product."""
        response = client.get("/api/v1/inventory/monitor/99999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
