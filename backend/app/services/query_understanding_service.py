"""
Query Understanding Service for SmartSupply Supplier Knowledge Layer.
Performs deterministic NLP-style intent classification, routing, and DB-backed entity resolution.
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.supplier import Supplier
from app.models.product import Product
from app.schemas.supplier_knowledge import QueryAnalysisResponse

logger = logging.getLogger(__name__)

# Intent definitions
INTENT_SUPPLIER_TERMS = "supplier_terms"
INTENT_SUPPLIER_POLICY = "supplier_policy"
INTENT_PROCUREMENT_POLICY = "procurement_policy"
INTENT_INVENTORY_POLICY = "inventory_policy"
INTENT_SUPPLIER_LOOKUP = "supplier_lookup"
INTENT_SUPPLIER_COMPARISON = "supplier_comparison"
INTENT_MIXED_DECISION = "mixed_supplier_decision"
INTENT_UNKNOWN = "unknown"

# Route definitions
ROUTE_STRUCTURED = "structured"
ROUTE_DOCUMENT = "document"
ROUTE_MIXED = "mixed"
ROUTE_UNKNOWN = "unknown"

# Regex keywords for intents
RE_MIXED_DECISION = re.compile(
    r"\b(compare|comparison|versus|vs|decision|tradeoff|recommend|choose|best supplier)\b.*\b(emergency|urgent|shortage|fast-track|stockout)\b|"
    r"\b(emergency|urgent|stockout)\b.*\b(compare|comparison|versus|vs|supplier|offer)\b",
    re.IGNORECASE,
)

RE_SUPPLIER_COMPARISON = re.compile(
    r"\b(compare|comparison|versus|vs|cheaper|cheapest|faster|fastest|difference between)\b",
    re.IGNORECASE,
)

RE_SUPPLIER_LOOKUP = re.compile(
    r"\b(which suppliers?|who supplies?|who sells?|who provides?|find suppliers?|suppliers? for|suppliers? providing|suppliers? of)\b",
    re.IGNORECASE,
)

RE_SUPPLIER_TERMS = re.compile(
    r"\b(moq|minimum order|lead\s*time|leadtime|unit\s*cost|price|pricing|cost|commercial terms|wholesale cost|pack size|offer)\b",
    re.IGNORECASE,
)

RE_SUPPLIER_POLICY = re.compile(
    r"\b(late|delay|delivers? late|delivery slip|penalty|rebate|warranty|rma|replacement|defective|damaged|return|cancel|cancellation|restocking|sla|service level)\b",
    re.IGNORECASE,
)

RE_PROCUREMENT_POLICY = re.compile(
    r"\b(procurement policy|approval|approve|authorization|authorise|threshold|exceeding|spend|spending|cfo|vice president|vp|three-way match|audit|grn|onboarding|avl|approved vendor list|vendor qualification|emergency procurement|emergency purchasing)\b",
    re.IGNORECASE,
)

RE_INVENTORY_POLICY = re.compile(
    r"\b(replenishment policy|inventory policy|stockout|safety stock|reorder point|rop|buffer quantity|order splitting|critical item|coverage|high stockout risk)\b",
    re.IGNORECASE,
)


def normalize_query_text(query: str) -> str:
    """Normalizes query text by lowercasing and stripping excess punctuation/whitespace."""
    if not query:
        return ""
    q = query.lower()
    # Normalize smart quotes and dashes
    q = q.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    q = q.replace("—", "-").replace("–", "-")
    # Replace punctuation (except hyphens in codes like DEMO-001) with spaces
    q = re.sub(r"[^\w\s\-]", " ", q)
    return " ".join(q.split())


from app.core.config import settings

try:
    from rapidfuzz import fuzz
    def _fuzzy_similarity(s1: str, s2: str) -> float:
        return float(fuzz.ratio(s1.lower(), s2.lower()))
    def _fuzzy_token_similarity(s1: str, s2: str) -> float:
        return float(max(fuzz.ratio(s1.lower(), s2.lower()), fuzz.token_set_ratio(s1.lower(), s2.lower())))
except ImportError:
    import difflib
    def _fuzzy_similarity(s1: str, s2: str) -> float:
        return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio() * 100.0
    def _fuzzy_token_similarity(s1: str, s2: str) -> float:
        return difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio() * 100.0


def _extract_query_ngrams(query: str, max_n: int = 3) -> List[str]:
    """Generates 1-word, 2-word, and 3-word shingles/ngrams from normalized query text."""
    tokens = normalize_query_text(query).split()
    ngrams: List[str] = []
    for n in range(1, min(max_n + 1, len(tokens) + 1)):
        for i in range(len(tokens) - n + 1):
            ngrams.append(" ".join(tokens[i : i + n]))
    return ngrams


def resolve_supplier_entity_with_status(
    query: str,
    db: Session,
    threshold: Optional[float] = None,
    ambiguity_margin: Optional[float] = None,
) -> Tuple[Optional[Supplier], bool, List[Supplier]]:
    """
    Resolves supplier from PostgreSQL using prioritized matching:
    1. Exact supplier code match
    2. Exact normalized name match
    3. Distinctive primary brand token match
    4. High-confidence fuzzy match
    5. Ambiguity detection (returns needs_clarification=True if top candidates are too close).
    """
    threshold = threshold if threshold is not None else getattr(settings, "FUZZY_MATCH_THRESHOLD", 75.0)
    ambiguity_margin = ambiguity_margin if ambiguity_margin is not None else getattr(settings, "FUZZY_AMBIGUITY_MARGIN", 5.0)

    suppliers = db.scalars(select(Supplier).order_by(Supplier.id.asc())).all()
    if not suppliers:
        return None, False, []

    norm_q = " " + normalize_query_text(query) + " "

    # Priority 1: Exact supplier code match (e.g. DEMO-SUP-001)
    for supp in suppliers:
        if supp.supplier_code:
            code_pattern = r"\b" + re.escape(supp.supplier_code.lower()) + r"\b"
            if re.search(code_pattern, norm_q):
                return supp, False, [supp]

    # Priority 2: Exact full name match (longest names first)
    sorted_by_len = sorted(suppliers, key=lambda s: len(s.name), reverse=True)
    for supp in sorted_by_len:
        name_lower = supp.name.lower()
        if name_lower in norm_q:
            return supp, False, [supp]

    # Priority 3: Distinctive primary word in name (e.g. 'TechSource', 'NextGen', 'Island Tech')
    generic_tokens = {"lanka", "supplies", "wholesale", "distribution", "electronics", "pvt", "ltd", "co"}
    priority_3_matches = []
    for supp in suppliers:
        name_tokens = [t.lower() for t in re.split(r"[\s\-]+", supp.name) if t.lower() not in generic_tokens]
        matched = False
        for token in name_tokens:
            if len(token) >= 4:
                token_pattern = r"\b" + re.escape(token) + r"\b"
                if re.search(token_pattern, norm_q):
                    matched = True
                    break
        if matched:
            priority_3_matches.append(supp)

    if len(priority_3_matches) == 1:
        return priority_3_matches[0], False, [priority_3_matches[0]]
    elif len(priority_3_matches) > 1:
        return None, True, priority_3_matches

    # Priority 4: High-confidence fuzzy matching against query ngrams
    query_ngrams = _extract_query_ngrams(query, max_n=3)
    scored_candidates: List[Tuple[Supplier, float]] = []

    for supp in suppliers:
        candidate_phrases = [supp.name.lower()]
        if supp.supplier_code:
            candidate_phrases.append(supp.supplier_code.lower())
        brand_tokens = [t.lower() for t in re.split(r"[\s\-]+", supp.name) if t.lower() not in generic_tokens]
        candidate_phrases.extend(brand_tokens)

        best_supp_score = 0.0
        for phrase in candidate_phrases:
            for ngram in query_ngrams:
                # Disregard single-letter or very short ngrams for fuzzy matching
                if len(ngram) < 3:
                    continue
                score = _fuzzy_similarity(phrase, ngram)
                if score > best_supp_score:
                    best_supp_score = score

        if best_supp_score >= threshold:
            scored_candidates.append((supp, best_supp_score))

    if not scored_candidates:
        return None, False, []

    # Sort descending by score
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    top_supp, top_score = scored_candidates[0]

    if len(scored_candidates) > 1:
        second_supp, second_score = scored_candidates[1]
        if (top_score - second_score) < ambiguity_margin:
            logger.info(
                "Ambiguous supplier resolution between '%s' (score=%.1f) and '%s' (score=%.1f)",
                top_supp.name, top_score, second_supp.name, second_score
            )
            return None, True, [top_supp, second_supp]

    return top_supp, False, [top_supp]


def resolve_supplier_entity(query: str, db: Session) -> Optional[Supplier]:
    """Resolves supplier entity from query. Returns None if ambiguous or not found."""
    supp, needs_clarification, _ = resolve_supplier_entity_with_status(query, db)
    return None if needs_clarification else supp


def resolve_product_entity_with_status(
    query: str,
    db: Session,
    threshold: Optional[float] = None,
    ambiguity_margin: Optional[float] = None,
) -> Tuple[Optional[Product], bool, List[Product]]:
    """
    Resolves catalog product using prioritized matching:
    1. Exact SKU match
    2. Exact normalized name match
    3. Alias/plural match (e.g. 'mice' -> 'mouse')
    4. High-confidence fuzzy match (e.g. 'wirless mouse' -> 'Wireless Mouse')
    5. Ambiguity detection (returns needs_clarification=True if top candidates are too close).
    """
    threshold = threshold if threshold is not None else getattr(settings, "FUZZY_MATCH_THRESHOLD", 75.0)
    ambiguity_margin = ambiguity_margin if ambiguity_margin is not None else getattr(settings, "FUZZY_AMBIGUITY_MARGIN", 5.0)

    products = db.scalars(select(Product).order_by(Product.id.asc())).all()
    if not products:
        return None, False, []

    norm_q = " " + normalize_query_text(query) + " "

    # Priority 1: Exact SKU match
    for prod in products:
        if prod.sku:
            sku_pattern = r"\b" + re.escape(prod.sku.lower()) + r"\b"
            if re.search(sku_pattern, norm_q):
                return prod, False, [prod]

    # Priority 2: Exact product name match (longest names first)
    sorted_by_len = sorted(products, key=lambda p: len(p.name), reverse=True)
    for prod in sorted_by_len:
        prod_name_norm = normalize_query_text(prod.name)
        if len(prod_name_norm) >= 3 and prod_name_norm in norm_q:
            return prod, False, [prod]

    # Priority 3: Alias / plurals
    alias_map = {
        "mice": "mouse",
        "keyboards": "keyboard",
        "hubs": "hub",
        "stands": "stand",
        "cables": "cable",
        "ssds": "ssd",
        "routers": "router",
        "headsets": "headset",
        "webcams": "webcam",
    }
    tokens = norm_q.split()
    mapped_tokens = [alias_map.get(t, t) for t in tokens]
    mapped_q = " " + " ".join(mapped_tokens) + " "

    for prod in sorted_by_len:
        prod_name_norm = normalize_query_text(prod.name)
        if len(prod_name_norm) >= 3 and prod_name_norm in mapped_q:
            return prod, False, [prod]

    # Priority 4: High-confidence fuzzy match against query ngrams
    query_ngrams = _extract_query_ngrams(query, max_n=4)
    scored_candidates: List[Tuple[Product, float]] = []

    for prod in products:
        prod_name_lower = prod.name.lower()
        prod_words_len = len(prod_name_lower.split())
        best_prod_score = 0.0

        for ngram in query_ngrams:
            if len(ngram) < 3:
                continue
            ngram_words_len = len(ngram.split())

            # Direct string similarity for similarly sized ngrams
            if abs(ngram_words_len - prod_words_len) <= 1:
                ratio_score = _fuzzy_similarity(prod_name_lower, ngram)
                if ratio_score > best_prod_score:
                    best_prod_score = ratio_score

            # Token set similarity for partial mentions / prefixes (e.g. 'usb cable' in 'USB Cable Type A')
            token_score = _fuzzy_token_similarity(prod_name_lower, ngram)
            if token_score > best_prod_score:
                best_prod_score = token_score

        if best_prod_score >= threshold:
            scored_candidates.append((prod, best_prod_score))

    if not scored_candidates:
        return None, False, []

    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    top_prod, top_score = scored_candidates[0]

    if len(scored_candidates) > 1:
        second_prod, second_score = scored_candidates[1]
        if (top_score - second_score) < ambiguity_margin:
            logger.info(
                "Ambiguous product resolution between '%s' (score=%.1f) and '%s' (score=%.1f)",
                top_prod.name, top_score, second_prod.name, second_score
            )
            return None, True, [top_prod, second_prod]

    return top_prod, False, [top_prod]


def resolve_product_entity(query: str, db: Session) -> Optional[Product]:
    """Resolves product entity from query. Returns None if ambiguous or not found."""
    prod, needs_clarification, _ = resolve_product_entity_with_status(query, db)
    return None if needs_clarification else prod


def analyze_query(query: str, db: Session) -> QueryAnalysisResponse:
    """
    Analyzes an incoming natural language query against current database entities
    and determines intent, source routing, and confidence.
    """
    if not query or not query.strip():
        return QueryAnalysisResponse(
            original_query=query or "",
            normalized_query="",
            intent=INTENT_UNKNOWN,
            route=ROUTE_UNKNOWN,
            confidence=0.0,
            unresolved_terms=["empty_query"],
        )

    norm_q = normalize_query_text(query)

    # 1. Entity resolution from live PostgreSQL
    supplier = resolve_supplier_entity(query, db)
    product = resolve_product_entity(query, db)

    # 2. Intent classification
    intent = INTENT_UNKNOWN
    route = ROUTE_UNKNOWN
    confidence = 0.5
    unresolved_terms: List[str] = []

    # Check for mixed decision / emergency comparison first
    if RE_MIXED_DECISION.search(norm_q):
        intent = INTENT_MIXED_DECISION
        route = ROUTE_MIXED
        confidence = 0.95
    # Check for supplier comparison
    elif RE_SUPPLIER_COMPARISON.search(norm_q):
        intent = INTENT_SUPPLIER_COMPARISON
        route = ROUTE_MIXED
        confidence = 0.90
    # Check for supplier lookup (who sells X)
    elif RE_SUPPLIER_LOOKUP.search(norm_q):
        intent = INTENT_SUPPLIER_LOOKUP
        route = ROUTE_STRUCTURED
        confidence = 0.95
    # Check for commercial supplier terms (MOQ, lead time, price)
    elif RE_SUPPLIER_TERMS.search(norm_q):
        intent = INTENT_SUPPLIER_TERMS
        route = ROUTE_STRUCTURED
        confidence = 0.95
    # Check for supplier policy / SLA (late delivery, warranty, RMA)
    elif RE_SUPPLIER_POLICY.search(norm_q):
        intent = INTENT_SUPPLIER_POLICY
        route = ROUTE_DOCUMENT
        confidence = 0.95
    # Check for procurement policy
    elif RE_PROCUREMENT_POLICY.search(norm_q):
        intent = INTENT_PROCUREMENT_POLICY
        route = ROUTE_DOCUMENT
        confidence = 0.95
    # Check for inventory replenishment policy
    elif RE_INVENTORY_POLICY.search(norm_q):
        intent = INTENT_INVENTORY_POLICY
        route = ROUTE_DOCUMENT
        confidence = 0.95
    # Entity-driven fallbacks
    elif supplier is not None and product is not None:
        intent = INTENT_SUPPLIER_TERMS
        route = ROUTE_STRUCTURED
        confidence = 0.85
    elif product is not None and ("supplier" in norm_q or "offer" in norm_q):
        intent = INTENT_SUPPLIER_LOOKUP
        route = ROUTE_STRUCTURED
        confidence = 0.85
    elif supplier is not None:
        intent = INTENT_SUPPLIER_POLICY
        route = ROUTE_DOCUMENT
        confidence = 0.75
    else:
        intent = INTENT_UNKNOWN
        route = ROUTE_UNKNOWN
        confidence = 0.20
        unresolved_terms.append(norm_q)

    # Cross-check mixed situations (e.g., asking for MOQ AND warranty in one query)
    has_terms = bool(RE_SUPPLIER_TERMS.search(norm_q))
    has_doc_policy = bool(RE_SUPPLIER_POLICY.search(norm_q) or RE_PROCUREMENT_POLICY.search(norm_q))
    if has_terms and has_doc_policy:
        route = ROUTE_MIXED
        intent = INTENT_MIXED_DECISION
        confidence = 0.95

    return QueryAnalysisResponse(
        original_query=query,
        normalized_query=norm_q,
        intent=intent,
        route=route,
        supplier_id=supplier.id if supplier else None,
        supplier_name=supplier.name if supplier else None,
        supplier_code=supplier.supplier_code if supplier else None,
        product_id=product.id if product else None,
        product_name=product.name if product else None,
        sku=product.sku if product else None,
        confidence=confidence,
        unresolved_terms=unresolved_terms,
    )
