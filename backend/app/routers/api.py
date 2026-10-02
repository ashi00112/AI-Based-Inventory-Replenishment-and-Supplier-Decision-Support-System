from fastapi import APIRouter
from app.routers import auth, demand, health, inventory, inventory_transactions, product

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

# Agent routes
api_router.include_router(demand.router, prefix="/demand", tags=["Demand & Risk Analysis"])
