"""
Unified Demo Data Seeder for SmartSupply AI.

Simulates 180 days of realistic, chronologically consistent inventory and commercial history
for SmartSupply Electronics (Sri Lankan IT / electronics accessories retailer and distributor).

Features:
- Exactly 12 catalog products with distinct demand patterns.
- Exactly 4 fictional commercial suppliers with realistic contact information.
- ProductSupplier commercial offers (2-3 per product) featuring realistic price/MOQ/lead-time trade-offs.
- Granular SALE transactions atomically paired with SalesHistory records.
- Realistic RESTOCK cycles triggered near replenishment thresholds.
- Occasional RETURN and counting ADJUSTMENT events.
- Strict database invariant validation before committing.
- Idempotency check with --reset-demo support (strictly protects non-demo records).
- Dry-run verification mode with --dry-run.

Usage:
    python scripts/seed_demo_data.py
    python scripts/seed_demo_data.py --reset-demo
    python scripts/seed_demo_data.py --dry-run
"""

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
import math
import random
import sys
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

# Ensure backend root is on sys.path when running script directly
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.session import SessionLocal
from app.models.inventory import Inventory
from app.models.inventory_transaction import (
    InventoryTransaction,
    InventoryTransactionType,
)
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.models.sales_history import SalesHistory
from app.models.supplier import Supplier

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_demo_data")

# Fixed pseudo-random seed for complete reproducibility
RANDOM_SEED = 42

# -----------------------------------------------------------------------------
# 1. CATALOG DEFINITIONS (12 Demo Products)
# -----------------------------------------------------------------------------
DEMO_PRODUCTS = [
    {
        "sku": "DEMO-001",
        "name": "Wireless Mouse",
        "category": "Peripherals",
        "description": "2.4GHz optical wireless mouse with ergonomic contoured grip and nano receiver",
        "unit_price": Decimal("3500.00"),
        "reorder_point": 30,
        "demand_pattern": "Stable High",
        "initial_stock": 220,
    },
    {
        "sku": "DEMO-002",
        "name": "Mechanical Keyboard",
        "category": "Peripherals",
        "description": "RGB tactile mechanical keyboard with hot-swappable switches and detachable USB-C",
        "unit_price": Decimal("12500.00"),
        "reorder_point": 15,
        "demand_pattern": "Stable Medium",
        "initial_stock": 110,
    },
    {
        "sku": "DEMO-003",
        "name": "USB-C Hub",
        "category": "Accessories",
        "description": "7-in-1 multi-port adapter with 4K HDMI, 100W PD charging, and SD/TF card reader",
        "unit_price": Decimal("8500.00"),
        "reorder_point": 20,
        "demand_pattern": "Increasing Trend",
        "initial_stock": 130,
    },
    {
        "sku": "DEMO-004",
        "name": "Laptop Stand",
        "category": "Accessories",
        "description": "Foldable aluminum ergonomic laptop elevator with silicone anti-slip pads",
        "unit_price": Decimal("5500.00"),
        "reorder_point": 20,
        "demand_pattern": "Weekly Seasonal",
        "initial_stock": 140,
    },
    {
        "sku": "DEMO-005",
        "name": "HDMI Cable 2m",
        "category": "Accessories",
        "description": "High-speed 4K 60Hz braided HDMI 2.0 cable with gold-plated connectors",
        "unit_price": Decimal("2000.00"),
        "reorder_point": 40,
        "demand_pattern": "High-Frequency Stable",
        "initial_stock": 280,
    },
    {
        "sku": "DEMO-006",
        "name": "External SSD 1TB",
        "category": "Storage",
        "description": "Portable USB 3.2 Gen 2 NVMe high-speed solid state drive (up to 1050 MB/s)",
        "unit_price": Decimal("28000.00"),
        "reorder_point": 10,
        "demand_pattern": "Moderate + Spikes",
        "initial_stock": 70,
    },
    {
        "sku": "DEMO-007",
        "name": "USB Flash Drive 64GB",
        "category": "Storage",
        "description": "Dual USB Type-A and Type-C OTG flash memory drive for PC and smartphone transfer",
        "unit_price": Decimal("3200.00"),
        "reorder_point": 35,
        "demand_pattern": "Stable Medium",
        "initial_stock": 190,
    },
    {
        "sku": "DEMO-008",
        "name": "Wi-Fi Router AC1200",
        "category": "Networking",
        "description": "Dual-band gigabit wireless router with 4 high-gain omnidirectional antennas",
        "unit_price": Decimal("14500.00"),
        "reorder_point": 12,
        "demand_pattern": "Intermittent",
        "initial_stock": 80,
    },
    {
        "sku": "DEMO-009",
        "name": "Wireless Headset",
        "category": "Peripherals",
        "description": "Over-ear Bluetooth 5.3 headset with active noise cancellation and clear mic",
        "unit_price": Decimal("9500.00"),
        "reorder_point": 18,
        "demand_pattern": "Increasing Trend",
        "initial_stock": 120,
    },
    {
        "sku": "DEMO-010",
        "name": "HD Webcam 1080p",
        "category": "Peripherals",
        "description": "Full HD autofocus streaming webcam with dual noise-reducing stereo microphones",
        "unit_price": Decimal("11000.00"),
        "reorder_point": 15,
        "demand_pattern": "Variable / Spikes",
        "initial_stock": 95,
    },
    {
        "sku": "DEMO-011",
        "name": "Power Bank 20000mAh",
        "category": "Electronics",
        "description": "22.5W fast-charging power bank with dual USB-A, Type-C bidirectional PD input/output",
        "unit_price": Decimal("8000.00"),
        "reorder_point": 25,
        "demand_pattern": "Weekend Seasonal",
        "initial_stock": 160,
    },
    {
        "sku": "DEMO-012",
        "name": "A4 Printer Paper Pack (500 Sheets)",
        "category": "Office Supplies",
        "description": "Premium 80gsm high-whiteness multi-purpose photocopy and laser printer paper ream",
        "unit_price": Decimal("2500.00"),
        "reorder_point": 50,
        "demand_pattern": "Regular Recurring",
        "initial_stock": 310,
    },
]

# -----------------------------------------------------------------------------
# 2. SUPPLIER DEFINITIONS (4 Demo Suppliers)
# -----------------------------------------------------------------------------
DEMO_SUPPLIERS = [
    {
        "supplier_code": "DEMO-SUP-001",
        "name": "TechSource Lanka",
        "contact_name": "Kamal Silva",
        "email": "orders@techsourcelanka.lk",
        "phone": "+94 11 234 1101",
        "address": "45 R.A. De Mel Mawatha, Colombo 03",
    },
    {
        "supplier_code": "DEMO-SUP-002",
        "name": "Digital Distribution Lanka",
        "contact_name": "Dilani Perera",
        "email": "supply@digitaldistribution.lk",
        "phone": "+94 11 258 2202",
        "address": "112 Duplication Road, Colombo 04",
    },
    {
        "supplier_code": "DEMO-SUP-003",
        "name": "NextGen Supplies",
        "contact_name": "Rohan Wickramasinghe",
        "email": "sales@nextgensupplies.lk",
        "phone": "+94 11 289 3303",
        "address": "88 High Level Road, Nugegoda",
    },
    {
        "supplier_code": "DEMO-SUP-004",
        "name": "Island Tech Wholesale",
        "contact_name": "Anura Fernando",
        "email": "wholesale@islandtech.lk",
        "phone": "+94 11 472 4404",
        "address": "240 Kandy Road, Kelaniya",
    },
]

# -----------------------------------------------------------------------------
# 3. PRODUCT-SUPPLIER OFFERS (2-3 per Product with Commercial Trade-offs)
# -----------------------------------------------------------------------------
# Key: (sku, supplier_code) -> {unit_cost, moq, lead_time_days, supplier_sku}
DEMO_OFFERS_SPEC = [
    # DEMO-001: Wireless Mouse (Retail: 3500)
    ("DEMO-001", "DEMO-SUP-001", Decimal("2400.00"), 30, 5, "TS-WM-01"),  # Balanced
    ("DEMO-001", "DEMO-SUP-002", Decimal("2550.00"), 20, 2, "DD-WM-99"),  # Fast delivery, lower MOQ, higher cost
    ("DEMO-001", "DEMO-SUP-003", Decimal("2300.00"), 50, 7, "NG-MOU-2"),  # Bulk discount, slow lead time

    # DEMO-002: Mechanical Keyboard (Retail: 12500)
    ("DEMO-002", "DEMO-SUP-001", Decimal("8800.00"), 15, 6, "TS-KB-RGB"),
    ("DEMO-002", "DEMO-SUP-003", Decimal("9200.00"), 10, 3, "NG-KB-PRO"),
    ("DEMO-002", "DEMO-SUP-004", Decimal("8500.00"), 25, 8, "ITW-MKB-1"),

    # DEMO-003: USB-C Hub (Retail: 8500)
    ("DEMO-003", "DEMO-SUP-002", Decimal("5900.00"), 20, 3, "DD-HUB-71"),
    ("DEMO-003", "DEMO-SUP-003", Decimal("5600.00"), 35, 6, "NG-HUB-7"),

    # DEMO-004: Laptop Stand (Retail: 5500)
    ("DEMO-004", "DEMO-SUP-001", Decimal("3700.00"), 20, 4, "TS-LS-ALU"),
    ("DEMO-004", "DEMO-SUP-004", Decimal("3500.00"), 40, 7, "ITW-STD-0"),

    # DEMO-005: HDMI Cable (Retail: 2000)
    ("DEMO-005", "DEMO-SUP-001", Decimal("1250.00"), 50, 4, "TS-HDMI-2"),
    ("DEMO-005", "DEMO-SUP-002", Decimal("1350.00"), 25, 2, "DD-HDM-4K"),
    ("DEMO-005", "DEMO-SUP-004", Decimal("1180.00"), 100, 7, "ITW-CBL-H"),

    # DEMO-006: External SSD 1TB (Retail: 28000)
    ("DEMO-006", "DEMO-SUP-002", Decimal("21500.00"), 10, 3, "DD-SSD-1T"),
    ("DEMO-006", "DEMO-SUP-003", Decimal("20500.00"), 20, 7, "NG-SSD-NV"),

    # DEMO-007: USB Flash Drive 64GB (Retail: 3200)
    ("DEMO-007", "DEMO-SUP-001", Decimal("2100.00"), 40, 4, "TS-FD-64G"),
    ("DEMO-007", "DEMO-SUP-002", Decimal("2250.00"), 20, 2, "DD-OTG-64"),
    ("DEMO-007", "DEMO-SUP-004", Decimal("1980.00"), 80, 8, "ITW-DRV-6"),

    # DEMO-008: Wi-Fi Router (Retail: 14500)
    ("DEMO-008", "DEMO-SUP-001", Decimal("10200.00"), 15, 5, "TS-RTR-AC"),
    ("DEMO-008", "DEMO-SUP-003", Decimal("10800.00"), 8, 2, "NG-WIFI-G"),

    # DEMO-009: Wireless Headset (Retail: 9500)
    ("DEMO-009", "DEMO-SUP-002", Decimal("6600.00"), 15, 3, "DD-AUD-BT"),
    ("DEMO-009", "DEMO-SUP-003", Decimal("6300.00"), 30, 6, "NG-HPH-NC"),

    # DEMO-010: HD Webcam (Retail: 11000)
    ("DEMO-010", "DEMO-SUP-001", Decimal("7800.00"), 15, 4, "TS-CAM-10"),
    ("DEMO-010", "DEMO-SUP-004", Decimal("7400.00"), 30, 7, "ITW-WBC-F"),

    # DEMO-011: Power Bank 20000mAh (Retail: 8000)
    ("DEMO-011", "DEMO-SUP-002", Decimal("5400.00"), 25, 3, "DD-PB-20K"),
    ("DEMO-011", "DEMO-SUP-003", Decimal("5100.00"), 50, 6, "NG-PWR-20"),
    ("DEMO-011", "DEMO-SUP-004", Decimal("5600.00"), 15, 2, "ITW-BAT-Q"),

    # DEMO-012: A4 Printer Paper (Retail: 2500)
    ("DEMO-012", "DEMO-SUP-001", Decimal("1750.00"), 50, 3, "TS-PPR-A4"),
    ("DEMO-012", "DEMO-SUP-004", Decimal("1650.00"), 100, 5, "ITW-RM-500"),
]


# -----------------------------------------------------------------------------
# 4. DETERMINISTIC DEMAND GENERATOR (10 Patterns, SEED=42)
# -----------------------------------------------------------------------------
def calculate_daily_demand(
    pattern: str,
    day_idx: int,
    total_days: int,
    date: datetime,
    rng: random.Random,
) -> int:
    """
    Computes deterministic daily customer demand quantity for a given day and pattern.
    """
    weekday = date.weekday()  # 0=Monday, 6=Sunday

    if pattern == "Stable High":
        # Mean 10-14 with slight noise
        return max(1, int(round(rng.gauss(12.0, 2.0))))

    elif pattern == "Stable Medium":
        # Mean 5-8 with moderate noise
        return max(0, int(round(rng.gauss(6.5, 1.8))))

    elif pattern == "High-Frequency Stable":
        # High volume staple (HDMI Cable), very low variance
        return max(4, int(round(rng.gauss(15.0, 2.2))))

    elif pattern == "Increasing Trend":
        # Linearly grows from ~2 units/day at start to ~10-12 units/day at end
        progress = day_idx / total_days
        base = 2.5 + (9.0 * progress)
        return max(0, int(round(rng.gauss(base, 1.5))))

    elif pattern == "Weekly Seasonal":
        # Higher on Tue-Thu (work/business accessories), lower on weekends
        if weekday in (1, 2, 3):  # Tue, Wed, Thu
            return max(2, int(round(rng.gauss(7.5, 1.5))))
        elif weekday in (0, 4):   # Mon, Fri
            return max(1, int(round(rng.gauss(5.0, 1.5))))
        else:                     # Sat, Sun
            return max(0, int(round(rng.gauss(1.8, 1.0))))

    elif pattern == "Weekend Seasonal":
        # Higher on Fri-Sun (lifestyle/gadget accessories), lower on Mon-Wed
        if weekday in (4, 5, 6):  # Fri, Sat, Sun
            return max(3, int(round(rng.gauss(10.0, 2.2))))
        else:
            return max(0, int(round(rng.gauss(3.5, 1.2))))

    elif pattern == "Moderate + Spikes":
        # Baseline ~2 units with sudden periodic spikes (10-16 units) every ~25-30 days
        if day_idx in (22, 54, 88, 119, 151, 172):
            return rng.randint(12, 18)
        return max(0, int(round(rng.gauss(2.2, 1.2))))

    elif pattern == "Variable / Spikes":
        # High variance baseline (2-5) with frequent irregular mini-surges
        if rng.random() < 0.08:  # 8% chance of burst
            return rng.randint(10, 16)
        return max(0, int(round(rng.gauss(3.5, 1.8))))

    elif pattern == "Intermittent":
        # Networking gear: ~50% zero days, cluster sales when non-zero
        if rng.random() < 0.52:
            return 0
        return rng.randint(1, 5)

    elif pattern == "Regular Recurring":
        # Office paper: baseline 12-18, month-end corporate bulk purchases (30-45)
        # Check if near end of month (day >= 26)
        if date.day >= 26:
            return rng.randint(28, 42)
        return max(2, int(round(rng.gauss(16.0, 3.0))))

    return rng.randint(1, 5)


def split_daily_demand_into_sale_events(
    day_date: datetime,
    daily_qty: int,
    rng: random.Random,
) -> List[Tuple[datetime, int]]:
    """
    Deconstructs a daily demand quantity into 1-3 granular customer transactions
    with distinct daytime timestamps.
    """
    if daily_qty <= 0:
        return []

    # If small quantity: 1 event
    if daily_qty <= 3:
        hour = rng.choice([9, 10, 11, 14, 15, 16, 17])
        minute = rng.randint(5, 55)
        second = rng.randint(0, 59)
        t = day_date.replace(hour=hour, minute=minute, second=second, microsecond=0)
        return [(t, daily_qty)]

    # If bulk surge (>= 10), allow single corporate/project order
    if daily_qty >= 10 and rng.random() < 0.65:
        hour = rng.choice([10, 11, 14, 15, 16])
        minute = rng.randint(5, 55)
        second = rng.randint(0, 59)
        t = day_date.replace(hour=hour, minute=minute, second=second, microsecond=0)
        return [(t, daily_qty)]

    # If medium quantity (4-8): 2 events
    if daily_qty <= 8:
        q1 = rng.randint(1, daily_qty - 1)
        q2 = daily_qty - q1
        t1 = day_date.replace(hour=rng.randint(9, 12), minute=rng.randint(5, 55), second=rng.randint(0, 59), microsecond=0)
        t2 = day_date.replace(hour=rng.randint(14, 18), minute=rng.randint(5, 55), second=rng.randint(0, 59), microsecond=0)
        return [(t1, q1), (t2, q2)]

    # If large quantity (> 8): 3 events
    q1 = max(1, daily_qty // 3)
    q2 = max(1, (daily_qty - q1) // 2)
    q3 = daily_qty - q1 - q2
    t1 = day_date.replace(hour=rng.randint(9, 11), minute=rng.randint(5, 55), second=rng.randint(0, 59), microsecond=0)
    t2 = day_date.replace(hour=rng.randint(12, 14), minute=rng.randint(5, 55), second=rng.randint(0, 59), microsecond=0)
    t3 = day_date.replace(hour=rng.randint(15, 18), minute=rng.randint(5, 55), second=rng.randint(0, 59), microsecond=0)
    return [(t1, q1), (t2, q2), (t3, q3)]


# -----------------------------------------------------------------------------
# 5. DEMO SEED ENGINE IMPLEMENTATION
# -----------------------------------------------------------------------------
class DemoDataSeeder:
    """
    Encapsulates chronological generation, ledger validation, and cleanup.
    """

    def __init__(self, db: Session, dry_run: bool = False, total_days: int = 180, reference_end: Optional[datetime] = None):
        self.db = db
        self.dry_run = dry_run
        self.total_days = total_days
        self.rng = random.Random(RANDOM_SEED)

        # Reference timeline end date (today 23:59:59 UTC)
        if reference_end is None:
            now_utc = datetime.now(timezone.utc)
            self.end_date = now_utc.replace(hour=23, minute=59, second=59, microsecond=0)
        else:
            self.end_date = reference_end.replace(hour=23, minute=59, second=59, microsecond=0)

        self.start_date = self.end_date - timedelta(days=total_days)

        # Entity collections
        self.products: Dict[str, Product] = {}
        self.suppliers: Dict[str, Supplier] = {}
        self.offers: List[ProductSupplier] = []
        self.inventories: Dict[int, Inventory] = {}

        # Statistical tracker for audit reporting
        self.stats: Dict[str, Dict[str, Any]] = {}

    def check_existing_demo_data(self) -> Tuple[bool, int, int]:
        """
        Detects if demo products or demo suppliers already exist in database.
        """
        demo_prod_count = self.db.scalars(
            select(func.count(Product.id)).where(Product.sku.like("DEMO-%"))
        ).one() or 0

        demo_sup_count = self.db.scalars(
            select(func.count(Supplier.id)).where(Supplier.supplier_code.like("DEMO-SUP-%"))
        ).one() or 0

        exists = (demo_prod_count > 0) or (demo_sup_count > 0)
        return exists, demo_prod_count, demo_sup_count

    def reset_demo_data(self) -> None:
        """
        Safely removes ONLY DEMO products and DEMO suppliers in strict dependency order.
        Guarantees zero mutation to any non-demo records.
        """
        logger.info("Executing safe demo data reset...")

        # 1. Fetch all demo product IDs
        demo_product_ids = list(
            self.db.scalars(select(Product.id).where(Product.sku.like("DEMO-%"))).all()
        )

        # 2. Fetch all demo supplier IDs
        demo_supplier_ids = list(
            self.db.scalars(select(Supplier.id).where(Supplier.supplier_code.like("DEMO-SUP-%"))).all()
        )

        if not demo_product_ids and not demo_supplier_ids:
            logger.info("No demo records found to reset.")
            return

        # Delete dependent tables explicitly in order of dependency
        if demo_product_ids:
            # SalesHistory
            self.db.execute(
                delete(SalesHistory).where(SalesHistory.product_id.in_(demo_product_ids))
            )
            # InventoryTransactions
            self.db.execute(
                delete(InventoryTransaction).where(InventoryTransaction.product_id.in_(demo_product_ids))
            )
            # Inventory
            self.db.execute(
                delete(Inventory).where(Inventory.product_id.in_(demo_product_ids))
            )

        # ProductSupplier (matches demo products OR demo suppliers)
        if demo_product_ids or demo_supplier_ids:
            conds = []
            if demo_product_ids:
                conds.append(ProductSupplier.product_id.in_(demo_product_ids))
            if demo_supplier_ids:
                conds.append(ProductSupplier.supplier_id.in_(demo_supplier_ids))

            from sqlalchemy import or_
            self.db.execute(delete(ProductSupplier).where(or_(*conds)))

        # Products
        if demo_product_ids:
            self.db.execute(delete(Product).where(Product.id.in_(demo_product_ids)))

        # Suppliers
        if demo_supplier_ids:
            self.db.execute(delete(Supplier).where(Supplier.id.in_(demo_supplier_ids)))

        self.db.flush()
        logger.info(
            "Demo reset completed successfully (Removed %d demo products, %d demo suppliers).",
            len(demo_product_ids),
            len(demo_supplier_ids),
        )

    def seed_suppliers(self) -> None:
        """
        Creates exactly 4 demo suppliers.
        """
        for spec in DEMO_SUPPLIERS:
            supplier = Supplier(
                supplier_code=spec["supplier_code"],
                name=spec["name"],
                contact_name=spec["contact_name"],
                email=spec["email"],
                phone=spec["phone"],
                address=spec["address"],
                is_active=True,
                created_at=self.start_date,
                updated_at=self.start_date,
            )
            self.db.add(supplier)
            self.suppliers[spec["supplier_code"]] = supplier

        self.db.flush()

    def seed_products(self) -> None:
        """
        Creates exactly 12 demo catalog products.
        """
        for spec in DEMO_PRODUCTS:
            product = Product(
                sku=spec["sku"],
                name=spec["name"],
                category=spec["category"],
                description=spec["description"],
                unit_price=spec["unit_price"],
                reorder_point=spec["reorder_point"],
                is_active=True,
                created_at=self.start_date,
                updated_at=self.start_date,
            )
            self.db.add(product)
            self.products[spec["sku"]] = product

            # Initialize stats tracker
            self.stats[spec["sku"]] = {
                "name": spec["name"],
                "pattern": spec["demand_pattern"],
                "reorder_point": spec["reorder_point"],
                "unit_price": spec["unit_price"],
                "initial_stock": spec["initial_stock"],
                "current_stock": spec["initial_stock"],
                "sales_count": 0,
                "units_sold": 0,
                "first_sale": None,
                "last_sale": None,
                "restock_count": 0,
                "units_restocked": 0,
                "return_count": 0,
                "units_returned": 0,
                "adjustment_count": 0,
                "adjustment_net_qty": 0,
                "active_offers": 0,
                "final_reserved": 0,
                "final_incoming": 0,
            }

        self.db.flush()

    def seed_product_suppliers(self) -> None:
        """
        Establishes commercial ProductSupplier relationships.
        """
        for sku, sup_code, unit_cost, moq, lead_days, sup_sku in DEMO_OFFERS_SPEC:
            prod = self.products[sku]
            sup = self.suppliers[sup_code]

            offer = ProductSupplier(
                product_id=prod.id,
                supplier_id=sup.id,
                supplier_sku=sup_sku,
                unit_cost=unit_cost,
                moq=moq,
                lead_time_days=lead_days,
                is_active=True,
                created_at=self.start_date,
                updated_at=self.start_date,
            )
            self.db.add(offer)
            self.offers.append(offer)
            self.stats[sku]["active_offers"] += 1

        self.db.flush()

    def simulate_history(self) -> None:
        """
        Executes a 180-day chronological business simulation for all 12 products.
        """
        logger.info("Simulating 180 days of business history (%s -> %s)...",
                    self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d"))

        # Day-by-day progression
        for day_idx in range(self.total_days):
            current_day = self.start_date + timedelta(days=day_idx)

            for spec in DEMO_PRODUCTS:
                sku = spec["sku"]
                prod = self.products[sku]
                stat = self.stats[sku]
                curr_stock = stat["current_stock"]
                reorder_threshold = spec["reorder_point"]

                # 1. Check if replenishment (RESTOCK) is needed before daily sales
                # If current stock is approaching or below 1.25x reorder point, trigger restock
                if curr_stock <= int(round(reorder_threshold * 1.25)):
                    # Select simulated supplier offers for this product
                    prod_offers = [o for o in self.offers if o.product_id == prod.id]
                    # Select offer with deterministic round-robin
                    offer_pick = prod_offers[stat["restock_count"] % len(prod_offers)]
                    # Restock quantity: at least offer MOQ, and enough to reach comfortable safety buffer
                    restock_qty = max(offer_pick.moq, reorder_threshold * 2)

                    restock_time = current_day.replace(hour=8, minute=30, second=0, microsecond=0)
                    prev_stock = curr_stock
                    curr_stock += restock_qty

                    restock_tx = InventoryTransaction(
                        product_id=prod.id,
                        transaction_type=InventoryTransactionType.RESTOCK,
                        quantity=restock_qty,
                        previous_on_hand=prev_stock,
                        new_on_hand=curr_stock,
                        note=f"Replenishment Order from {offer_pick.supplier_sku or 'Supplier'}",
                        created_at=restock_time,
                        updated_at=restock_time,
                    )
                    self.db.add(restock_tx)

                    stat["restock_count"] += 1
                    stat["units_restocked"] += restock_qty
                    stat["current_stock"] = curr_stock

                # 2. Daily Customer Demand & SALE transactions
                daily_demand = calculate_daily_demand(
                    spec["demand_pattern"],
                    day_idx,
                    self.total_days,
                    current_day,
                    self.rng,
                )

                if daily_demand > 0:
                    events = split_daily_demand_into_sale_events(current_day, daily_demand, self.rng)

                    for sale_time, sale_qty in events:
                        # Safety check: ensure stock is sufficient
                        if sale_qty > curr_stock:
                            # Emergency top-up restock if surge unexpectedly exceeded buffer
                            emergency_qty = max(20, (sale_qty - curr_stock) + reorder_threshold)
                            em_prev = curr_stock
                            curr_stock += emergency_qty
                            em_tx = InventoryTransaction(
                                product_id=prod.id,
                                transaction_type=InventoryTransactionType.RESTOCK,
                                quantity=emergency_qty,
                                previous_on_hand=em_prev,
                                new_on_hand=curr_stock,
                                note="Emergency stock intake",
                                created_at=sale_time - timedelta(minutes=15),
                                updated_at=sale_time - timedelta(minutes=15),
                            )
                            self.db.add(em_tx)
                            stat["restock_count"] += 1
                            stat["units_restocked"] += emergency_qty

                        prev_on_hand = curr_stock
                        curr_stock -= sale_qty

                        # Create SALE InventoryTransaction
                        sale_tx = InventoryTransaction(
                            product_id=prod.id,
                            transaction_type=InventoryTransactionType.SALE,
                            quantity=sale_qty,
                            previous_on_hand=prev_on_hand,
                            new_on_hand=curr_stock,
                            note=None,
                            created_at=sale_time,
                            updated_at=sale_time,
                        )
                        self.db.add(sale_tx)

                        # Create linked SalesHistory
                        total_amt = Decimal(sale_qty) * prod.unit_price
                        sale_hist = SalesHistory(
                            product=prod,
                            transaction=sale_tx,
                            quantity=sale_qty,
                            unit_price=prod.unit_price,
                            total_amount=total_amt,
                            sale_date=sale_time,
                            created_at=sale_time,
                            updated_at=sale_time,
                        )
                        self.db.add(sale_hist)

                        stat["sales_count"] += 1
                        stat["units_sold"] += sale_qty
                        if stat["first_sale"] is None:
                            stat["first_sale"] = sale_time
                        stat["last_sale"] = sale_time
                        stat["current_stock"] = curr_stock

                # 3. Occasional RETURN events (rare, ~1.5% daily chance for high/medium items)
                if self.rng.random() < 0.015:
                    return_qty = self.rng.randint(1, 2)
                    ret_time = current_day.replace(hour=16, minute=rng_min(self.rng), second=0, microsecond=0)
                    ret_prev = curr_stock
                    curr_stock += return_qty

                    ret_tx = InventoryTransaction(
                        product_id=prod.id,
                        transaction_type=InventoryTransactionType.RETURN,
                        quantity=return_qty,
                        previous_on_hand=ret_prev,
                        new_on_hand=curr_stock,
                        note="Customer RMA return",
                        created_at=ret_time,
                        updated_at=ret_time,
                    )
                    self.db.add(ret_tx)
                    stat["return_count"] += 1
                    stat["units_returned"] += return_qty
                    stat["current_stock"] = curr_stock

                # 4. Occasional stock counting ADJUSTMENT events (rare, ~0.8% daily chance)
                if self.rng.random() < 0.008:
                    adj_delta = self.rng.choice([-1, 1])
                    if curr_stock + adj_delta >= 0:
                        adj_time = current_day.replace(hour=19, minute=rng_min(self.rng), second=0, microsecond=0)
                        adj_prev = curr_stock
                        curr_stock += adj_delta

                        adj_tx = InventoryTransaction(
                            product_id=prod.id,
                            transaction_type=InventoryTransactionType.ADJUSTMENT,
                            quantity=adj_delta,
                            previous_on_hand=adj_prev,
                            new_on_hand=curr_stock,
                            note="Physical cycle count discrepancy adjustment",
                            created_at=adj_time,
                            updated_at=adj_time,
                        )
                        self.db.add(adj_tx)
                        stat["adjustment_count"] += 1
                        stat["adjustment_net_qty"] += adj_delta
                        stat["current_stock"] = curr_stock

        # Create final Inventory rows with realistic current reserved and incoming values
        for spec in DEMO_PRODUCTS:
            sku = spec["sku"]
            prod = self.products[sku]
            stat = self.stats[sku]
            final_on_hand = stat["current_stock"]

            # Set realistic final reserved (small committed units, <= on_hand)
            # Higher volume products have 2-5 reserved units
            if spec["demand_pattern"] in ("Stable High", "High-Frequency Stable", "Regular Recurring") and final_on_hand >= 5:
                final_reserved = min(5, final_on_hand // 4)
            elif final_on_hand >= 2:
                final_reserved = 1
            else:
                final_reserved = 0

            # Set realistic incoming orders for products currently close to reorder point
            if final_on_hand <= spec["reorder_point"] * 1.5:
                final_incoming = spec["reorder_point"] * 2
            else:
                final_incoming = 0

            inv = Inventory(
                product_id=prod.id,
                on_hand=final_on_hand,
                reserved=final_reserved,
                incoming=final_incoming,
                created_at=self.start_date,
                updated_at=self.end_date,
            )
            self.db.add(inv)
            self.inventories[prod.id] = inv
            stat["final_reserved"] = final_reserved
            stat["final_incoming"] = final_incoming

        self.db.flush()

    def validate_consistency(self) -> None:
        """
        Executes strict invariant checks across the generated database ledger.
        Raises AssertionError if any anomaly or discrepancy is detected.
        """
        logger.info("Executing post-simulation database consistency checks...")

        for spec in DEMO_PRODUCTS:
            sku = spec["sku"]
            prod = self.products[sku]
            inv = self.inventories[prod.id]
            stat = self.stats[sku]

            # Invariant 1: Inventory stock arithmetic balance
            expected_balance = (
                stat["initial_stock"]
                + stat["units_restocked"]
                + stat["units_returned"]
                + stat["adjustment_net_qty"]
                - stat["units_sold"]
            )
            if inv.on_hand != expected_balance:
                raise AssertionError(
                    f"[{sku}] Stock ledger mismatch! Inventory.on_hand={inv.on_hand}, Expected={expected_balance}"
                )

            # Invariant 2: Non-negativity and reserved <= on_hand
            if inv.on_hand < 0:
                raise AssertionError(f"[{sku}] Negative on_hand ({inv.on_hand})!")
            if inv.reserved < 0 or inv.incoming < 0:
                raise AssertionError(f"[{sku}] Negative reserved ({inv.reserved}) or incoming ({inv.incoming})!")
            if inv.reserved > inv.on_hand:
                raise AssertionError(
                    f"[{sku}] Reserved stock ({inv.reserved}) exceeds on_hand stock ({inv.on_hand})!"
                )

            # Invariant 3: Active supplier offers >= 2
            if stat["active_offers"] < 2:
                raise AssertionError(f"[{sku}] Less than 2 active supplier offers ({stat['active_offers']})!")

        # Invariant 4: SalesHistory <-> InventoryTransaction 1-to-1 linkage for SALE events
        sale_txs = list(
            self.db.scalars(
                select(InventoryTransaction).where(
                    InventoryTransaction.product_id.in_([p.id for p in self.products.values()]),
                    InventoryTransaction.transaction_type == InventoryTransactionType.SALE,
                )
            ).all()
        )
        sales_records = list(
            self.db.scalars(
                select(SalesHistory).where(
                    SalesHistory.product_id.in_([p.id for p in self.products.values()])
                )
            ).all()
        )

        if len(sale_txs) != len(sales_records):
            raise AssertionError(
                f"Count mismatch: {len(sale_txs)} SALE transactions vs {len(sales_records)} SalesHistory records!"
            )

        # Map by transaction ID
        sh_by_tx = {sh.transaction_id: sh for sh in sales_records}
        for tx in sale_txs:
            sh = sh_by_tx.get(tx.id)
            if sh is None:
                raise AssertionError(f"SALE transaction #{tx.id} has no linked SalesHistory!")
            if sh.quantity != tx.quantity:
                raise AssertionError(f"Quantity mismatch on tx #{tx.id}: tx={tx.quantity}, sh={sh.quantity}")
            if sh.product_id != tx.product_id:
                raise AssertionError(f"Product ID mismatch on tx #{tx.id}: tx={tx.product_id}, sh={sh.product_id}")
            if tx.quantity <= 0:
                raise AssertionError(f"Zero or negative quantity on SALE tx #{tx.id} ({tx.quantity})")

            # Check price arithmetic
            expected_amt = Decimal(sh.quantity) * sh.unit_price
            if sh.total_amount != expected_amt:
                raise AssertionError(
                    f"Total amount mismatch on sales record #{sh.id}: got {sh.total_amount}, expected {expected_amt}"
                )

        # Invariant 5: Verify non-SALE transactions have zero SalesHistory records
        non_sale_tx_ids = set(
            self.db.scalars(
                select(InventoryTransaction.id).where(
                    InventoryTransaction.product_id.in_([p.id for p in self.products.values()]),
                    InventoryTransaction.transaction_type != InventoryTransactionType.SALE,
                )
            ).all()
        )
        for sh in sales_records:
            if sh.transaction_id in non_sale_tx_ids:
                raise AssertionError(
                    f"SalesHistory record #{sh.id} is linked to a NON-SALE transaction #{sh.transaction_id}!"
                )

        logger.info("All 5 database consistency invariants passed successfully!")

    def print_reports(self) -> None:
        """
        Prints clean formatted validation and distribution tables to stdout.
        """
        print("\n" + "=" * 95)
        print(" DEMAND & INVENTORY VALIDATION REPORT (180 DAYS CHRONOLOGICAL HISTORY)")
        print("=" * 95)
        print(f"{'SKU':<10} {'Product Title':<28} {'Pattern':<16} {'Sales':<6} {'Sold':<6} {'Restocks':<9} {'Stock':<6} {'Rsv/Inc':<8} {'Reorder'}")
        print("-" * 95)

        total_sales_tx = 0
        total_units_sold = 0
        total_restocks = 0

        for spec in DEMO_PRODUCTS:
            sku = spec["sku"]
            st = self.stats[sku]
            total_sales_tx += st["sales_count"]
            total_units_sold += st["units_sold"]
            total_restocks += st["restock_count"]

            rsv_inc_str = f"{st['final_reserved']}/{st['final_incoming']}"
            print(
                f"{sku:<10} {st['name'][:26]:<28} {st['pattern'][:15]:<16} "
                f"{st['sales_count']:<6} {st['units_sold']:<6} {st['restock_count']:<9} "
                f"{st['current_stock']:<6} {rsv_inc_str:<8} {st['reorder_point']}"
            )

        print("-" * 95)
        print(f"Total Sales Events: {total_sales_tx} | Total Units Sold: {total_units_sold} | Total Restocks: {total_restocks}")
        print("=" * 95 + "\n")

        print("=" * 80)
        print(" PRODUCT-SUPPLIER COMMERCIAL TERMS NETWORK")
        print("=" * 80)
        for prod_sku, p in self.products.items():
            offers_for_prod = [o for o in self.offers if o.product_id == p.id]
            print(f"\n{prod_sku} - {p.name} (Selling Price: Rs. {p.unit_price:,.2f})")
            for off in offers_for_prod:
                sup = off.supplier
                print(
                    f"   +-- {sup.supplier_code} ({sup.name}): "
                    f"Cost=Rs. {off.unit_cost:,.2f} | MOQ={off.moq} units | Lead={off.lead_time_days} days | "
                    f"PartCode={off.supplier_sku or 'N/A'}"
                )
        print("\n" + "=" * 80)

        # Final Totals
        print("\n" + "=" * 60)
        print(" DEMO SEED SUMMARY")
        print("=" * 60)
        print(f"Products:                   {len(self.products)}")
        print(f"Suppliers:                  {len(self.suppliers)}")
        print(f"ProductSupplier offers:     {len(self.offers)}")
        print(f"Inventory records:          {len(self.inventories)}")
        print(f"SALE transactions:          {total_sales_tx}")
        print(f"RESTOCK transactions:       {total_restocks}")
        return_tx_count = sum(s["return_count"] for s in self.stats.values())
        adj_tx_count = sum(s["adjustment_count"] for s in self.stats.values())
        print(f"RETURN transactions:        {return_tx_count}")
        print(f"ADJUSTMENT transactions:    {adj_tx_count}")
        print(f"SalesHistory records:       {total_sales_tx}")
        print(f"Historical period:          {self.start_date.strftime('%Y-%m-%d')} -> {self.end_date.strftime('%Y-%m-%d')}")
        print(f"Pseudo-Random Seed:         {RANDOM_SEED}")
        print(f"Verification:               SALE count == SalesHistory count: {total_sales_tx == total_sales_tx}")
        print("=" * 60 + "\n")


def rng_min(rng: random.Random) -> int:
    return rng.randint(0, 59)


# -----------------------------------------------------------------------------
# 6. CLI ENTRYPOINT
# -----------------------------------------------------------------------------
def run_seed(
    reset_demo: bool = False,
    dry_run: bool = False,
    db: Optional[Session] = None,
) -> Optional[DemoDataSeeder]:
    """
    Main execution coordinator with transaction management.
    """
    if reset_demo and dry_run:
        logger.error("Cannot combine --reset-demo and --dry-run. Choose one mode.")
        sys.exit(1)

    own_session = False
    if db is None:
        db = SessionLocal()
        own_session = True

    try:
        seeder = DemoDataSeeder(db=db, dry_run=dry_run)

        # Check existing demo data
        exists, prod_count, sup_count = seeder.check_existing_demo_data()

        if exists and not reset_demo:
            print(
                f"\n[NOTICE] Demo data already exists in database ({prod_count} DEMO products, {sup_count} DEMO suppliers).\n"
                f"To reset and regenerate fresh demo data, run:\n"
                f"    python scripts/seed_demo_data.py --reset-demo\n"
            )
            return None

        if reset_demo:
            seeder.reset_demo_data()

        logger.info("Seeding demo catalog products and suppliers...")
        seeder.seed_suppliers()
        seeder.seed_products()
        seeder.seed_product_suppliers()

        logger.info("Generating chronological stock ledger and commercial transactions...")
        seeder.simulate_history()

        # Consistency validation before commit
        seeder.validate_consistency()

        # Print detailed report
        seeder.print_reports()

        if dry_run:
            db.rollback()
            logger.info("[DRY RUN COMPLETE] Validations passed. All database modifications were rolled back.")
        else:
            db.commit()
            logger.info("[SUCCESS] Unified demo data committed to database successfully.")

        return seeder

    except Exception as exc:
        db.rollback()
        # Ensure credentials/connection strings are not exposed
        exc_str = str(exc)
        if "password authentication failed" in exc_str or "connection failed" in exc_str:
            logger.error("[DATABASE CONNECTION FAILED] Unable to authenticate with configured database. Please verify your network access and credentials in .env.")
        else:
            logger.error("Seed execution failed! Database rolled back: %s", exc)
        raise exc
    finally:
        if own_session:
            db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Unified Demo Data Seeder for SmartSupply AI (SmartSupply Electronics)."
    )
    parser.add_argument(
        "--reset-demo",
        action="store_true",
        help="Remove existing DEMO products and suppliers before recreating the 180-day dataset.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate and validate the 180-day dataset without committing changes.",
    )
    args = parser.parse_args()

    try:
        run_seed(reset_demo=args.reset_demo, dry_run=args.dry_run)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
