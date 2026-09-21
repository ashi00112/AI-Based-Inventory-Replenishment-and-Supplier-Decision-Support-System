from fastapi import APIRouter
from app.routers import health

api_router = APIRouter()

# Core system routes
api_router.include_router(health.router)

# Future agent routes to be added by team members:
# Developer 1: api_router.include_router(inventory.router, prefix="/inventory", tags=["Inventory Monitoring"])
# Developer 2: api_router.include_router(demand.router, prefix="/demand", tags=["Demand & Risk Analysis"])
# Developer 3: api_router.include_router(supplier.router, prefix="/supplier", tags=["Supplier Intelligence"])
# Developer 4: api_router.include_router(decision.router, prefix="/decision", tags=["Replenishment Decision"])
