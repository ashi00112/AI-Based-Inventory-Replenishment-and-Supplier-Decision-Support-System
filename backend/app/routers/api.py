from fastapi import APIRouter
from app.routers import (
    auth,
    documents,
    health,
    inventory,
    inventory_transactions,
    product,
    product_suppliers,
    suppliers,
    retrieval,
    supplier_knowledge,
    supplier_agent,
)

api_router = APIRouter()

# Core system routes
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(product.router, prefix="/products", tags=["Product Management"])
api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory Management"])
api_router.include_router(
    inventory_transactions.router,
    prefix="/inventory-transactions",
    tags=["Inventory Transactions"],
)
api_router.include_router(suppliers.router, prefix="/suppliers", tags=["Supplier Management"])
api_router.include_router(
    product_suppliers.router,
    prefix="/product-suppliers",
    tags=["Product Supplier Offers"],
)
api_router.include_router(retrieval.router, prefix="/documents", tags=["Document Retrieval"])
api_router.include_router(documents.router, prefix="/documents", tags=["Document Management"])
api_router.include_router(
    supplier_knowledge.router,
    prefix="/supplier-knowledge",
    tags=["Supplier Knowledge"],
)
api_router.include_router(supplier_agent.router, tags=["Supplier Agent"])





# Future agent routes to be added by team members:
# Developer 1: api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory Monitoring"])
# Developer 2: api_router.include_router(demand.router, prefix="/demand", tags=["Demand & Risk Analysis"])
# Developer 3: api_router.include_router(supplier.router, prefix="/supplier", tags=["Supplier Intelligence"])
# Developer 4: api_router.include_router(decision.router, prefix="/decision", tags=["Replenishment Decision"])
