from fastapi import APIRouter

from app.routers import (
    auth,
    demand,
    documents,
    health,
    inventory,
    inventory_transactions,
    product,
    product_suppliers,
    retrieval,
    supplier_agent,
    supplier_knowledge,
    suppliers,
)

api_router = APIRouter()

# Core system routes
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

api_router.include_router(
    product.router,
    prefix="/products",
    tags=["Product Management"],
)

api_router.include_router(
    inventory.router,
    prefix="/inventory",
    tags=["Inventory Management"],
)

api_router.include_router(
    inventory_transactions.router,
    prefix="/inventory-transactions",
    tags=["Inventory Transactions"],
)

api_router.include_router(
    suppliers.router,
    prefix="/suppliers",
    tags=["Supplier Management"],
)

api_router.include_router(
    product_suppliers.router,
    prefix="/product-suppliers",
    tags=["Product Supplier Offers"],
)

# Document / IR routes
api_router.include_router(
    retrieval.router,
    prefix="/documents",
    tags=["Document Retrieval"],
)

api_router.include_router(
    documents.router,
    prefix="/documents",
    tags=["Document Management"],
)

# Member 3 Supplier Knowledge / Agent routes
api_router.include_router(
    supplier_knowledge.router,
    prefix="/supplier-knowledge",
    tags=["Supplier Knowledge"],
)

api_router.include_router(
    supplier_agent.router,
    tags=["Supplier Agent"],
)

# Member 2 Demand & Risk routes
api_router.include_router(
    demand.router,
    prefix="/demand",
    tags=["Demand & Risk Analysis"],
)