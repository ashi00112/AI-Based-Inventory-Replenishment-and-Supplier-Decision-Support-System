"""
Test Suite for Role-Based Access Control (RBAC) and User Authentication.
Validates all 18 specification cases:
- CASE 1: Valid ADMIN login (success)
- CASE 2: Valid STAFF login (success)
- CASE 3: Invalid password (401)
- CASE 4: Inactive user login (blocked / 401)
- CASE 5: Anonymous protected endpoint request (401)
- CASE 6: STAFF calls user creation endpoint (403)
- CASE 7: ADMIN creates STAFF user (success)
- CASE 8: STAFF views products (success)
- CASE 9: STAFF edits products (success)
- CASE 10: STAFF views suppliers (success)
- CASE 11: STAFF edits suppliers (success)
- CASE 12: STAFF runs Decision Agent (success)
- CASE 13: STAFF calls approve endpoint (403)
- CASE 14: STAFF calls reject endpoint (403)
- CASE 15: ADMIN approves recommendation (success)
- CASE 16: ADMIN rejects recommendation (success)
- CASE 17: ADMIN deactivates STAFF account (success)
- CASE 18: Deactivated STAFF account attempts login (blocked / 401)
"""

import json
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from fastapi import status
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.core.security import create_access_token, hash_password
from app.core.llm_provider import MockLLMProvider, set_grok_provider, set_llm_provider
from app.models.user import User, UserRole
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.product_supplier import ProductSupplier
from app.models.inventory import Inventory
from app.models.decision import ApprovalStatus, DecisionRecommendation
from app.services.decision_service import save_decision_recommendation


@pytest.fixture(scope="function")
def test_db_session():
    """Isolated in-memory SQLite database for deterministic RBAC testing."""
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
        yield db, TestingSessionLocal
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def rbac_client(test_db_session):
    """TestClient bound to the isolated test database."""
    _, TestingSessionLocal = test_db_session

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_external_llm():
    """Ensures external LLM is mocked during decision runs."""
    mock = MockLLMProvider(
        default_response=json.dumps({
            "reasoning": "RBAC verification test replenishment recommendation.",
            "factors": ["Inventory deficit detected"],
            "confidence": 0.95,
        })
    )
    set_llm_provider(mock)
    set_grok_provider(mock)
    yield mock


@pytest.fixture
def seed_rbac_env(test_db_session):
    """Seeds admin user, staff user, inactive user, sample product, supplier, and inventory."""
    db, _ = test_db_session

    admin = User(
        id=1,
        name="Admin Manager",
        email="admin@company.com",
        password_hash=hash_password("AdminPassword123!"),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    staff = User(
        id=2,
        name="Procurement Staff",
        email="staff@company.com",
        password_hash=hash_password("StaffPassword123!"),
        role=UserRole.STAFF.value,
        is_active=True,
    )
    inactive_user = User(
        id=3,
        name="Inactive Staff",
        email="inactive@company.com",
        password_hash=hash_password("InactivePassword123!"),
        role=UserRole.STAFF.value,
        is_active=False,
    )
    db.add_all([admin, staff, inactive_user])

    # Sample product and supplier
    product = Product(
        id=10,
        sku="RBAC-PROD-001",
        name="Test Component",
        category="Hardware",
        unit_price=Decimal("5000.00"),
        reorder_point=20,
        is_active=True,
    )
    supplier = Supplier(
        id=20,
        supplier_code="SUP-RBAC-01",
        name="Reliable Vendor Ltd",
        is_active=True,
    )
    db.add_all([product, supplier])
    db.flush()

    inv = Inventory(
        id=10,
        product_id=10,
        on_hand=5,
        reserved=0,
        incoming=0,
    )
    offer = ProductSupplier(
        id=10,
        product_id=10,
        supplier_id=20,
        unit_cost=Decimal("4200.00"),
        moq=10,
        lead_time_days=3,
        is_active=True,
    )
    db.add_all([inv, offer])
    db.commit()

    return {
        "admin": admin,
        "staff": staff,
        "inactive": inactive_user,
        "product": product,
        "supplier": supplier,
    }


def get_token_for(user: User) -> str:
    return create_access_token(user_id=user.id)


def auth_headers_for(user: User) -> dict:
    return {"Authorization": f"Bearer {get_token_for(user)}"}


# =========================================================================
# CASE 1: Valid ADMIN login
# =========================================================================
def test_case_1_valid_admin_login(rbac_client, seed_rbac_env):
    res = rbac_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@company.com", "password": "AdminPassword123!"},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Verify role via /auth/me
    token = data["access_token"]
    res_me = rbac_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == status.HTTP_200_OK
    assert res_me.json()["role"] == "admin"


# =========================================================================
# CASE 2: Valid STAFF login
# =========================================================================
def test_case_2_valid_staff_login(rbac_client, seed_rbac_env):
    res = rbac_client.post(
        "/api/v1/auth/login",
        json={"email": "staff@company.com", "password": "StaffPassword123!"},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "access_token" in data

    # Verify role via /auth/me
    token = data["access_token"]
    res_me = rbac_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == status.HTTP_200_OK
    assert res_me.json()["role"] == "staff"


# =========================================================================
# CASE 3: Invalid password
# =========================================================================
def test_case_3_invalid_password(rbac_client, seed_rbac_env):
    res = rbac_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@company.com", "password": "WrongPassword999!"},
    )
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


# =========================================================================
# CASE 4: Inactive user login blocked
# =========================================================================
def test_case_4_inactive_user_login_blocked(rbac_client, seed_rbac_env):
    res = rbac_client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@company.com", "password": "InactivePassword123!"},
    )
    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
    assert "inactive" in res.json()["detail"].lower()


# =========================================================================
# CASE 5: Anonymous protected endpoint request -> 401
# =========================================================================
def test_case_5_anonymous_protected_endpoint(rbac_client, seed_rbac_env):
    # /api/v1/users is strictly protected
    res_users = rbac_client.get("/api/v1/users")
    assert res_users.status_code == status.HTTP_401_UNAUTHORIZED

    # /api/v1/decision/recommend is protected
    res_dec = rbac_client.post("/api/v1/decision/recommend", json={"product_id": 10})
    assert res_dec.status_code == status.HTTP_401_UNAUTHORIZED

    # /api/v1/auth/me is protected
    res_me = rbac_client.get("/api/v1/auth/me")
    assert res_me.status_code == status.HTTP_401_UNAUTHORIZED


# =========================================================================
# CASE 6: STAFF calls user creation endpoint -> 403
# =========================================================================
def test_case_6_staff_cannot_create_users(rbac_client, seed_rbac_env):
    staff_headers = auth_headers_for(seed_rbac_env["staff"])
    res = rbac_client.post(
        "/api/v1/users",
        json={
            "name": "New Employee",
            "email": "newemp@company.com",
            "password": "Password123!",
            "role": "STAFF",
        },
        headers=staff_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


# =========================================================================
# CASE 7: ADMIN creates STAFF user -> success
# =========================================================================
def test_case_7_admin_creates_staff_user(rbac_client, seed_rbac_env):
    admin_headers = auth_headers_for(seed_rbac_env["admin"])
    res = rbac_client.post(
        "/api/v1/users",
        json={
            "name": "New Staff Member",
            "email": "newstaff@company.com",
            "password": "TemporaryPassword123!",
            "role": "STAFF",
        },
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["email"] == "newstaff@company.com"
    assert data["role"] == "staff"
    assert data["is_active"] is True
    assert "password_hash" not in data
    assert "password" not in data


# =========================================================================
# CASE 8: STAFF views products -> success
# =========================================================================
def test_case_8_staff_views_products(rbac_client, seed_rbac_env):
    staff_headers = auth_headers_for(seed_rbac_env["staff"])
    res = rbac_client.get("/api/v1/products", headers=staff_headers)
    assert res.status_code == status.HTTP_200_OK
    items = res.json()
    assert isinstance(items, list)
    assert any(p["id"] == 10 for p in items)


# =========================================================================
# CASE 9: STAFF edits products -> success
# =========================================================================
def test_case_9_staff_edits_products(rbac_client, seed_rbac_env):
    staff_headers = auth_headers_for(seed_rbac_env["staff"])
    res = rbac_client.patch(
        "/api/v1/products/10",
        json={"name": "Updated Component by Staff"},
        headers=staff_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["name"] == "Updated Component by Staff"


# =========================================================================
# CASE 10: STAFF views suppliers -> success
# =========================================================================
def test_case_10_staff_views_suppliers(rbac_client, seed_rbac_env):
    staff_headers = auth_headers_for(seed_rbac_env["staff"])
    res = rbac_client.get("/api/v1/suppliers", headers=staff_headers)
    assert res.status_code == status.HTTP_200_OK
    items = res.json()
    assert isinstance(items, list)
    assert any(s["id"] == 20 for s in items)


# =========================================================================
# CASE 11: STAFF edits suppliers -> success
# =========================================================================
def test_case_11_staff_edits_suppliers(rbac_client, seed_rbac_env):
    staff_headers = auth_headers_for(seed_rbac_env["staff"])
    res = rbac_client.patch(
        "/api/v1/suppliers/20",
        json={"contact_name": "Updated by Staff"},
        headers=staff_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["contact_name"] == "Updated by Staff"


# =========================================================================
# CASE 12: STAFF runs Decision Agent -> success
# =========================================================================
def test_case_12_staff_runs_decision_agent(rbac_client, seed_rbac_env):
    staff_headers = auth_headers_for(seed_rbac_env["staff"])
    res = rbac_client.post(
        "/api/v1/decision/recommend",
        json={"product_id": 10, "forecast_horizon_days": 14, "urgency": "normal"},
        headers=staff_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["product_id"] == 10
    assert data["approval_status"] == "PENDING"


# =========================================================================
# CASE 13: STAFF calls approve endpoint -> 403 Forbidden
# =========================================================================
def test_case_13_staff_calls_approve_blocked(rbac_client, seed_rbac_env, test_db_session):
    db, _ = test_db_session
    rec = save_decision_recommendation(
        db=db,
        product_id=10,
        replenishment_required=True,
        recommended_order_quantity=30,
        selected_supplier_id=20,
        selected_supplier_name="Reliable Vendor Ltd",
        unit_cost=4200.0,
        estimated_total_cost=126000.0,
        risk_level="HIGH",
        reasoning="Test shortage requiring approval.",
        factors=[],
        warnings=[],
        policy_references=[],
        confidence=0.9,
    )

    staff_headers = auth_headers_for(seed_rbac_env["staff"])
    res = rbac_client.post(
        f"/api/v1/decision/{rec.id}/approve",
        json={"status": "APPROVED", "reviewer_notes": "Attempted staff approval"},
        headers=staff_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


# =========================================================================
# CASE 14: STAFF calls reject endpoint -> 403 Forbidden
# =========================================================================
def test_case_14_staff_calls_reject_blocked(rbac_client, seed_rbac_env, test_db_session):
    db, _ = test_db_session
    rec = save_decision_recommendation(
        db=db,
        product_id=10,
        replenishment_required=True,
        recommended_order_quantity=30,
        selected_supplier_id=20,
        selected_supplier_name="Reliable Vendor Ltd",
        unit_cost=4200.0,
        estimated_total_cost=126000.0,
        risk_level="HIGH",
        reasoning="Test shortage requiring review.",
        factors=[],
        warnings=[],
        policy_references=[],
        confidence=0.9,
    )

    staff_headers = auth_headers_for(seed_rbac_env["staff"])
    res = rbac_client.post(
        f"/api/v1/decision/{rec.id}/reject",
        json={"status": "REJECTED", "rejection_reason": "Attempted staff rejection"},
        headers=staff_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


# =========================================================================
# CASE 15: ADMIN approves recommendation -> success
# =========================================================================
def test_case_15_admin_approves_recommendation(rbac_client, seed_rbac_env, test_db_session):
    db, _ = test_db_session
    rec = save_decision_recommendation(
        db=db,
        product_id=10,
        replenishment_required=True,
        recommended_order_quantity=25,
        selected_supplier_id=20,
        selected_supplier_name="Reliable Vendor Ltd",
        unit_cost=4200.0,
        estimated_total_cost=105000.0,
        risk_level="HIGH",
        reasoning="Critical component replenishment.",
        factors=[],
        warnings=[],
        policy_references=[],
        confidence=0.95,
    )

    admin_headers = auth_headers_for(seed_rbac_env["admin"])
    res = rbac_client.post(
        f"/api/v1/decision/{rec.id}/approve",
        json={"status": "APPROVED", "reviewer_notes": "Manager confirmed purchase order."},
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["approval_status"] == "APPROVED"
    assert data["reviewed_by"] == seed_rbac_env["admin"].id


# =========================================================================
# CASE 16: ADMIN rejects recommendation -> success
# =========================================================================
def test_case_16_admin_rejects_recommendation(rbac_client, seed_rbac_env, test_db_session):
    db, _ = test_db_session
    rec = save_decision_recommendation(
        db=db,
        product_id=10,
        replenishment_required=True,
        recommended_order_quantity=15,
        selected_supplier_id=20,
        selected_supplier_name="Reliable Vendor Ltd",
        unit_cost=4200.0,
        estimated_total_cost=63000.0,
        risk_level="LOW",
        reasoning="Optional replenishment.",
        factors=[],
        warnings=[],
        policy_references=[],
        confidence=0.88,
    )

    admin_headers = auth_headers_for(seed_rbac_env["admin"])
    res = rbac_client.post(
        f"/api/v1/decision/{rec.id}/reject",
        json={"status": "REJECTED", "rejection_reason": "Deferred until next quarter."},
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["approval_status"] == "REJECTED"
    assert data["rejection_reason"] == "Deferred until next quarter."


# =========================================================================
# CASE 17: ADMIN deactivates STAFF account -> success
# =========================================================================
def test_case_17_admin_deactivates_staff(rbac_client, seed_rbac_env):
    admin_headers = auth_headers_for(seed_rbac_env["admin"])
    staff_id = seed_rbac_env["staff"].id

    res = rbac_client.post(f"/api/v1/users/{staff_id}/deactivate", headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["is_active"] is False


# =========================================================================
# CASE 18: Deactivated STAFF account attempts login -> blocked
# =========================================================================
def test_case_18_deactivated_staff_login_blocked(rbac_client, seed_rbac_env):
    # First deactivate via admin
    admin_headers = auth_headers_for(seed_rbac_env["admin"])
    staff_id = seed_rbac_env["staff"].id
    rbac_client.post(f"/api/v1/users/{staff_id}/deactivate", headers=admin_headers)

    # Deactivated staff attempts to login
    res = rbac_client.post(
        "/api/v1/auth/login",
        json={"email": "staff@company.com", "password": "StaffPassword123!"},
    )
    assert res.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
    assert "inactive" in res.json()["detail"].lower()


# =========================================================================
# CASE 19: Anonymous catalog & inventory access blocked -> 401 Unauthorized
# =========================================================================
def test_case_19_anonymous_catalog_and_inventory_blocked(rbac_client, seed_rbac_env):
    """
    Ensures unauthenticated requests to catalog, suppliers, inventory,
    and commercial offers receive HTTP 401 Unauthorized.
    """
    for endpoint in [
        "/api/v1/products",
        "/api/v1/suppliers",
        "/api/v1/inventory",
        "/api/v1/product-suppliers",
    ]:
        res = rbac_client.get(endpoint)
        assert res.status_code == status.HTTP_401_UNAUTHORIZED, (
            f"Expected 401 Unauthorized for anonymous {endpoint}, got {res.status_code}"
        )


# =========================================================================
# CASE 20: Public registration disabled -> 403 Forbidden
# =========================================================================
def test_case_20_public_registration_disabled(rbac_client, seed_rbac_env):
    """
    Ensures anonymous self-signup is forbidden in production enterprise mode.
    """
    res = rbac_client.post(
        "/api/v1/auth/register",
        json={
            "name": "Anonymous User",
            "email": "anonymous@enterprise.com",
            "password": "ValidPassword123!",
        },
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN
    assert "registration is disabled" in res.json()["detail"].lower()

