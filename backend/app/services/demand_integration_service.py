import logging
from typing import Any, Dict, List
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agents.demand.agent import DemandRiskAgent
from app.models.sales_history import SalesHistory
from app.schemas.demand import DemandDataPoint
from app.services.inventory_service import get_inventory_by_product
from app.services.product_service import get_product

logger = logging.getLogger(__name__)


class DemandIntegrationError(Exception):
    """Base domain exception for demand integration service failures."""
    pass


class NoSalesHistoryError(DemandIntegrationError):
    """Raised when no SalesHistory records exist for the specified product."""
    pass


def get_sales_history_for_product(
    db: Session,
    product_id: int,
) -> List[DemandDataPoint]:
    """
    Retrieves sales history records for a specific product ID ordered chronologically by sale_date.

    Mappings:
      - sale_date.date() -> DemandDataPoint.date
      - float(quantity) -> DemandDataPoint.quantity

    Note:
      - Does NOT aggregate same-day records here (handled by preprocess_demand_data / DemandRiskAgent).
      - Executes read-only database query (does not commit).
    """
    try:
        query = (
            select(SalesHistory)
            .where(SalesHistory.product_id == product_id)
            .order_by(SalesHistory.sale_date.asc())
        )
        records = list(db.scalars(query).all())
    except SQLAlchemyError as exc:
        logger.error(
            "Database failure retrieving sales history for product %d: %s",
            product_id,
            type(exc).__name__,
        )
        raise DemandIntegrationError(
            "An internal database error occurred while fetching sales history."
        ) from exc

    return [
        DemandDataPoint(
            date=record.sale_date.date(),
            quantity=float(record.quantity),
        )
        for record in records
    ]


def analyze_product_demand_from_db(
    db: Session,
    product_id: int,
    forecast_horizon_days: int,
    lead_time_days: int,
) -> Dict[str, Any]:
    """
    Orchestrates real database data fetching (Product, SalesHistory, Inventory)
    and executes DemandRiskAgent.

    Flow:
      1. Validates product existence via Product service (raises ProductNotFoundError if missing).
      2. Retrieves sales history via get_sales_history_for_product (raises NoSalesHistoryError if empty).
      3. Retrieves inventory via Inventory service (raises InventoryNotFoundError if missing).
      4. Extracts inventory.available_stock (on_hand - reserved).
      5. Constructs agent context dictionary and executes DemandRiskAgent.run().

    Raises:
        ProductNotFoundError: If product does not exist in catalog.
        InventoryNotFoundError: If inventory record does not exist for product.
        NoSalesHistoryError: If product has zero historical sales records.
        ValueError: If input parameters or history length fail agent validations.
    """
    # 1. Validate product existence
    product = get_product(db, product_id)

    # 2. Retrieve sales history
    sales_history = get_sales_history_for_product(db, product.id)
    if not sales_history:
        raise NoSalesHistoryError(
            f"No sales history records found for product ID {product.id}."
        )

    # 3. Retrieve inventory
    inventory = get_inventory_by_product(db, product.id)
    available_stock = inventory.available_stock

    # 4. Construct context and execute DemandRiskAgent
    agent = DemandRiskAgent()
    context = {
        "product_id": product.id,
        "historical_data": sales_history,
        "forecast_horizon_days": forecast_horizon_days,
        "lead_time_days": lead_time_days,
        "current_available_stock": available_stock,
    }

    return agent.run(context)
