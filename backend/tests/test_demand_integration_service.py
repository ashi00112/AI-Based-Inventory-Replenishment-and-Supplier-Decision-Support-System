from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.sales_history import SalesHistory
from app.services.demand_integration_service import (
    DemandIntegrationError,
    NoSalesHistoryError,
    analyze_product_demand_from_db,
    get_sales_history_for_product,
)
from app.services.inventory_service import InventoryNotFoundError
from app.services.product_service import ProductNotFoundError


@pytest.fixture(scope="function")
def db_session():
    """
    Isolated in-memory SQLite database using StaticPool.
    Ensures zero interaction with external databases.
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
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _create_sample_product_and_inventory(
    db,
    sku: str = "TEST-PROD-1",
    on_hand: int = 100,
    reserved: int = 20,
    incoming: int = 50,
) -> Product:
    """Helper to seed a product and associated inventory in test database."""
    product = Product(
        sku=sku,
        name=f"Product {sku}",
        unit_price=Decimal("1500.00"),
        reorder_point=15,
        is_active=True,
    )
    db.add(product)
    db.flush()

    inventory = Inventory(
        product_id=product.id,
        on_hand=on_hand,
        reserved=reserved,
        incoming=incoming,
    )
    db.add(inventory)
    db.commit()
    db.refresh(product)
    return product


def _seed_sales_history(
    db,
    product_id: int,
    num_days: int = 25,
    start_date: date = date(2026, 1, 1),
    daily_quantity: int = 10,
):
    """Helper to seed sales history entries in test database."""
    records = []
    for i in range(num_days):
        sale_dt = datetime.combine(
            start_date + timedelta(days=i),
            datetime.min.time(),
        ).replace(tzinfo=timezone.utc)

        record = SalesHistory(
            product_id=product_id,
            quantity=daily_quantity,
            unit_price=Decimal("1500.00"),
            total_amount=Decimal(daily_quantity * 1500),
            sale_date=sale_dt,
        )
        records.append(record)

    db.add_all(records)
    db.commit()


def test_get_sales_history_for_product_correct_product_only(db_session):
    """1. Verify get_sales_history_for_product queries records for requested product only."""
    prod_a = _create_sample_product_and_inventory(db_session, sku="PROD-A")
    prod_b = _create_sample_product_and_inventory(db_session, sku="PROD-B")

    _seed_sales_history(db_session, prod_a.id, num_days=5, daily_quantity=10)
    _seed_sales_history(db_session, prod_b.id, num_days=3, daily_quantity=25)

    history_a = get_sales_history_for_product(db_session, prod_a.id)
    history_b = get_sales_history_for_product(db_session, prod_b.id)

    assert len(history_a) == 5
    assert all(p.quantity == 10.0 for p in history_a)

    assert len(history_b) == 3
    assert all(p.quantity == 25.0 for p in history_b)


def test_get_sales_history_chronological_ordering(db_session):
    """2. Verify sales history is returned strictly ordered by sale_date ascending."""
    prod = _create_sample_product_and_inventory(db_session, sku="PROD-ORDER")

    # Insert out of chronological order
    dates = [date(2026, 1, 15), date(2026, 1, 2), date(2026, 1, 8)]
    for d in dates:
        dt = datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc)
        db_session.add(
            SalesHistory(
                product_id=prod.id,
                quantity=5,
                unit_price=Decimal("100.00"),
                total_amount=Decimal("500.00"),
                sale_date=dt,
            )
        )
    db_session.commit()

    history = get_sales_history_for_product(db_session, prod.id)
    assert len(history) == 3
    assert history[0].date == date(2026, 1, 2)
    assert history[1].date == date(2026, 1, 8)
    assert history[2].date == date(2026, 1, 15)


def test_get_sales_history_type_mappings(db_session):
    """3. Verify UTC datetime -> date mapping and quantity -> float mapping."""
    prod = _create_sample_product_and_inventory(db_session, sku="PROD-TYPES")
    dt = datetime(2026, 1, 10, 14, 45, 30, tzinfo=timezone.utc)

    db_session.add(
        SalesHistory(
            product_id=prod.id,
            quantity=18,
            unit_price=Decimal("20.00"),
            total_amount=Decimal("360.00"),
            sale_date=dt,
        )
    )
    db_session.commit()

    history = get_sales_history_for_product(db_session, prod.id)
    assert len(history) == 1
    point = history[0]

    assert point.date == date(2026, 1, 10)
    assert isinstance(point.quantity, float)
    assert point.quantity == 18.0


def test_multiple_sales_same_day_aggregated_in_agent(db_session):
    """4. Verify multiple sales on the same calendar day reach agent/preprocessing correctly."""
    prod = _create_sample_product_and_inventory(db_session, sku="PROD-MULTI-SALE")

    # Seed 20 baseline days
    _seed_sales_history(db_session, prod.id, num_days=20, start_date=date(2026, 1, 1))

    # Add 3 separate sale events on the 21st day (2026-01-21)
    day_21 = date(2026, 1, 21)
    for hour, qty in [(9, 5), (13, 10), (17, 15)]:
        dt = datetime(2026, 1, 21, hour, 0, 0, tzinfo=timezone.utc)
        db_session.add(
            SalesHistory(
                product_id=prod.id,
                quantity=qty,
                unit_price=Decimal("100.00"),
                total_amount=Decimal(qty * 100),
                sale_date=dt,
            )
        )
    db_session.commit()

    res = analyze_product_demand_from_db(
        db_session,
        product_id=prod.id,
        forecast_horizon_days=7,
        lead_time_days=3,
    )

    assert res["product_id"] == prod.id
    assert res["forecast_horizon_days"] == 7
    assert len(res["daily_forecasts"]) == 7


def test_available_stock_from_member_1_inventory(db_session):
    """5. Verify available_stock = on_hand - reserved (ignoring incoming stock)."""
    prod = _create_sample_product_and_inventory(
        db_session,
        sku="PROD-STOCK",
        on_hand=100,
        reserved=30,
        incoming=50,  # Must be ignored
    )
    _seed_sales_history(db_session, prod.id, num_days=25)

    res = analyze_product_demand_from_db(
        db_session,
        product_id=prod.id,
        forecast_horizon_days=7,
        lead_time_days=3,
    )

    # 100 - 30 = 70 available stock. 3 days @ 10 qty/day = 30 demand over lead time -> LOW risk
    assert res["stockout_risk"]["current_available_stock"] == 70
    assert res["stockout_risk"]["risk_level"] == "LOW"


def test_zero_available_stock(db_session):
    """6. Verify behaviour when available stock is 0 (on_hand == reserved)."""
    prod = _create_sample_product_and_inventory(
        db_session,
        sku="PROD-ZERO-STOCK",
        on_hand=20,
        reserved=20,
        incoming=100,
    )
    _seed_sales_history(db_session, prod.id, num_days=25)

    res = analyze_product_demand_from_db(
        db_session,
        product_id=prod.id,
        forecast_horizon_days=7,
        lead_time_days=3,
    )

    assert res["stockout_risk"]["current_available_stock"] == 0
    assert res["stockout_risk"]["risk_level"] == "HIGH"


def test_missing_product_raises_product_not_found(db_session):
    """7. Verify missing product raises ProductNotFoundError."""
    with pytest.raises(ProductNotFoundError):
        analyze_product_demand_from_db(
            db_session,
            product_id=99999,
            forecast_horizon_days=7,
            lead_time_days=3,
        )


def test_missing_inventory_raises_inventory_not_found(db_session):
    """8. Verify product without inventory record raises InventoryNotFoundError."""
    prod = Product(
        sku="NO-INV",
        name="No Inventory Product",
        unit_price=Decimal("50.00"),
        reorder_point=10,
        is_active=True,
    )
    db_session.add(prod)
    db_session.commit()

    _seed_sales_history(db_session, prod.id, num_days=20)

    with pytest.raises(InventoryNotFoundError):
        analyze_product_demand_from_db(
            db_session,
            product_id=prod.id,
            forecast_horizon_days=7,
            lead_time_days=3,
        )


def test_no_sales_history_raises_no_sales_history_error(db_session):
    """9. Verify product with zero sales history raises NoSalesHistoryError."""
    prod = _create_sample_product_and_inventory(db_session, sku="PROD-NO-HISTORY")

    with pytest.raises(NoSalesHistoryError):
        analyze_product_demand_from_db(
            db_session,
            product_id=prod.id,
            forecast_horizon_days=7,
            lead_time_days=3,
        )


def test_successful_end_to_end_db_integration(db_session):
    """10. Verify successful end-to-end DB -> integration service -> DemandRiskAgent execution."""
    prod = _create_sample_product_and_inventory(
        db_session,
        sku="PROD-E2E",
        on_hand=150,
        reserved=10,
    )
    _seed_sales_history(db_session, prod.id, num_days=30, daily_quantity=12)

    res = analyze_product_demand_from_db(
        db_session,
        product_id=prod.id,
        forecast_horizon_days=10,
        lead_time_days=5,
    )

    assert isinstance(res, dict)
    assert res["product_id"] == prod.id
    assert res["forecast_horizon_days"] == 10
    assert "total_forecasted_demand" in res
    assert "evaluation_metrics" in res
    assert "stockout_risk" in res
    assert len(res["daily_forecasts"]) == 10


def test_db_integration_is_read_only(db_session):
    """11. Verify integration service performs read-only DB operations."""
    prod = _create_sample_product_and_inventory(db_session, sku="PROD-READONLY")
    _seed_sales_history(db_session, prod.id, num_days=25)

    history_count_before = db_session.scalars(select(SalesHistory)).all()
    inventory_before = db_session.get(Inventory, prod.inventory.id)
    on_hand_before = inventory_before.on_hand

    analyze_product_demand_from_db(
        db_session,
        product_id=prod.id,
        forecast_horizon_days=7,
        lead_time_days=3,
    )

    history_count_after = db_session.scalars(select(SalesHistory)).all()
    inventory_after = db_session.get(Inventory, prod.inventory.id)

    assert len(history_count_before) == len(history_count_after)
    assert inventory_after.on_hand == on_hand_before
