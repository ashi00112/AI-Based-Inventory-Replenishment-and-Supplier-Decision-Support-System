import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent
from app.models.inventory import Inventory
from app.schemas.inventory import (
    InventoryMonitoringItem,
    InventoryMonitoringReport,
    InventoryStatus,
)
from app.services.inventory_service import (
    get_inventory_by_product,
    list_inventory,
)

logger = logging.getLogger(__name__)


class InventoryMonitoringAgent(BaseAgent):
    """
    Deterministic Inventory Monitoring Agent (Developer 1).

    Responsibilities:
    - Monitor real-time stock levels and calculate net available stock.
    - Classify inventory health status (OUT_OF_STOCK, LOW_STOCK, HEALTHY) against reorder thresholds.
    - Generate structured monitoring items and aggregated inventory reports.
    - Compatible with BaseAgent.run(context) execution loop.
    """

    def __init__(self, agent_name: str = "inventory_monitoring_agent"):
        super().__init__(agent_name=agent_name)

    @staticmethod
    def evaluate_stock_status(available_stock: int, reorder_point: int) -> InventoryStatus:
        """
        Applies deterministic stock classification rules:
        - available_stock == 0 -> OUT_OF_STOCK
        - available_stock <= reorder_point -> LOW_STOCK
        - available_stock > reorder_point -> HEALTHY
        """
        if available_stock == 0:
            return InventoryStatus.OUT_OF_STOCK
        elif available_stock <= reorder_point:
            return InventoryStatus.LOW_STOCK
        else:
            return InventoryStatus.HEALTHY

    def evaluate_inventory_item(self, inventory: Inventory) -> InventoryMonitoringItem:
        """
        Evaluates stock health for a single Inventory model instance using its available_stock property.
        Reuses eagerly loaded product relationship without duplicating queries.
        """
        product = inventory.product
        product_name = product.name if product is not None else ""
        sku = product.sku if product is not None else None
        reorder_point = product.reorder_point if product is not None else 0
        available_stock = inventory.available_stock
        status = self.evaluate_stock_status(available_stock, reorder_point)

        return InventoryMonitoringItem(
            product_id=inventory.product_id,
            product_name=product_name,
            sku=sku,
            reorder_point=reorder_point,
            on_hand=inventory.on_hand,
            reserved=inventory.reserved,
            incoming=inventory.incoming,
            available_stock=available_stock,
            status=status,
        )

    def monitor_product(self, db: Session, product_id: int) -> InventoryMonitoringItem:
        """
        Monitors a single product by ID, fetching the inventory record via existing inventory_service.
        """
        inventory = get_inventory_by_product(db=db, product_id=product_id)
        return self.evaluate_inventory_item(inventory)

    def generate_report(self, items: List[InventoryMonitoringItem]) -> InventoryMonitoringReport:
        """
        Generates an aggregated inventory monitoring report from a collection of evaluated items.
        """
        total_items = len(items)
        healthy_count = sum(1 for item in items if item.status == InventoryStatus.HEALTHY)
        low_stock_count = sum(1 for item in items if item.status == InventoryStatus.LOW_STOCK)
        out_of_stock_count = sum(1 for item in items if item.status == InventoryStatus.OUT_OF_STOCK)

        return InventoryMonitoringReport(
            items=items,
            total_items=total_items,
            healthy_count=healthy_count,
            low_stock_count=low_stock_count,
            out_of_stock_count=out_of_stock_count,
        )

    def monitor_inventory(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
    ) -> InventoryMonitoringReport:
        """
        Monitors a collection of inventory records retrieved via existing inventory_service.
        """
        inventories = list_inventory(db=db, skip=skip, limit=limit)
        items = [self.evaluate_inventory_item(inv) for inv in inventories]
        return self.generate_report(items)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes the agent reasoning/processing loop implementing the BaseAgent interface.

        Supported context parameters:
        - {"db": Session, "product_id": int}: Evaluates and returns single product monitoring item.
        - {"db": Session, "skip": int, "limit": int}: Evaluates and returns full inventory report.
        - {"inventory": Inventory}: Evaluates pre-loaded Inventory instance directly.
        - {"inventories": List[Inventory]}: Evaluates list of pre-loaded Inventory instances.
        """
        db: Optional[Session] = context.get("db")
        product_id: Optional[int] = context.get("product_id")
        single_inv: Optional[Inventory] = context.get("inventory")
        inv_list: Optional[List[Inventory]] = context.get("inventories") or context.get("inventory_list")

        if single_inv is not None:
            item = self.evaluate_inventory_item(single_inv)
            return {
                "status": "success",
                "agent": self.agent_name,
                "item": item.model_dump(),
                "inventory_status": item.status.value,
            }

        if inv_list is not None:
            items = [self.evaluate_inventory_item(inv) for inv in inv_list]
            report = self.generate_report(items)
            return {
                "status": "success",
                "agent": self.agent_name,
                "report": report.model_dump(),
            }

        if db is not None:
            if product_id is not None:
                item = self.monitor_product(db=db, product_id=product_id)
                return {
                    "status": "success",
                    "agent": self.agent_name,
                    "item": item.model_dump(),
                    "inventory_status": item.status.value,
                }
            else:
                skip = context.get("skip", 0)
                limit = context.get("limit", 100)
                report = self.monitor_inventory(db=db, skip=skip, limit=limit)
                return {
                    "status": "success",
                    "agent": self.agent_name,
                    "report": report.model_dump(),
                }

        return {
            "status": "error",
            "agent": self.agent_name,
            "message": "Insufficient context provided for inventory monitoring. Must provide 'db', 'inventory', or 'inventories'.",
        }
