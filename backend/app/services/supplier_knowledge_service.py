"""
Supplier Knowledge Service for SmartSupply.
Provides unified access to structured PostgreSQL supplier/product data
and grounded ChromaDB document evidence.
"""

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select

from app.models.supplier import Supplier
from app.models.product import Product
from app.models.product_supplier import ProductSupplier
from app.services.query_understanding_service import (
    analyze_query,
    ROUTE_STRUCTURED,
    ROUTE_DOCUMENT,
    ROUTE_MIXED,
    ROUTE_UNKNOWN,
    INTENT_SUPPLIER_POLICY,
    INTENT_PROCUREMENT_POLICY,
    INTENT_INVENTORY_POLICY,
)
from app.services.chroma_service import search_documents

logger = logging.getLogger(__name__)


# =============================================================================
# 1. STRUCTURED SUPPLIER & PRODUCT KNOWLEDGE FUNCTIONS
# =============================================================================

def get_supplier(db: Session, supplier_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves structured supplier details from PostgreSQL."""
    supp = db.get(Supplier, supplier_id)
    if not supp:
        return None
    return {
        "id": supp.id,
        "supplier_code": supp.supplier_code,
        "name": supp.name,
        "contact_name": supp.contact_name,
        "email": supp.email,
        "phone": supp.phone,
        "address": supp.address,
        "is_active": supp.is_active,
        "source_type": "postgresql",
        "authority": "operational",
    }


def get_product(db: Session, product_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves structured product catalog details from PostgreSQL."""
    prod = db.get(Product, product_id)
    if not prod:
        return None
    return {
        "id": prod.id,
        "sku": prod.sku,
        "name": prod.name,
        "category": prod.category,
        "description": prod.description,
        "unit_price": float(prod.unit_price) if prod.unit_price is not None else 0.0,
        "reorder_point": prod.reorder_point,
        "is_active": prod.is_active,
        "source_type": "postgresql",
        "authority": "operational",
    }


def get_product_supplier_offers(
    db: Session,
    product_id: int,
    is_active: Optional[bool] = True,
) -> List[Dict[str, Any]]:
    """
    Retrieves all commercial offers for a product across suppliers,
    eagerly loading supplier records.
    """
    stmt = (
        select(ProductSupplier)
        .options(joinedload(ProductSupplier.supplier), joinedload(ProductSupplier.product))
        .where(ProductSupplier.product_id == product_id)
    )
    if is_active is not None:
        stmt = stmt.where(ProductSupplier.is_active == is_active)

    stmt = stmt.order_by(ProductSupplier.unit_cost.asc())
    offers = db.scalars(stmt).all()

    results: List[Dict[str, Any]] = []
    for o in offers:
        results.append({
            "offer_id": o.id,
            "product_id": o.product_id,
            "product_sku": o.product.sku if o.product else None,
            "product_name": o.product.name if o.product else None,
            "supplier_id": o.supplier_id,
            "supplier_code": o.supplier.supplier_code if o.supplier else None,
            "supplier_name": o.supplier.name if o.supplier else None,
            "unit_cost": float(o.unit_cost) if o.unit_cost is not None else 0.0,
            "moq": o.moq,
            "lead_time_days": o.lead_time_days,
            "is_active": o.is_active,
            "source_type": "postgresql",
            "authority": "operational",
        })
    return results


def get_supplier_offer(
    db: Session,
    product_id: int,
    supplier_id: int,
) -> Optional[Dict[str, Any]]:
    """Retrieves the commercial offer for a specific product and supplier pair."""
    stmt = (
        select(ProductSupplier)
        .options(joinedload(ProductSupplier.supplier), joinedload(ProductSupplier.product))
        .where(
            ProductSupplier.product_id == product_id,
            ProductSupplier.supplier_id == supplier_id,
        )
    )
    offer = db.scalars(stmt).first()
    if not offer:
        return None
    return {
        "offer_id": offer.id,
        "product_id": offer.product_id,
        "product_sku": offer.product.sku if offer.product else None,
        "product_name": offer.product.name if offer.product else None,
        "supplier_id": offer.supplier_id,
        "supplier_code": offer.supplier.supplier_code if offer.supplier else None,
        "supplier_name": offer.supplier.name if offer.supplier else None,
        "unit_cost": float(offer.unit_cost) if offer.unit_cost is not None else 0.0,
        "moq": offer.moq,
        "lead_time_days": offer.lead_time_days,
        "is_active": offer.is_active,
        "source_type": "postgresql",
        "authority": "operational",
    }


def get_suppliers_for_product(
    db: Session,
    product_id: int,
    is_active: Optional[bool] = True,
) -> List[Dict[str, Any]]:
    """Retrieves all distinct suppliers that offer the given product."""
    offers = get_product_supplier_offers(db=db, product_id=product_id, is_active=is_active)
    seen_ids = set()
    suppliers: List[Dict[str, Any]] = []
    for o in offers:
        supp_id = o["supplier_id"]
        if supp_id not in seen_ids:
            seen_ids.add(supp_id)
            suppliers.append({
                "supplier_id": o["supplier_id"],
                "supplier_code": o["supplier_code"],
                "supplier_name": o["supplier_name"],
                "unit_cost": o["unit_cost"],
                "moq": o["moq"],
                "lead_time_days": o["lead_time_days"],
                "is_active": o["is_active"],
                "source_type": "postgresql",
                "authority": "operational",
            })
    return suppliers


# =============================================================================
# 2. DOCUMENT KNOWLEDGE ACCESS FUNCTIONS
# =============================================================================

def search_supplier_documents(
    query: str,
    supplier_id: int,
    top_k: int = 5,
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Searches documents specific to a given supplier (SLA, performance reports)."""
    return search_documents(
        query=query,
        top_k=top_k,
        supplier_id=supplier_id,
        db=db,
    )


def search_procurement_policy(
    query: str,
    top_k: int = 5,
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Searches corporate procurement policy documents."""
    return search_documents(
        query=query,
        top_k=top_k,
        document_type="procurement_policy",
        db=db,
    )


def search_inventory_policy(
    query: str,
    top_k: int = 5,
    db: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """Searches inventory replenishment policy documents."""
    return search_documents(
        query=query,
        top_k=top_k,
        document_type="inventory_replenishment_policy",
        db=db,
    )


# =============================================================================
# 3. UNIFIED SUPPLIER KNOWLEDGE RESOLUTION
# =============================================================================

def resolve_supplier_knowledge(
    query: str,
    db: Session,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Unified entry point for the Supplier Knowledge Layer.

    Flow:
    1. Deterministically analyze query for intent and entities.
    2. Route to:
       - structured: PostgreSQL commercial facts
       - document: grounded ChromaDB document chunks (verified in DB)
       - mixed: both structured offers and document evidence
       - unknown: returns structured safe response with needs_clarification=True
    3. Return purely structured factual payload without LLM prose or recommendation.
    """
    analysis = analyze_query(query=query, db=db)
    structured_facts: List[Dict[str, Any]] = []
    document_evidence: List[Dict[str, Any]] = []

    route = analysis.route

    if route == ROUTE_STRUCTURED:
        # Retrieve structured facts from PostgreSQL
        if analysis.product_id and analysis.supplier_id:
            offer = get_supplier_offer(db, analysis.product_id, analysis.supplier_id)
            if offer:
                structured_facts.append(offer)
            else:
                # If no specific offer, return supplier and product info
                supp = get_supplier(db, analysis.supplier_id)
                prod = get_product(db, analysis.product_id)
                if supp:
                    structured_facts.append({"supplier": supp, "source_type": "postgresql", "authority": "operational"})
                if prod:
                    structured_facts.append({"product": prod, "source_type": "postgresql", "authority": "operational"})
        elif analysis.product_id:
            offers = get_product_supplier_offers(db, analysis.product_id)
            structured_facts.extend(offers)
        elif analysis.supplier_id:
            supp = get_supplier(db, analysis.supplier_id)
            if supp:
                structured_facts.append({"supplier": supp, "source_type": "postgresql", "authority": "operational"})

    elif route == ROUTE_DOCUMENT:
        # Retrieve grounded document chunks
        if analysis.intent == INTENT_SUPPLIER_POLICY and analysis.supplier_id:
            document_evidence = search_supplier_documents(query, analysis.supplier_id, top_k=top_k, db=db)
        elif analysis.intent == INTENT_PROCUREMENT_POLICY:
            document_evidence = search_procurement_policy(query, top_k=top_k, db=db)
        elif analysis.intent == INTENT_INVENTORY_POLICY:
            document_evidence = search_inventory_policy(query, top_k=top_k, db=db)
        else:
            document_evidence = search_documents(
                query=query,
                top_k=top_k,
                supplier_id=analysis.supplier_id,
                db=db,
            )

    elif route == ROUTE_MIXED:
        # Retrieve both structured commercial offers AND document evidence
        if analysis.product_id:
            structured_facts = get_product_supplier_offers(db, analysis.product_id)
        elif analysis.supplier_id:
            supp = get_supplier(db, analysis.supplier_id)
            if supp:
                structured_facts.append({"supplier": supp, "source_type": "postgresql", "authority": "operational"})

        # Fetch relevant document evidence
        if analysis.supplier_id:
            document_evidence = search_supplier_documents(query, analysis.supplier_id, top_k=top_k, db=db)
        else:
            # Query broad document collection (policy + SLAs)
            document_evidence = search_documents(query=query, top_k=top_k, db=db)

    elif route == ROUTE_UNKNOWN:
        # Safe unknown handling: do NOT run unrestricted retrieval for unclear queries
        return {
            "query_analysis": analysis.model_dump(),
            "structured_facts": [],
            "document_evidence": [],
            "needs_clarification": True,
            "clarification_reason": "Could not determine whether the query requests supplier commercial data, policy information, or a supplier comparison.",
        }

    return {
        "query_analysis": analysis.model_dump(),
        "structured_facts": structured_facts,
        "document_evidence": document_evidence,
        "needs_clarification": False,
        "clarification_reason": None,
    }
