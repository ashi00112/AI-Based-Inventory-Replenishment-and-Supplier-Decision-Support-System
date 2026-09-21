# Inventory Monitoring Agent (Developer 1)

## Responsibilities
- Monitor real-time stock levels, reorder thresholds, and safety stock requirements.
- Detect stockouts, overstocking, and anomalies in inventory balance.
- Emit replenishment triggers to the Replenishment Decision Agent.

## Associated Files (Recommended Convention)
- Agent Logic: `backend/app/agents/inventory/agent.py`
- Router: `backend/app/routers/inventory.py`
- Models: `backend/app/models/inventory.py`
- Schemas: `backend/app/schemas/inventory.py`
- Tests: `backend/tests/test_inventory.py`
