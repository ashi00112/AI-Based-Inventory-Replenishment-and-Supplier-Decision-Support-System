# AI-Based Inventory Replenishment and Supplier Decision Support System

A shared monorepo foundation for an AI-driven inventory replenishment and supplier decision support platform developed as a 4-member university team project.

---

## Tech Stack

| Domain | Technologies |
|---|---|
| **Frontend** | React 18, Vite, Tailwind CSS, Lucide Icons |
| **Backend** | Python 3.10+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (Psycopg 3) |
| **Database** | Supabase-hosted PostgreSQL (Cloud) |
| **Migrations** | Alembic |
| **Testing** | pytest, httpx, TestClient |

---

## Target Architecture

```text
React Frontend (Vite)
       │ (HTTP / JSON)
       ▼
FastAPI Backend
       │ (SQLAlchemy 2.0 ORM / Alembic)
       ▼
Supabase-hosted PostgreSQL
```

- **FastAPI** remains our primary application server and API runtime.
- **Supabase** is utilized solely as our managed PostgreSQL cloud database and browser-based database management dashboard.
- We do **not** use Supabase Auth or client SDKs at this stage.

---

## 4-Member Agent Architecture Overview

The system architecture is structured so that 4 developers can develop their respective agent modules concurrently without merge conflicts:

| Member | Agent Focus | Primary Backend Directory | Router / Models |
|---|---|---|---|
| **Developer 1** | **Inventory Monitoring Agent** | `backend/app/agents/inventory/` | `routers/inventory.py`, `models/inventory.py` |
| **Developer 2** | **Demand & Risk Analysis Agent** | `backend/app/agents/demand/` | `routers/demand.py`, `models/demand.py` |
| **Developer 3** | **Supplier Intelligence Agent** | `backend/app/agents/supplier/` | `routers/supplier.py`, `models/supplier.py` |
| **Developer 4** | **Replenishment Decision Agent** | `backend/app/agents/decision/` | `routers/decision.py`, `models/decision.py` |

> **Notice**: Business logic, demand forecasting models, RAG document pipelines, and LLM integrations will be implemented in subsequent project phases. This repository provides the shared, verified development foundation.

---

## Repository Structure

```text
irwa-project/
├── .env.example
├── .gitignore
├── README.md
│
├── backend/
│   ├── .env.example
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/           # Configuration & environment settings
│   │   ├── database/       # SQLAlchemy engine & session dependency
│   │   ├── models/         # Database models inheriting Base
│   │   ├── schemas/        # Pydantic schemas for request/response
│   │   ├── routers/        # FastAPI route controllers
│   │   ├── services/       # Domain business services
│   │   ├── agents/         # 4 Agent workspaces
│   │   │   ├── base.py
│   │   │   ├── inventory/
│   │   │   ├── demand/
│   │   │   ├── supplier/
│   │   │   └── decision/
│   │   ├── retrieval/      # Document & knowledge base loaders
│   │   └── utils/          # Shared helper functions
│   └── tests/              # Pytest automated test suite
│
├── frontend/               # React + Vite + Tailwind CSS dashboard
│   ├── .env.example
│   ├── src/
│   │   ├── components/     # UI components (SystemStatus)
│   │   ├── services/       # API clients
│   │   ├── App.jsx
│   │   └── index.css
│   ├── package.json
│   └── vite.config.js
│
├── data/
│   └── sample/             # Mock datasets for local development
│
└── documents/
    ├── policies/           # Inventory & safety stock policies
    └── suppliers/          # Supplier SLAs and contract documents
```

---

## Prerequisites

Before starting, ensure you have installed:
- [Python 3.10+](https://www.python.org/)
- [Node.js 18+ and npm](https://nodejs.org/)
- [Git](https://git-scm.com/)
- Access to the team's shared **Supabase project** (or your own free Supabase account).

---

## Quickstart Setup Guide (For Team Members)

### 1. Clone Repository
```bash
git clone https://github.com/<your-org>/irwa-project.git
cd irwa-project
```

### 2. Obtain Supabase PostgreSQL Connection String
1. Log in to the [Supabase Dashboard](https://supabase.com/dashboard).
2. Open your project and navigate to:
   **Project Settings** ➔ **Database** ➔ **Connection string** ➔ **URI**.
3. Select the **Session** or **Transaction** connection mode (port `6543`) or Direct Connection (port `5432`).
4. The URI format will look like:
   ```text
   postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
   ```
5. Prefix with `postgresql+psycopg://` to use the Psycopg 3 driver:
   ```text
   postgresql+psycopg://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require
   ```

### 3. Configure Environment Files
Copy the `.env.example` templates into `.env` (never commit real `.env` files):

**Windows (PowerShell):**
```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

**macOS / Linux:**
```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Open `backend/.env` in your editor and paste your Supabase PostgreSQL connection string into `DATABASE_URL`:
```env
DATABASE_URL=postgresql+psycopg://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres?sslmode=require
```

### 4. Setup & Run Backend

In a terminal window:
```bash
cd backend

# Create Python virtual environment
python -m venv venv

# Activate virtual environment:
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (Command Prompt):
# .\venv\Scripts\activate.bat
# macOS / Linux:
# source venv/bin/activate

# Install dependencies (includes FastAPI, SQLAlchemy, Alembic, psycopg)
pip install -r requirements.txt -r requirements-dev.txt

# Run initial database migration against Supabase
alembic upgrade head

# Run automated tests
pytest

# Start the FastAPI development server
uvicorn app.main:app --reload --port 8000
```

Once running:
- **API Health Check**: [http://localhost:8000/health](http://localhost:8000/health) (pings Supabase PostgreSQL and returns status)
- **Interactive Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 5. Setup & Run Frontend

In a separate terminal window:
```bash
cd frontend

# Install Node dependencies
npm install

# Start Vite dev server
npm run dev
```

Once running, navigate to [http://localhost:5173](http://localhost:5173) in your web browser. You will see the system dashboard displaying live connectivity to your FastAPI backend and Supabase-hosted database.

---

## Recommended Git Branching Workflow

To maintain code quality and prevent merge conflicts across 4 team members:

```text
main           (Production / Releases - strictly protected)
  ▲
develop        (Integration branch - all PRs target here)
  ▲
feat/<topic>   (Individual developer feature branches)
```

### Branch Naming Conventions
- Developer 1: `feat/inventory-<feature-name>`
- Developer 2: `feat/demand-<feature-name>`
- Developer 3: `feat/supplier-<feature-name>`
- Developer 4: `feat/decision-<feature-name>`
- Bug fixes: `fix/<issue-name>`
- Shared chores/config: `chore/<description>`

### Development Workflow Steps
1. **Always pull latest `develop` before starting work**:
   ```bash
   git checkout develop
   git pull origin develop
   ```
2. **Create your feature branch**:
   ```bash
   git checkout -b feat/inventory-stock-tracking
   ```
3. **Commit often with clear messages**:
   ```bash
   git commit -m "feat(inventory): implement stock level Pydantic schema"
   ```
4. **Push branch and open a Pull Request (PR)**:
   - Target branch: `develop`
   - Require at least 1 peer code review approval before merging.
   - Run `pytest` locally to ensure all tests pass.
5. **Merge**:
   - Use **Squash and Merge** to keep the Git history clean and linear.

---

## Adding New Database Migrations with Supabase

When you define or modify SQLAlchemy models in `backend/app/models/`:

1. Ensure your model is imported in `backend/app/models/__init__.py`.
2. Generate migration script:
   ```bash
   alembic revision --autogenerate -m "add item stock table"
   ```
3. Review the generated file in `backend/alembic/versions/`.
4. Apply the migration directly to your Supabase PostgreSQL database:
   ```bash
   alembic upgrade head
   ```
5. You can inspect the migrated tables immediately in the [Supabase Table Editor](https://supabase.com/dashboard).

---

## Demo Data Seeder (SmartSupply Electronics)

A unified development seeder populates ~180 days of realistic, chronologically consistent inventory ledger and sales history for **SmartSupply Electronics** (Sri Lankan IT & electronics accessories retailer/distributor).

### Seeder Commands

Run from the `backend/` directory with virtual environment activated:

```bash
# Seed initial demo dataset (idempotent; stops if demo data already exists)
python scripts/seed_demo_data.py

# Dry-run mode (generates dataset, runs full ledger validation, prints report, rolls back)
python scripts/seed_demo_data.py --dry-run

# Reset and recreate demo dataset (safely cleans demo records and re-seeds)
python scripts/seed_demo_data.py --reset-demo
```

Alternatively, from the repository root:
```bash
python -m backend.scripts.seed_demo_data
python -m backend.scripts.seed_demo_data --dry-run
python -m backend.scripts.seed_demo_data --reset-demo
```

### Key Dataset Characteristics
- **Synthetic Demo Data**: Fictional Sri Lankan market catalog for university demonstration and downstream multi-agent evaluation.
- **Demo Entity Identification**: All demo products use prefix `DEMO-` (`DEMO-001` to `DEMO-012`) and demo suppliers use prefix `DEMO-SUP-` (`DEMO-SUP-001` to `DEMO-SUP-004`).
- **Reproducibility**: Uses fixed pseudo-random seed `SEED = 42`.
- **Safe Reset**: `--reset-demo` strictly deletes records linked to `DEMO-*` products and `DEMO-SUP-*` suppliers in safe foreign-key order, completely preserving non-demo data.
- **Atomic & Ledger-Consistent**: Every `SALE` event atomically creates linked `InventoryTransaction` and `SalesHistory` records. Ledger formula `initial + RESTOCK + RETURN + pos_ADJ - SALE - neg_ADJ == final on_hand` is strictly validated.
- **Realistic Commercial Offers**: ProductSupplier entries feature realistic LKR margins, trade-offs between unit cost, MOQ, and lead times across 4 suppliers.

