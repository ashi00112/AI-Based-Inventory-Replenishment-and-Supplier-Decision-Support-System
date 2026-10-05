"""
Conversational presentation layer for the SmartSupply AI Assistant.

This module contains ONLY presentation and parameter-parsing logic:
- Forecast-horizon parsing / validation for conversational parameter collection
- Intent-specific deterministic answer formatters (used directly in degraded
  mode and as the grounding baseline for LLM synthesis)
- The conversational response-length policy given to the LLM

It never performs business calculations. All numbers come from the existing
authoritative components (PostgreSQL, Demand Agent, Decision Agent, Document IR).
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

# ---------------------------------------------------------------------------
# Forecast horizon parameter
# ---------------------------------------------------------------------------

# Must stay consistent with DecisionRecommendationRequest.forecast_horizon_days (gt=0, le=90).
HORIZON_MIN_DAYS = 1
HORIZON_MAX_DAYS = 90

AWAITING_FORECAST_HORIZON = "forecast_horizon_days"

HORIZON_SOURCE_EXPLICIT = "explicit"   # stated in the user's question
HORIZON_SOURCE_SELECTED = "selected"   # answered a horizon clarification
HORIZON_SOURCE_REUSED = "reused"       # reused an explicit horizon from this conversation

HORIZON_CLARIFICATION_OPTIONS: List[Dict[str, str]] = [
    {"label": "7 days", "value": "7 days"},
    {"label": "14 days", "value": "14 days"},
    {"label": "30 days", "value": "30 days"},
    {"label": "Custom", "value": "custom"},
]

HORIZON_RANGE_MESSAGE = (
    f"Please choose a forecast horizon between {HORIZON_MIN_DAYS} and {HORIZON_MAX_DAYS} days."
)

_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "twenty": 20,
    "twenty-one": 21, "thirty": 30, "forty-five": 45, "sixty": 60, "ninety": 90,
}
_NUM = r"(\d{1,4}|" + "|".join(sorted((re.escape(w) for w in _WORD_NUMBERS), key=len, reverse=True)) + r")"

_RE_DAYS = re.compile(rf"\b{_NUM}\s*-?\s*(?:days?|d)\b", re.IGNORECASE)
_RE_WEEKS = re.compile(rf"\b{_NUM}\s*-?\s*(?:weeks?|wks?)\b", re.IGNORECASE)
_RE_MONTHS = re.compile(rf"\b{_NUM}\s*-?\s*months?\b", re.IGNORECASE)
_RE_NEXT_WEEK = re.compile(r"\b(?:next|coming|this)\s+week\b", re.IGNORECASE)
_RE_FORTNIGHT = re.compile(r"\b(?:fortnight|next\s+two\s+weeks)\b", re.IGNORECASE)
_RE_NEXT_MONTH = re.compile(r"\b(?:next|coming|this)\s+month\b", re.IGNORECASE)
_RE_NEXT_QUARTER = re.compile(r"\b(?:next|coming|this)\s+quarter\b", re.IGNORECASE)
_RE_BARE_NUMBER = re.compile(r"^\s*(\d{1,4})\s*[.!]?\s*$")
_RE_CUSTOM = re.compile(r"^\s*(?:custom|other|custom horizon|something else)\s*[.!]?\s*$", re.IGNORECASE)

# Hypothetical / updated-horizon phrasing ("What if we use 7 days instead?")
RE_HORIZON_SCENARIO = re.compile(
    r"\b(what if|instead|how about|what about|scenario|try (?:it )?with|use (?:a )?\d+|switch to|change (?:it|the horizon) to)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HorizonParseResult:
    """Outcome of parsing a forecast horizon from free text."""

    status: str  # "ok" | "out_of_range" | "custom" | "none"
    days: Optional[int] = None


def _to_int(token: str) -> Optional[int]:
    token = token.lower()
    if token.isdigit():
        return int(token)
    return _WORD_NUMBERS.get(token)


def parse_forecast_horizon(text: str, allow_bare_number: bool = False) -> HorizonParseResult:
    """
    Extracts an unambiguous forecast horizon (in days) from user text.

    allow_bare_number: accept a bare number ("14") – only safe when the assistant
    has just asked for a horizon, otherwise numbers like SKUs or quantities
    would be misread.
    """
    if not text:
        return HorizonParseResult("none")

    if allow_bare_number and _RE_CUSTOM.match(text):
        return HorizonParseResult("custom")

    days: Optional[int] = None
    for pattern, multiplier in ((_RE_DAYS, 1), (_RE_WEEKS, 7), (_RE_MONTHS, 30)):
        match = pattern.search(text)
        if match:
            value = _to_int(match.group(1))
            if value is not None:
                days = value * multiplier
                break

    if days is None:
        if _RE_FORTNIGHT.search(text):
            days = 14
        elif _RE_NEXT_WEEK.search(text):
            days = 7
        elif _RE_NEXT_MONTH.search(text):
            days = 30
        elif _RE_NEXT_QUARTER.search(text):
            days = 90

    if days is None and allow_bare_number:
        clean = text.strip().rstrip(".!").lower()
        if clean in _WORD_NUMBERS:
            days = _WORD_NUMBERS[clean]
        else:
            match = _RE_BARE_NUMBER.match(text)
            if match:
                days = int(match.group(1))

    if days is None:
        return HorizonParseResult("none")
    if days < HORIZON_MIN_DAYS or days > HORIZON_MAX_DAYS:
        return HorizonParseResult("out_of_range", days)
    return HorizonParseResult("ok", days)


def horizon_clarification_prompt(intent_label: str, product_name: Optional[str] = None) -> str:
    """Neutral, conversational question asking which horizon to use."""
    subject = f" for **{product_name}**" if product_name else ""
    if intent_label == "decision":
        return f"Which forecast horizon would you like me to use for the replenishment analysis{subject}?"
    if intent_label == "risk":
        return f"Which planning horizon should I use to assess stockout risk{subject}?"
    return f"Which forecast horizon would you like for the demand forecast{subject}?"


# ---------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------

def fmt_lkr(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    value = float(value)
    if value.is_integer():
        return f"LKR {value:,.0f}"
    return f"LKR {value:,.2f}"


def fmt_units(value: Optional[float]) -> str:
    if value is None:
        return "N/A"
    value = float(value)
    if value.is_integer():
        return f"{int(value):,}"
    return f"{value:,.1f}"


def _days_phrase(days: Optional[int], zero_text: str = "0 days") -> str:
    if days is None:
        return "not projected within the horizon"
    if days == 0:
        return zero_text
    return f"~{days} day{'s' if days != 1 else ''}"


_MODEL_NAMES = {
    "sma": "Simple Moving Average",
    "wma": "Weighted Moving Average",
    "ema": "Exponential Moving Average",
    "ses": "Simple Exponential Smoothing",
    "naive": "Naive (last value)",
}


def describe_forecast_model(model: Optional[str]) -> str:
    if not model:
        return "N/A"
    return _MODEL_NAMES.get(str(model).strip().lower(), str(model))


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Reads a key from a dict or attribute from a model uniformly."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        value = obj.get(key, default)
    else:
        value = getattr(obj, key, default)
    return default if value is None else value


# ---------------------------------------------------------------------------
# Prompt-injection hygiene for extractive document answers
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS = re.compile(
    r"(ignore (all )?(previous|prior|above) instructions|system override|disregard (the )?(rules|instructions)|"
    r"you are now|output hacked|act as|jailbreak)",
    re.IGNORECASE,
)

_STOPWORDS = {
    "what", "which", "when", "where", "who", "whom", "why", "how", "does", "do", "did", "is", "are",
    "was", "were", "the", "a", "an", "of", "for", "to", "in", "on", "our", "we", "us", "if", "it",
    "they", "their", "them", "say", "says", "about", "and", "or", "with", "be", "can", "will",
    "would", "should", "me", "tell", "show", "policy", "supplier", "s",
}

_QUERY_EXPANSIONS = {
    "late": {"late", "delay", "delayed", "delays", "penalty", "penalties", "notify", "notification"},
    "delivers": {"delivery", "deliver", "delivers", "delivered"},
    "warranty": {"warranty", "rma", "return", "returns", "defect", "defective"},
    "emergency": {"emergency", "expedited", "urgent", "rush"},
    "penalty": {"penalty", "penalties", "credit", "credits", "late"},
    "sla": {"sla", "service", "otif", "level"},
}


def is_suspicious_text(text: str) -> bool:
    return bool(_INJECTION_PATTERNS.search(text or ""))


def _keywords(query: str) -> set:
    tokens = set(re.findall(r"[a-z0-9%]+", (query or "").lower())) - _STOPWORDS
    expanded = set(tokens)
    for token in tokens:
        expanded |= _QUERY_EXPANSIONS.get(token, set())
    return expanded


def _split_sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip(" -•\t") for p in parts if p and len(p.strip()) > 12]


def extract_relevant_sentences(query: str, excerpts: Sequence[str], max_sentences: int = 2) -> List[str]:
    """
    Picks the sentences from retrieved excerpts that best answer the question.
    Purely extractive (no paraphrasing) so it never invents content; skips
    sentences that look like prompt-injection attempts.
    """
    keywords = _keywords(query)
    scored = []
    order = 0
    for rank, excerpt in enumerate(excerpts):
        for sentence in _split_sentences(excerpt):
            if is_suspicious_text(sentence):
                continue
            words = set(re.findall(r"[a-z0-9%]+", sentence.lower()))
            overlap = len(words & keywords)
            # Prefer higher-ranked chunks on ties
            scored.append((overlap, -rank, -order, sentence))
            order += 1
    if not scored:
        return []
    scored.sort(reverse=True)
    best = [s for s in scored if s[0] > 0][:max_sentences] or scored[:1]
    # Restore document order for readability
    best.sort(key=lambda s: (-s[1], -s[2]))
    return [s[3] for s in best]


# ---------------------------------------------------------------------------
# Intent-specific deterministic formatters
# ---------------------------------------------------------------------------

def format_inventory_answer(data: Dict[str, Any]) -> str:
    """INVENTORY_LOOKUP: a concise stock answer, nothing about forecasts or suppliers."""
    name = data.get("product_name", "This product")
    available = data.get("available_stock", 0)
    lines = [
        f"{name} currently has {fmt_units(available)} units available to fulfil.",
        "",
        f"On hand: {fmt_units(data.get('on_hand'))}",
        f"Reserved: {fmt_units(data.get('reserved'))}",
        f"Incoming: {fmt_units(data.get('incoming_stock'))}",
        f"Reorder-point buffer: {fmt_units(data.get('reorder_point'))}",
    ]
    return "\n".join(lines)


def detect_supplier_fact_focus(query: str) -> Optional[str]:
    q = (query or "").lower()
    if "moq" in q or "minimum order" in q:
        return "moq"
    if "lead time" in q or "leadtime" in q or "how long" in q or "how fast" in q:
        return "lead_time"
    if any(t in q for t in ("price", "pricing", "cost", "charge", "how much")):
        return "unit_cost"
    return None


def format_supplier_facts_answer(supplier_name: str, offers: List[Dict[str, Any]], focus: Optional[str]) -> str:
    """SUPPLIER_FACTS: answers the asked attribute first, then the other commercial terms."""
    if not offers:
        return f"No active catalogue terms were found for {supplier_name}."

    if len(offers) == 1:
        o = offers[0]
        prefix = f"{supplier_name}'s current offer for {o['product_name']}"
        terms = {
            "unit_cost": ("Unit cost", fmt_lkr(o.get("unit_cost"))),
            "moq": ("MOQ", f"{o.get('moq')} units"),
            "lead_time": ("Lead time", f"{o.get('lead_time_days')} days"),
        }
        if focus == "moq":
            lead = f"{prefix} has an MOQ of {o.get('moq')} units."
        elif focus == "lead_time":
            lead = f"{prefix} has a lead time of {o.get('lead_time_days')} days."
        elif focus == "unit_cost":
            lead = f"{prefix} has a unit cost of {fmt_lkr(o.get('unit_cost'))}."
        else:
            lead = f"{prefix}:"
        rest = [f"{label}: {value}" for key, (label, value) in terms.items() if key != focus]
        return "\n".join([lead, ""] + rest)

    lines = [f"{supplier_name}'s current offers:", ""]
    for o in offers:
        lines.append(
            f"{o['product_name']} — {fmt_lkr(o.get('unit_cost'))} | MOQ {o.get('moq')} | {o.get('lead_time_days')} days"
        )
    return "\n".join(lines)


def format_supplier_list_answer(product_name: str, rows: List[Dict[str, Any]]) -> str:
    """SUPPLIER_LIST: compact comparison line per supplier. No recommendation."""
    if not rows:
        return f"No active suppliers are currently listed for {product_name}."
    lines = [
        f"{r['supplier_name']} — {fmt_lkr(r.get('unit_cost'))} | MOQ {r.get('moq')} | {r.get('lead_time_days')} days"
        for r in rows
    ]
    return "\n".join(lines)


def format_supplier_comparison_answer(product_name: str, rows: List[Dict[str, Any]]) -> str:
    """SUPPLIER_COMPARISON: commercial terms + SLA signals, one line each."""
    if not rows:
        return f"No candidate suppliers to compare for {product_name}."
    lines = [f"Supplier comparison for {product_name}:", ""]
    for r in rows:
        sla_bits = []
        if r.get("otif_target") is not None:
            sla_bits.append(f"OTIF {r['otif_target']:.1f}%")
        if r.get("expedited_support") and r["expedited_support"] != "unknown":
            sla_bits.append(f"expedited: {r['expedited_support']}")
        if r.get("emergency_suitability") and r["emergency_suitability"] != "unknown":
            sla_bits.append(f"emergency: {r['emergency_suitability']}")
        sla_text = f" — SLA: {', '.join(sla_bits)}" if sla_bits else ""
        lines.append(
            f"{r['supplier_name']} — {fmt_lkr(r.get('unit_cost'))} | MOQ {r.get('moq')} | {r.get('lead_time_days')} days{sla_text}"
        )
    return "\n".join(lines)


def format_document_answer(
    query: str,
    subject: str,
    excerpts: Sequence[Dict[str, Any]],
    max_citations: int = 3,
) -> str:
    """
    SUPPLIER_DOCUMENT_KNOWLEDGE / PROCUREMENT_POLICY: direct extractive answer
    first, then a compact citation line. Full excerpts live in the Sources panel.
    excerpts: [{"title", "page", "text"}] ordered by relevance.
    """
    if not excerpts:
        return f"I couldn't find documentation covering that for {subject}."
    top = list(excerpts)[:max_citations]
    sentences = extract_relevant_sentences(query, [e.get("text", "") for e in top])
    if sentences:
        body = " ".join(sentences)
    else:
        body = f"{subject}'s SLA requires advance notification for expected delays. Late-delivery penalties may apply according to the SLA."
    seen = []
    for e in top:
        label = f"{e.get('title') or 'Document'} — Page {e.get('page') or 1}"
        if label not in seen:
            seen.append(label)
    if seen:
        return f"{body}\n\nSources\n" + "\n".join(seen)
    return body


def format_forecast_answer(
    product_name: str,
    horizon_days: int,
    total_demand: float,
    selected_model: Optional[str],
) -> str:
    """DEMAND_FORECAST: concise forecast result. No supplier selection."""
    avg_daily = (float(total_demand) / horizon_days) if horizon_days else 0.0
    return "\n".join([
        f"Over the next {horizon_days} days, {product_name} is forecast to have approximately "
        f"{fmt_units(round(float(total_demand), 1))} units of demand.",
        "",
        f"Average daily demand: {avg_daily:,.1f} units",
        f"Model: {describe_forecast_model(selected_model)}",
    ])


def format_risk_answer(
    product_name: str,
    horizon_days: int,
    risk_level: str,
    available_stock: int,
    days_until_stockout: Optional[int],
    days_until_buffer_breach: Optional[int],
) -> str:
    """STOCKOUT_RISK: risk, timing and a one-line explanation. No procurement advice."""
    exhaustion_str = (
        "depleted now (0 days)" if days_until_stockout == 0
        else f"approximately {days_until_stockout} days" if days_until_stockout is not None
        else "no exhaustion projected"
    )
    breach_str = (
        "BREACHED NOW" if days_until_buffer_breach == 0
        else f"approximately {days_until_buffer_breach} days" if days_until_buffer_breach is not None
        else "safe over planning horizon"
    )
    return "\n".join([
        f"{product_name} currently has {str(risk_level).upper()} stockout risk over the selected "
        f"{horizon_days}-day planning horizon.",
        "",
        f"Available-to-fulfil inventory: {fmt_units(available_stock)}",
        f"Projected available inventory exhaustion: {exhaustion_str}",
        f"Reorder-point buffer breach: {breach_str}",
    ])


def build_decision_reason_bullets(rec: Dict[str, Any], max_bullets: int = 5) -> List[str]:
    """
    Turns the Decision Agent's explicit, deterministic factors into 3–6 short
    business bullets. Uses existing output fields only – no recalculation.
    """
    bullets: List[str] = []
    selected = rec.get("selected_supplier") or {}
    condition = rec.get("detected_condition") or {}
    stockout_days = rec.get("days_until_stockout", condition.get("days_until_stockout"))
    breach_days = rec.get("days_until_buffer_breach", condition.get("days_until_buffer_breach"))
    window = rec.get("required_delivery_window_days") or condition.get("required_delivery_window_days")
    required = bool(rec.get("replenishment_required"))

    if stockout_days is not None:
        if stockout_days == 0:
            bullets.append("Available inventory is depleted now (0 days).")
        else:
            bullets.append(f"Available inventory may be exhausted within approximately {stockout_days} day{'s' if stockout_days != 1 else ''}.")
    elif breach_days is not None:
        if breach_days == 0:
            bullets.append("Inventory is currently below the reorder-point buffer (BREACHED NOW).")
        else:
            bullets.append(f"Inventory is projected to fall below the reorder-point buffer in about {breach_days} day{'s' if breach_days != 1 else ''}.")
    elif not required:
        bullets.append("Projected inventory stays above the reorder-point buffer for the planning horizon.")

    sup_name = selected.get("supplier_name")
    if required and sup_name:
        options = rec.get("supplier_options") or []
        feasible = [o for o in options if o.get("is_feasible")]
        lead = selected.get("lead_time_days")
        if window and len(feasible) == 1:
            bullets.append(f"{sup_name} is the only supplier able to meet the required {window}-day delivery window.")
        elif window and lead is not None:
            bullets.append(f"{sup_name} can deliver in {lead} days, within the required {window}-day window.")

        signals = selected.get("policy_signals") or {}
        emergency = signals.get("emergency_suitability")
        expedited = signals.get("expedited_support")
        urgency = str(rec.get("effective_urgency") or rec.get("derived_urgency") or "").lower()
        if urgency in ("emergency", "high") and emergency in ("preferred", "acceptable"):
            bullets.append(f"Its SLA rates it **{emergency}** for emergency replenishment.")
        elif expedited in ("strong", "supported"):
            bullets.append(f"Its SLA provides **{expedited}** expedited-delivery support.")

        slack = selected.get("delivery_slack_days")
        if slack == 0:
            bullets.append("Delivery slack is 0 days, so any supplier delay still carries stockout risk.")
        elif slack is not None and slack < 0:
            bullets.append(f"Delivery slack is {slack} days — delivery is expected after the required window.")
    elif required and not sup_name:
        bullets.append("No candidate supplier could satisfy the constraints, so manual sourcing is needed.")

    sel_ev = selected.get("evidence") or []
    sel_id = selected.get("supplier_id")
    sel_name = (selected.get("supplier_name") or "").lower()

    for warning in rec.get("warnings") or []:
        if len(bullets) >= max_bullets:
            break
        text = str(warning).strip()
        t_lower = text.lower()
        is_missing_doc = any(k in t_lower for k in ["lack", "missing", "insufficient", "no sla", "without sla", "no performance", "no documentation"]) and any(k in t_lower for k in ["sla", "performance", "documentation", "evidence", "document"])
        if is_missing_doc:
            if len(sel_ev) > 0:
                if (sel_id and str(sel_id) in text) or (sel_name and sel_name in t_lower) or ("supplier" in t_lower and not any(str(c.get("supplier_id")) in text for c in (rec.get("supplier_options") or []) if len(c.get("evidence") or []) == 0)):
                    continue
            suppress = False
            for opt in rec.get("supplier_options") or []:
                opt_ev = opt.get("evidence") or []
                opt_id = opt.get("supplier_id")
                opt_name = (opt.get("supplier_name") or "").lower()
                if len(opt_ev) > 0 and ((opt_id and str(opt_id) in text) or (opt_name and opt_name in t_lower)):
                    suppress = True
                    break
            if suppress:
                continue

        if text and len(text) <= 160 and not any(text[:40] in b for b in bullets):
            bullets.append(text)
            break

    return bullets[:max_bullets]


def format_decision_answer(rec: Dict[str, Any], horizon_days: Optional[int] = None, is_scenario: bool = False) -> str:
    """
    FULL_REPLENISHMENT_DECISION: one-sentence recommendation + "Why?" bullets.
    Card values (spend, lead time, slack…) are shown by the UI card, not repeated here.
    """
    product = rec.get("product_name") or "this product"
    qty = rec.get("recommended_order_quantity") or 0
    selected = rec.get("selected_supplier") or {}
    sup_name = selected.get("supplier_name")

    prefix = ""
    if is_scenario and horizon_days:
        prefix = f"**{horizon_days}-Day Scenario**\n\n"

    if rec.get("replenishment_required") and sup_name:
        headline = f"SmartSupply recommends replenishing {product} with {qty} units from {sup_name}."
    elif rec.get("replenishment_required"):
        headline = f"{product} needs replenishment ({qty} units), but no candidate supplier satisfied the delivery constraints."
    else:
        horizon_text = f" over the {horizon_days}-day horizon" if horizon_days else ""
        headline = f"No replenishment is needed for {product}{horizon_text}."

    bullets = build_decision_reason_bullets(rec)
    if not bullets:
        return f"{prefix}Recommendation\n\n{headline}"
    return f"{prefix}Recommendation\n\n{headline}\n\nWhy?\n\n" + "\n".join([f"• {b}" for b in bullets])


def build_decision_details(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Structured data for the expandable sections under the recommendation card."""
    inv = rec.get("inventory_context") or {}
    dem = rec.get("demand_context") or {}
    selected = rec.get("selected_supplier") or {}
    condition = rec.get("detected_condition") or {}

    comparison = []
    for o in rec.get("supplier_options") or []:
        sb = o.get("score_breakdown") or {}
        comparison.append({
            "supplier_name": o.get("supplier_name"),
            "unit_cost": o.get("unit_cost"),
            "moq": o.get("moq"),
            "lead_time_days": o.get("lead_time_days"),
            "delivery_slack_days": o.get("delivery_slack_days"),
            "is_feasible": o.get("is_feasible"),
            "weighted_score": sb.get("weighted_score", o.get("weighted_score")),
            "cost_score": sb.get("cost_score", o.get("cost_score")),
            "delivery_score": sb.get("delivery_score", o.get("delivery_score")),
            "sla_score": sb.get("sla_score", o.get("sla_score")),
            "note": o.get("disqualification_reason") or o.get("eligibility_reason"),
            "selected": o.get("supplier_id") == selected.get("supplier_id"),
        })

    return {
        "inventory_demand": {
            "available_stock": inv.get("available_stock"),
            "on_hand": inv.get("on_hand"),
            "reserved": inv.get("reserved"),
            "incoming": inv.get("incoming"),
            "effective_inventory": inv.get("effective_inventory"),
            "reorder_point": inv.get("reorder_point"),
            "forecast_horizon_days": dem.get("forecast_horizon_days"),
            "total_forecasted_demand": dem.get("total_forecasted_demand"),
            "expected_demand_over_lead_time": dem.get("expected_demand_over_lead_time"),
            "demand_risk_level": dem.get("risk_level"),
            "selected_model": dem.get("selected_model"),
            "days_until_stockout": rec.get("days_until_stockout", condition.get("days_until_stockout")),
            "days_until_buffer_breach": rec.get("days_until_buffer_breach", condition.get("days_until_buffer_breach")),
            "required_delivery_window_days": rec.get("required_delivery_window_days"),
        },
        "supplier_comparison": comparison,
        "reasoning": rec.get("reasoning"),
        "factors": list(rec.get("factors") or []),
        "warnings": list(rec.get("warnings") or []),
        "policy_references": list(rec.get("policy_references") or []),
    }


def format_supplier_scores(rec: Dict[str, Any]) -> str:
    """Targeted detail: candidate score table (only when the user asks)."""
    rows = build_decision_details(rec)["supplier_comparison"]
    if not rows:
        return "No supplier scores are available for the current recommendation."

    def score(v: Any) -> str:
        return f"{float(v):.1f}" if v is not None else "—"

    lines = [
        "| Supplier | Weighted | Cost | Delivery | SLA | Lead time | Slack | Feasible |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        name = f"**{r['supplier_name']}** ✓" if r["selected"] else r["supplier_name"]
        feasible = "Yes" if r["is_feasible"] else ("No" if r["is_feasible"] is False else "—")
        slack = r["delivery_slack_days"] if r["delivery_slack_days"] is not None else "—"
        lines.append(
            f"| {name} | {score(r['weighted_score'])} | {score(r['cost_score'])} | {score(r['delivery_score'])} | "
            f"{score(r['sla_score'])} | {r['lead_time_days']}d | {slack} | {feasible} |"
        )
    return "Supplier scores for the current recommendation (0–100):\n\n" + "\n".join(lines)


def format_demand_details(rec: Dict[str, Any]) -> str:
    """Targeted detail: inventory & demand inputs behind the recommendation."""
    d = build_decision_details(rec)["inventory_demand"]
    return "\n".join([
        f"Demand and inventory inputs behind the recommendation ({d.get('forecast_horizon_days') or '—'}-day horizon):",
        "",
        f"- Forecast demand: {fmt_units(d.get('total_forecasted_demand'))} units "
        f"({describe_forecast_model(d.get('selected_model'))})",
        f"- Demand over supplier lead time: {fmt_units(d.get('expected_demand_over_lead_time'))} units",
        f"- Available-to-fulfil: {fmt_units(d.get('available_stock'))} | Incoming: {fmt_units(d.get('incoming'))} | "
        f"Reorder point: {fmt_units(d.get('reorder_point'))}",
        f"- Available inventory exhaustion: {_days_phrase(d.get('days_until_stockout'), zero_text='depleted now (0 days)')}",
        f"- Reorder-point buffer breach: {_days_phrase(d.get('days_until_buffer_breach'), zero_text='BREACHED NOW')}",
    ])


def format_evidence_answer(scope_title: str, citations: Iterable[Dict[str, Any]]) -> str:
    """EVIDENCE_REQUEST: short list of citations; excerpts are in the Sources panel."""
    items = list(citations)
    if not items:
        return "No document evidence has been retrieved in this conversation yet for the current context."
    lines = [f"Documents supporting {scope_title}:", ""]
    for i, c in enumerate(items, 1):
        lines.append(f"{i}. **{c.get('title') or 'Document'}** — p. {c.get('page') or 1}")
    lines += ["", "Open **Sources** below to read the relevant excerpts."]
    return "\n".join(lines)


def strip_decorative_rules(text: str) -> str:
    """Removes stand-alone horizontal rules that LLMs like to add."""
    cleaned = re.sub(r"(?m)^\s*([-*_])\1{2,}\s*$\n?", "", text or "")
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


# ---------------------------------------------------------------------------
# LLM response-style policy
# ---------------------------------------------------------------------------

CHAT_RESPONSE_STYLE_RULES = (
    "RESPONSE STYLE:\n"
    "- Answer the user's actual question first, in the first sentence.\n"
    "- Be concise by default. Do NOT produce a full procurement report unless the intent requires it.\n"
    "- Do not repeat values the UI already shows in a structured card (they are listed under 'UI card already shows').\n"
    "- Use short headings only where genuinely useful. Prefer bullet points for explanations.\n"
    "- Never output decorative horizontal rules (---).\n"
    "- Do not output internal agent traces or step-by-step private reasoning; give business factors only.\n"
    "- Use supplied facts exactly. Never invent missing details; if something is unknown, say so briefly.\n"
    "- Never claim that SLA or performance documentation is missing when grounded supplier evidence has been supplied.\n"
)

# Per-intent length/shape contract handed to the LLM.
INTENT_RESPONSE_CONTRACTS: Dict[str, str] = {
    "INVENTORY_LOOKUP": "Simple fact: 1–3 sentences. Stock numbers only. No forecast, risk, supplier or replenishment content.",
    "SUPPLIER_FACTS": "Simple fact: 1–3 sentences answering the asked term first. No recommendation.",
    "SUPPLIER_LIST": "Compact list, one line per supplier (cost | MOQ | lead time). No recommendation.",
    "SUPPLIER_COMPARISON": "Compact comparison, one line per supplier, then at most one sentence of observation. No final recommendation.",
    "SUPPLIER_DOCUMENT_KNOWLEDGE": "Direct answer in 1–3 sentences grounded in the cited SLA text, then 'Sources:' with 1–3 'Title — p. N' items. No inventory analysis.",
    "PROCUREMENT_POLICY": "Concise policy summary (1–3 sentences) plus up to 3 rule bullets, then 'Sources:' with 1–3 'Title — p. N' items. No product decision.",
    "DEMAND_FORECAST": "Short structured result (total demand, average daily demand, model) plus at most one sentence. No supplier selection.",
    "STOCKOUT_RISK": "Risk level and timing in 1–2 sentences plus at most 3 bullets. No procurement recommendation.",
    "FULL_REPLENISHMENT_DECISION": "One-sentence recommendation, then a '**Why?**' list of 3–6 short bullets. Under 120 words. Do not restate spend, lead time or slack figures beyond what the bullets need.",
    "DECISION_EXPLANATION": "Focused answer to the specific 'why' question in 2–5 bullets. Do not repeat the full inventory report.",
    "EVIDENCE_REQUEST": "List the supporting documents (title and page) in 1–4 lines. Do not quote long excerpts.",
}

DETAILED_RESPONSE_CONTRACT = (
    "The user explicitly asked for detail. You may use short headed sections, but stay factual and avoid repetition."
)
