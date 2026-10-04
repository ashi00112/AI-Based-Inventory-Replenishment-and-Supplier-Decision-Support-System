"""
SmartSupply Electronics — Demo Document Generation & API Upload Script.

Generates 8 valid, professional PDF documents using ReportLab and uploads them
via the Document Management API (FastAPI TestClient) with proper validation,
checksum calculation, UUID storage keys, and supplier relationship enforcement.
"""

import os
import sys
import hashlib
from pathlib import Path
from decimal import Decimal

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from sqlalchemy import select
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfgen import canvas

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.database.session import SessionLocal
from app.models.supplier import Supplier
from app.models.user import User
from app.models.document import Document, DocumentType
from app.services.document_service import get_storage_dir, delete_document

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas for professional document styling:
    - Running headers with enterprise branding and rule
    - Running footers with confidentiality notice, page X of Y, and rule
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#1E3A8A"))
        
        # Running Header (pages 2+)
        if self._pageNumber > 1:
            self.drawString(54, 794, "SMARTSUPPLY ELECTRONICS PVT LTD")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748B"))
            self.drawRightString(541, 794, "Enterprise Operations & Procurement Manual")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.75)
            self.line(54, 788, 541, 788)

        # Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.75)
        self.line(54, 45, 541, 45)
        
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawString(54, 32, "Confidential — Internal Procurement & Supply Chain Distribution • SmartSupply Electronics")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(541, 32, page_str)
        self.restoreState()


def get_custom_stylesheet():
    """Generates a cohesive, professional typography and color hierarchy."""
    styles = getSampleStyleSheet()

    c_primary = colors.HexColor("#1E3A8A")     # Navy 900
    c_secondary = colors.HexColor("#0284C7")   # Sky 600
    c_body = colors.HexColor("#334155")        # Slate 700

    styles.add(ParagraphStyle(
        name="DocTitle",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=c_primary,
        spaceAfter=4,
    ))

    styles.add(ParagraphStyle(
        name="DocSubtitle",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=c_secondary,
        spaceAfter=14,
    ))

    styles.add(ParagraphStyle(
        name="SectionHeading",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=c_primary,
        spaceBefore=12,
        spaceAfter=5,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="SubSectionHeading",
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=c_secondary,
        spaceBefore=8,
        spaceAfter=3,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="ClauseBody",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12.5,
        textColor=c_body,
        spaceAfter=5,
    ))

    styles.add(ParagraphStyle(
        name="ClauseBodyBold",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=5,
    ))

    styles.add(ParagraphStyle(
        name="BulletText",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=c_body,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3,
    ))

    styles.add(ParagraphStyle(
        name="CalloutText",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#0C4A6E"),
    ))

    styles.add(ParagraphStyle(
        name="MetaLabel",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#64748B"),
    ))

    styles.add(ParagraphStyle(
        name="MetaValue",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
    ))

    styles.add(ParagraphStyle(
        name="TableHeader",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    ))

    styles.add(ParagraphStyle(
        name="TableCell",
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=c_body,
    ))

    styles.add(ParagraphStyle(
        name="TableCellBold",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=10,
        textColor=c_primary,
    ))

    return styles


def create_meta_box(styles, meta_items):
    """Creates a clean metadata banner table at the top of the document."""
    data = []
    for row in meta_items:
        r = []
        for label, val in row:
            p_label = Paragraph(label.upper(), styles["MetaLabel"])
            p_val = Paragraph(val, styles["MetaValue"])
            r.extend([p_label, p_val])
        data.append(r)

    t = Table(data, colWidths=[110, 135, 100, 142])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#E2E8F0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


def create_callout_box(styles, text, title="POLICY DIRECTIVE"):
    """Creates a distinct callout box for critical regulatory or SLA stipulations."""
    content = [
        Paragraph(f"<b>{title}:</b> {text}", styles["CalloutText"]),
    ]
    t = Table([[content]], colWidths=[487])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F0F9FF")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#BAE6FD")),
        ('LINELEFT', (0, 0), (0, -1), 3.0, colors.HexColor("#0284C7")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return t


# =============================================================================
# DOCUMENT 1: SmartSupply Procurement Policy 2026
# =============================================================================
def generate_procurement_policy(output_path: str):
    styles = get_custom_stylesheet()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    story = []

    story.append(Paragraph("SmartSupply Procurement Policy 2026", styles["DocTitle"]))
    story.append(Paragraph("Enterprise Commercial Directives & Supply Chain Governance Guidelines", styles["DocSubtitle"]))
    
    meta_items = [
        [("Document Identifier", "POL-PROC-2026-V2"), ("Effective Date", "January 01, 2026")],
        [("Governance Authority", "Executive Procurement Council"), ("Applicability", "Enterprise-Wide / Global")],
        [("Document Type", "Procurement Policy"), ("Review Cadence", "Annual Mandatory Review")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 12))

    # 1.0 Supplier Eligibility & Compliance
    story.append(Paragraph("1.0 Supplier Eligibility, Compliance, and Restrictive Covenants", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 Only certified vendors active on the SmartSupply Approved Vendor List (AVL) may receive commercial purchase commitments. "
        "Suppliers marked by compliance audits as restricted, suspended, blacklisted, or ineligible are strictly barred from receiving procurement awards.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "1.2 <b>Suspended supplier procurement eligibility:</b> Any vendor currently undergoing Stage 2 or Stage 3 non-performance escalation, "
        "or flagged with an unrectified compliance hold, is deemed ineligible. Purchase orders shall never be awarded to suspended or restricted vendors "
        "regardless of unit price advantages.",
        styles["ClauseBodyBold"]
    ))

    # 2.0 Standard Procurement (Normal Urgency)
    story.append(Paragraph("2.0 Standard Procurement and Normal Urgency Rules", styles["SectionHeading"]))
    story.append(Paragraph(
        "2.1 Under NORMAL procurement urgency, sufficient delivery time exists and candidate suppliers can comfortably satisfy the required delivery window. "
        "In standard procurement, total acquisition cost is the dominant selection criterion, provided the vendor meets MOQ and compliance standards.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "2.2 <b>Normal Priority Decision Weighting:</b> When replenishment urgency is Normal, supplier evaluation adheres to: "
        "Cost Efficiency 60%, Delivery Suitability 20%, and SLA Reliability 20%. Cost-effective suppliers such as NextGen Supplies are preferred for bulk replenishment.",
        styles["ClauseBodyBold"]
    ))

    # 3.0 High-Risk Replenishment (High Urgency)
    story.append(Paragraph("3.0 High-Risk Replenishment and Balanced Decision Rules", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 A HIGH urgency condition occurs when inventory is expected to breach the reorder point buffer within a narrow delivery window. "
        "In high risk supplier selection delivery versus cost, procurement officers must balance acquisition cost with delivery safety margin. "
        "High urgency does NOT blindly select the fastest supplier nor the cheapest supplier; it requires a holistic trade-off.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "3.2 <b>High Priority Decision Weighting:</b> In HIGH urgency scenarios, weighting shifts to: "
        "Delivery Suitability 40%, Cost 40%, and SLA Reliability 20%. Suppliers with higher delivery slack provide safety buffer against stockouts, "
        "which justifies modest cost premiums over zero-slack options.",
        styles["ClauseBodyBold"]
    ))

    # 4.0 Emergency Procurement Protocol
    story.append(Paragraph("4.0 Emergency Procurement Protocol and Lead-Time Dominance", styles["SectionHeading"]))
    story.append(Paragraph(
        "4.1 An EMERGENCY procurement condition is declared when stockout is imminent or already in progress, threatening retail partner fulfillment. "
        "In emergency procurement fastest supplier capability dominates to prevent operational interruption.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "4.2 <b>Emergency Priority Decision Weighting:</b> In EMERGENCY scenarios, weighting is: "
        "Delivery Suitability 60%, SLA Reliability 25%, and Cost 15%. If multiple emergency suppliers can satisfy the delivery window, "
        "the lower-cost compliant supplier shall be preferred as a tie-breaker.",
        styles["ClauseBodyBold"]
    ))

    # 5.0 Cost vs Delivery Priority Weighting Matrix
    story.append(Paragraph("5.0 Cost vs Delivery Priority Weighting Matrix", styles["SectionHeading"]))
    matrix_data = [
        [
            Paragraph("Procurement Urgency", styles["TableHeader"]),
            Paragraph("Cost Weight", styles["TableHeader"]),
            Paragraph("Delivery Weight", styles["TableHeader"]),
            Paragraph("SLA / Reliability Weight", styles["TableHeader"]),
            Paragraph("Core Strategic Intent", styles["TableHeader"]),
        ],
        [
            Paragraph("NORMAL", styles["TableCellBold"]),
            Paragraph("60%", styles["TableCell"]),
            Paragraph("20%", styles["TableCell"]),
            Paragraph("20%", styles["TableCell"]),
            Paragraph("Cost optimization; all feasible suppliers deliver comfortably", styles["TableCell"]),
        ],
        [
            Paragraph("HIGH", styles["TableCellBold"]),
            Paragraph("40%", styles["TableCell"]),
            Paragraph("40%", styles["TableCell"]),
            Paragraph("20%", styles["TableCell"]),
            Paragraph("Balanced trade-off; delivery safety margin weighed alongside price", styles["TableCell"]),
        ],
        [
            Paragraph("EMERGENCY", styles["TableCellBold"]),
            Paragraph("15%", styles["TableCell"]),
            Paragraph("60%", styles["TableCell"]),
            Paragraph("25%", styles["TableCell"]),
            Paragraph("Delivery continuity dominates; fastest compliant supplier chosen", styles["TableCell"]),
        ],
    ]
    t_mat = Table(matrix_data, colWidths=[80, 65, 75, 95, 172])
    t_mat.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_mat)
    story.append(Spacer(1, 8))

    # 6.0 Delivery Safety Margin & Delivery Slack
    story.append(Paragraph("6.0 Delivery Safety Margin and Delivery Slack Governance", styles["SectionHeading"]))
    story.append(Paragraph(
        "6.1 <b>Delivery Slack Definition:</b> Delivery Slack is mathematically defined as: "
        "<code>delivery_slack_days = required_delivery_window_days - supplier.lead_time_days</code>.<br/>"
        "• <b>Slack &lt; 0 days (Infeasible):</b> Supplier cannot meet the delivery window. Infeasible for award when compliant alternatives exist.<br/>"
        "• <b>Zero delivery slack (Slack = 0 days):</b> Supplier lead time exactly matches the window with zero margin. Treated as elevated execution risk and penalized in scoring.<br/>"
        "• <b>Slack 1–2 days:</b> Acceptable delivery margin.<br/>"
        "• <b>Slack &ge; 3 days:</b> Strong delivery margin offering maximum operational resilience against freight delays.",
        styles["ClauseBody"]
    ))

    # 7.0 Purchase Approval Authority & Expenditure Thresholds
    story.append(Paragraph("7.0 Purchase Approval Authority and Expenditure Thresholds", styles["SectionHeading"]))
    story.append(Paragraph(
        "7.1 SmartSupply enforces a graduated financial authorization hierarchy:<br/>"
        "• <b>Tier 1 (Up to LKR 100,000):</b> Operational Purchasing Supervisor approval required.<br/>"
        "• <b>Tier 2 (LKR 100,001 to LKR 500,000):</b> Procurement Manager approval required.<br/>"
        "• <b>Tier 3 (Exceeding LKR 500,000):</b> High-value commitment requiring joint sign-off from Chief Financial Officer (CFO) and VP of Operations.",
        styles["ClauseBody"]
    ))
    story.append(create_callout_box(
        styles,
        "Expenditures exceeding LKR 500,000 mandate joint executive sign-off from the CFO and VP of Operations. Requisitions cannot be split to evade threshold limits.",
        "EXPENDITURE THRESHOLD"
    ))
    story.append(Spacer(1, 6))

    # 8.0 Supplier Escalation and Non-Performance Remediation
    story.append(Paragraph("8.0 Supplier Escalation and Performance Remediation", styles["SectionHeading"]))
    story.append(Paragraph(
        "8.1 When can a supplier be escalated for poor performance? Formal escalation occurs when: "
        "(a) On-Time In-Full delivery rate falls below 90.0% across two consecutive cycles; "
        "(b) Product defect rate exceeds 2.5% in any single delivery batch or 1.5% on average; or "
        "(c) Failure to resolve open RMA warranty replacements within contractual SLA turnaround limits.",
        styles["ClauseBodyBold"]
    ))

    # 9.0 Exception Handling Protocol
    story.append(Paragraph("9.0 Exception Handling Protocol When No Supplier Meets Delivery Window", styles["SectionHeading"]))
    story.append(Paragraph(
        "9.1 If NO compliant supplier can satisfy the required delivery window, the system must not fail or abort. "
        "Instead, the decision is flagged with a prominent delivery-risk warning, and the fastest compliant supplier is selected to minimize expected exposure.",
        styles["ClauseBody"]
    ))
    story.append(create_callout_box(
        styles,
        "No available supplier can fully meet the required delivery window. The fastest compliant supplier was selected to minimize expected exposure.",
        "EXCEPTION MANDATE"
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated: {output_path}")


# =============================================================================
# DOCUMENT 2: SmartSupply Inventory Replenishment Policy 2026
# =============================================================================
def generate_inventory_replenishment_policy(output_path: str):
    styles = get_custom_stylesheet()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    story = []

    story.append(Paragraph("SmartSupply Inventory Replenishment Policy 2026", styles["DocTitle"]))
    story.append(Paragraph("Operational Guidelines for Inventory Buffering, Pipeline Stock & Automated Urgency", styles["DocSubtitle"]))
    
    meta_items = [
        [("Document Identifier", "POL-INVR-2026-V2"), ("Effective Date", "January 01, 2026")],
        [("Operational Scope", "Enterprise Warehouse Network"), ("Applicability", "Automated Multi-Agent Replenishment")],
        [("Document Type", "Inventory Replenishment Policy"), ("Effective Safety Buffer", "Reorder Point (ROP)")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 12))

    # 1.0 Reorder Point as Effective Safety-Stock Buffer
    story.append(Paragraph("1.0 Reorder Point as SmartSupply's Effective Safety-Stock Buffer", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 SmartSupply explicitly treats the <b>reorder_point</b> as the effective safety-stock / retained inventory buffer. "
        "The system does NOT compute a separate statistical safety-stock quantity. The reorder point ensures a baseline operational buffer "
        "is maintained to absorb short-term demand fluctuations and minor delivery variances.",
        styles["ClauseBody"]
    ))

    # 2.0 Physical Inventory vs Reserved Inventory
    story.append(Paragraph("2.0 Physical Inventory, Reserved Stock, and Available Stock", styles["SectionHeading"]))
    story.append(Paragraph(
        "2.1 Available Stock represents the unencumbered physical stock currently in warehouse racks that can be allocated to customer orders:<br/>"
        "<code>available_stock = on_hand - reserved</code>.<br/>"
        "Reserved units allocated to confirmed open sales orders are strictly excluded from available inventory.",
        styles["ClauseBody"]
    ))

    # 3.0 Incoming Inventory as Confirmed Pipeline Stock
    story.append(Paragraph("3.0 Incoming Inventory as Confirmed Pipeline Stock and Timing Limitations", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 <b>Quantity Planning:</b> Confirmed incoming inventory (in-transit purchase orders) is treated as pipeline stock and credited toward the "
        "replenishment requirement to prevent costly over-ordering:<br/>"
        "<code>effective_inventory = available_stock + incoming</code>.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "3.2 <b>Arrival Timing Limitation:</b> Incoming stock is included in replenishment quantity planning, but its exact arrival timing cannot be "
        "used for delivery-window calculation because expected arrival dates are not currently stored in the inventory data model. "
        "For urgency timing, the system relies on physical available stock and daily forecast trajectories.",
        styles["ClauseBodyBold"]
    ))

    # 4.0 Replenishment Requirement Formula
    story.append(Paragraph("4.0 Replenishment Requirement and Order Quantity Formula", styles["SectionHeading"]))
    story.append(Paragraph(
        "4.1 Net requirement is deterministically calculated across the active forecast planning horizon:<br/>"
        "<code>net_requirement = (predicted_demand + reorder_point) - (available_stock + incoming)</code>.<br/>"
        "Replenishment is triggered if <code>net_requirement &gt; 0</code> or if <code>effective_inventory &lt; reorder_point</code>.<br/>"
        "The raw recommended quantity is rounded up to whole units: <code>raw_quantity = max(0, ceil(net_requirement))</code>.",
        styles["ClauseBody"]
    ))

    # 5.0 Stockout Risk & Projected Unsafe Timing
    story.append(Paragraph("5.0 Stockout Risk Classification and Projected Unsafe-Stock Timing", styles["SectionHeading"]))
    story.append(Paragraph(
        "5.1 <b>Days Until Unsafe:</b> Defined as the earliest forecast day on which projected inventory falls below the reorder-point buffer. "
        "If available stock is already below ROP on Day 0, the condition is immediately unsafe.<br/>"
        "5.2 <b>Required Delivery Window:</b> Represents the maximum number of business days before projected stock reaches unsafe levels. "
        "Replenishment must arrive within this window to maintain uninterrupted customer fulfillment.",
        styles["ClauseBody"]
    ))

    # 6.0 Automatic Urgency Derivation
    story.append(Paragraph("6.0 Automatic Urgency Derivation vs Manual Override", styles["SectionHeading"]))
    story.append(Paragraph(
        "6.1 Procurement urgency means: 'How quickly replenishment needs to arrive.' It is derived automatically by SmartSupply by comparing "
        "the required delivery window against active catalog supplier lead times:<br/>"
        "• <b>NORMAL:</b> Sufficient delivery time exists; eligible suppliers comfortably satisfy the delivery window.<br/>"
        "• <b>HIGH:</b> Stock is becoming unsafe soon; some suppliers may miss the window; delivery time and cost both matter.<br/>"
        "• <b>EMERGENCY:</b> Very little delivery time remains; only fastest compliant suppliers can satisfy window; delivery continuity dominates cost.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "6.2 <b>Manual Urgency Override Audit Requirement:</b> Users may optionally supply an urgency override. If the manual override differs "
        "from the system-derived urgency, the recommendation must be audited with a prominent warning: "
        "<i>'System-derived urgency was HIGH, but EMERGENCY was manually selected.'</i>",
        styles["ClauseBodyBold"]
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated: {output_path}")


# =============================================================================
# DOCUMENT 3: TechSource Lanka Service Level Agreement
# =============================================================================
def generate_techsource_sla(output_path: str, supplier_id: int):
    styles = get_custom_stylesheet()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    story = []

    story.append(Paragraph("TechSource Lanka Service Level Agreement", styles["DocTitle"]))
    story.append(Paragraph("Master Commercial Supply & Service Level Terms — Balanced Service Profile", styles["DocSubtitle"]))
    
    meta_items = [
        [("Vendor Name", "TechSource Lanka"), ("Supplier Code", "DEMO-SUP-001")],
        [("Agreement Ref", f"SLA-TSL-2026-ID{supplier_id}"), ("Effective Date", "January 01, 2026")],
        [("Document Type", "Supplier Service Level Agreement"), ("Target OTIF", "96.0% On-Time In-Full")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 12))

    story.append(Paragraph("1.0 Vendor Profile and Balanced Operational Scope", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 TechSource Lanka serves as SmartSupply's balanced-tier supplier, offering dependable fulfillment, high quality, "
        "and moderate lead times across wireless peripherals, ergonomic laptop stands, and office accessories.",
        styles["ClauseBody"]
    ))

    story.append(Paragraph("2.0 Service Commitments and OTIF Target", styles["SectionHeading"]))
    story.append(Paragraph(
        "2.1 TechSource Lanka contractually commits to an On-Time In-Full (OTIF) fulfillment rate of 96.0% across all catalog product categories.",
        styles["ClauseBodyBold"]
    ))
    story.append(Paragraph(
        "2.2 Written order acknowledgements are transmitted within 24 business hours of PO release.",
        styles["ClauseBody"]
    ))

    story.append(Paragraph("3.0 High-Risk Priority Dispatch Protocol", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 <b>TechSource priority dispatch high risk:</b> TechSource supports approved high-risk priority dispatch protocols to accelerate warehouse "
        "release within 24 hours of PO approval, making it suitable for balanced high-risk and standard replenishment scenarios. "
        "In high-risk situations, TechSource provides confirmed dispatch tracking and priority warehouse queue allocation.",
        styles["ClauseBodyBold"]
    ))

    story.append(Paragraph("4.0 Late Delivery Penalties & Warranty Terms", styles["SectionHeading"]))
    story.append(Paragraph(
        "4.1 Late delivery requires 24-hour advance written notification. Delays without notice incur a 1.5% penalty per week up to a 10.0% cap.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "4.2 TechSource provides a 12-month manufacturer replacement warranty with RMA replacement dispatched within 5 business days.",
        styles["ClauseBody"]
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated: {output_path}")


# =============================================================================
# DOCUMENT 4: Digital Distribution Lanka Service Level Agreement
# =============================================================================
def generate_digital_distribution_sla(output_path: str, supplier_id: int):
    styles = get_custom_stylesheet()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    story = []

    story.append(Paragraph("Digital Distribution Lanka Service Level Agreement", styles["DocTitle"]))
    story.append(Paragraph("Master Commercial Supply & Service Level Terms — Rapid Fulfillment & Emergency Support Profile", styles["DocSubtitle"]))
    
    meta_items = [
        [("Vendor Name", "Digital Distribution Lanka"), ("Supplier Code", "DEMO-SUP-002")],
        [("Agreement Ref", f"SLA-DDL-2026-ID{supplier_id}"), ("Effective Date", "January 01, 2026")],
        [("Document Type", "Supplier Service Level Agreement"), ("Target OTIF", "98.0% (Highest Catalog Commitment)")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 12))

    story.append(Paragraph("1.0 Vendor Profile and Expedited Operational Specialization", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 Digital Distribution Lanka is SmartSupply's primary rapid-fulfillment partner, specializing in ultra-short delivery windows, "
        "high-speed courier fulfillment, and urgent replenishment across electronics and computing peripherals.",
        styles["ClauseBody"]
    ))

    story.append(Paragraph("2.0 Industry-Leading OTIF Commitment", styles["SectionHeading"]))
    story.append(Paragraph(
        "2.1 Digital Distribution Lanka contractually commits to an industry-leading On-Time In-Full (OTIF) fulfillment rate of 98.0%, "
        "the highest benchmark among SmartSupply catalog vendors.",
        styles["ClauseBodyBold"]
    ))

    story.append(Paragraph("3.0 Emergency Rapid Delivery and Expedited Orders", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 <b>Digital Distribution emergency rapid delivery:</b> Expedited orders and emergency dispatch are fully supported with dedicated express courier handling "
        "and 24-48 hour fulfillment turnaround. Digital Distribution Lanka is specifically qualified and preferred for HIGH and EMERGENCY procurement "
        "where delivery continuity dominates and zero-slack risks must be avoided.",
        styles["ClauseBodyBold"]
    ))

    story.append(Paragraph("4.0 Strict Late Delivery Terms & Rapid RMA", styles["SectionHeading"]))
    story.append(Paragraph(
        "4.1 Late delivery notification is mandatory within 12 hours. Delays incur a 2.0% penalty per calendar day up to a 15.0% cap.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "4.2 Emergency warranty replacement dispatch is guaranteed within 24 to 48 hours for business-critical accounts.",
        styles["ClauseBody"]
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated: {output_path}")


# =============================================================================
# DOCUMENT 5: NextGen Supplies Service Level Agreement
# =============================================================================
def generate_nextgen_sla(output_path: str, supplier_id: int):
    styles = get_custom_stylesheet()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    story = []

    story.append(Paragraph("NextGen Supplies Service Level Agreement", styles["DocTitle"]))
    story.append(Paragraph("Master Commercial Supply & Service Level Terms — High-Volume Bulk & Cost-Competitive Profile", styles["DocSubtitle"]))
    
    meta_items = [
        [("Vendor Name", "NextGen Supplies"), ("Supplier Code", "DEMO-SUP-003")],
        [("Agreement Ref", f"SLA-NGS-2026-ID{supplier_id}"), ("Effective Date", "January 01, 2026")],
        [("Document Type", "Supplier Service Level Agreement"), ("Commercial Focus", "High-Volume Wholesale & Lowest Unit Cost")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 12))

    story.append(Paragraph("1.0 Vendor Profile and Bulk Commercial Focus", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 NextGen Supplies is SmartSupply's primary high-volume commercial wholesale supplier, providing the lowest unit cost economics "
        "across computer peripherals and accessories. Preferred use case: standard bulk replenishment where delivery timing is non-critical.",
        styles["ClauseBody"]
    ))

    story.append(Paragraph("2.0 Fulfillment Target and Volume Rebates", styles["SectionHeading"]))
    story.append(Paragraph(
        "2.1 NextGen Supplies commits to an On-Time In-Full (OTIF) fulfillment rate of 92.0%, reflecting consolidated freight schedules.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "2.2 High-volume purchase orders exceeding 100 units qualify for an additional 4.0% commercial volume rebate.",
        styles["ClauseBody"]
    ))

    story.append(Paragraph("3.0 Emergency / Expedited Service Limitations", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 <b>NextGen expedited emergency orders:</b> Expedited emergency orders are not guaranteed or supported. High-risk and emergency procurement "
        "orders cannot be expedited through standard freight consolidation networks. NextGen is intended strictly for normal replenishment where cost "
        "efficiency dominates and delivery lead times are comfortably within planning windows. When required delivery windows are constrained, NextGen is not suitable.",
        styles["ClauseBodyBold"]
    ))

    story.append(Paragraph("4.0 Delivery Terms and Extended Cancellation Notice", styles["SectionHeading"]))
    story.append(Paragraph(
        "4.1 Late delivery notices must be issued 48 hours in advance. Penalties are capped at 1.0% per week. Cancellation requires 21 days overdue notice.",
        styles["ClauseBody"]
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated: {output_path}")


# =============================================================================
# DOCUMENT 6: TechSource Lanka Performance Review — Q3 2026
# =============================================================================
def generate_techsource_performance_review(output_path: str, supplier_id: int):
    styles = get_custom_stylesheet()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    story = []

    story.append(Paragraph("Supplier Performance Review — Q3 2026", styles["DocTitle"]))
    story.append(Paragraph("Quarterly Vendor Evaluation & Contractual SLA Compliance Audit: TechSource Lanka", styles["DocSubtitle"]))
    
    meta_items = [
        [("Vendor Evaluated", "TechSource Lanka"), ("Supplier Code", "DEMO-SUP-001")],
        [("Evaluation Period", "Q3 2026 (July 1 – Sept 30, 2026)"), ("Supplier ID Ref", f"SUP-{supplier_id}")],
        [("Document Type", "Supplier Performance Report"), ("Overall Score", "88.5 / 100 (Good Standing)")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 12))

    story.append(Paragraph("1.0 Executive Summary and Review Scope", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 This performance evaluation details operational fulfillment and SLA compliance of TechSource Lanka for Q3 2026. "
        "TechSource achieved an observed OTIF rate of 95.8% and a low defect rate of 0.4%, demonstrating balanced operational reliability "
        "for both normal replenishment and high-risk orders.",
        styles["ClauseBody"]
    ))

    story.append(Paragraph("2.0 Key Performance Indicators Scorecard", styles["SectionHeading"]))
    kpi_data = [
        [
            Paragraph("KPI Dimension", styles["TableHeader"]),
            Paragraph("SLA Target", styles["TableHeader"]),
            Paragraph("Q3 Observed", styles["TableHeader"]),
            Paragraph("Variance", styles["TableHeader"]),
            Paragraph("Assessment", styles["TableHeader"]),
        ],
        [
            Paragraph("On-Time In-Full (OTIF)", styles["TableCellBold"]),
            Paragraph("96.0%", styles["TableCell"]),
            Paragraph("95.8%", styles["TableCell"]),
            Paragraph("-0.2%", styles["TableCell"]),
            Paragraph("Approved / Reliable", styles["TableCell"]),
        ],
        [
            Paragraph("Quality Defect Rate", styles["TableCellBold"]),
            Paragraph("&le; 1.5%", styles["TableCell"]),
            Paragraph("0.40%", styles["TableCell"]),
            Paragraph("+1.1%", styles["TableCell"]),
            Paragraph("Excellent Quality", styles["TableCell"]),
        ],
        [
            Paragraph("RMA Replacement Speed", styles["TableCellBold"]),
            Paragraph("&le; 5 days", styles["TableCell"]),
            Paragraph("4.2 days", styles["TableCell"]),
            Paragraph("+0.8 days", styles["TableCell"]),
            Paragraph("Compliant", styles["TableCell"]),
        ],
    ]
    t_kpi = Table(kpi_data, colWidths=[120, 75, 80, 75, 137])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 8))

    story.append(Paragraph("3.0 Reliability Standing and Escalation Assessment", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 TechSource Lanka is in Good Standing. No formal Stage 1 or Stage 2 escalation was triggered during Q3 2026. "
        "The vendor remains recommended for balanced high-risk and standard procurement operations.",
        styles["ClauseBody"]
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated: {output_path}")


# Backwards compatibility alias
generate_performance_review = generate_techsource_performance_review


# =============================================================================
# DOCUMENT 7: Digital Distribution Lanka Performance Review — Q3 2026
# =============================================================================
def generate_digital_performance_review(output_path: str, supplier_id: int):
    styles = get_custom_stylesheet()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    story = []

    story.append(Paragraph("Supplier Performance Review — Q3 2026", styles["DocTitle"]))
    story.append(Paragraph("Quarterly Vendor Evaluation & Contractual SLA Compliance Audit: Digital Distribution Lanka", styles["DocSubtitle"]))
    
    meta_items = [
        [("Vendor Evaluated", "Digital Distribution Lanka"), ("Supplier Code", "DEMO-SUP-002")],
        [("Evaluation Period", "Q3 2026 (July 1 – Sept 30, 2026)"), ("Supplier ID Ref", f"SUP-{supplier_id}")],
        [("Document Type", "Supplier Performance Report"), ("Overall Score", "97.2 / 100 (Premium Standing)")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 12))

    story.append(Paragraph("1.0 Executive Summary and Review Scope", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 Digital Distribution Lanka demonstrated superior delivery velocity in Q3 2026, achieving an observed OTIF rate of 98.4% "
        "and rapid delivery compliance of 99.1% across 42 expedited orders. Outstanding choice for emergency and high-urgency fulfillment.",
        styles["ClauseBody"]
    ))

    story.append(Paragraph("2.0 Key Performance Indicators Scorecard", styles["SectionHeading"]))
    kpi_data = [
        [
            Paragraph("KPI Dimension", styles["TableHeader"]),
            Paragraph("SLA Target", styles["TableHeader"]),
            Paragraph("Q3 Observed", styles["TableHeader"]),
            Paragraph("Variance", styles["TableHeader"]),
            Paragraph("Assessment", styles["TableHeader"]),
        ],
        [
            Paragraph("On-Time In-Full (OTIF)", styles["TableCellBold"]),
            Paragraph("98.0%", styles["TableCell"]),
            Paragraph("98.4%", styles["TableCell"]),
            Paragraph("+0.4%", styles["TableCell"]),
            Paragraph("Exceeded Target", styles["TableCell"]),
        ],
        [
            Paragraph("Expedited Delivery Accuracy", styles["TableCellBold"]),
            Paragraph("&ge; 98.0%", styles["TableCell"]),
            Paragraph("99.1%", styles["TableCell"]),
            Paragraph("+1.1%", styles["TableCell"]),
            Paragraph("Premium Velocity", styles["TableCell"]),
        ],
        [
            Paragraph("Quality Defect Rate", styles["TableCellBold"]),
            Paragraph("&le; 1.0%", styles["TableCell"]),
            Paragraph("0.20%", styles["TableCell"]),
            Paragraph("+0.8%", styles["TableCell"]),
            Paragraph("Benchmark Standard", styles["TableCell"]),
        ],
    ]
    t_kpi = Table(kpi_data, colWidths=[120, 75, 80, 75, 137])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 8))

    story.append(Paragraph("3.0 Strategic Value in Emergency Procurement", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 Digital Distribution Lanka's strong delivery margin and 2-day standard lead time reliably eliminate stockout exposure. "
        "Retains Premium Standing status for critical and emergency purchase commitments.",
        styles["ClauseBody"]
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated: {output_path}")


# =============================================================================
# DOCUMENT 8: NextGen Supplies Performance Review — Q3 2026
# =============================================================================
def generate_nextgen_performance_review(output_path: str, supplier_id: int):
    styles = get_custom_stylesheet()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    story = []

    story.append(Paragraph("Supplier Performance Review — Q3 2026", styles["DocTitle"]))
    story.append(Paragraph("Quarterly Vendor Evaluation & Contractual SLA Compliance Audit: NextGen Supplies", styles["DocSubtitle"]))
    
    meta_items = [
        [("Vendor Evaluated", "NextGen Supplies"), ("Supplier Code", "DEMO-SUP-003")],
        [("Evaluation Period", "Q3 2026 (July 1 – Sept 30, 2026)"), ("Supplier ID Ref", f"SUP-{supplier_id}")],
        [("Document Type", "Supplier Performance Report"), ("Overall Score", "83.4 / 100 (Bulk Qualified)")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 12))

    story.append(Paragraph("1.0 Executive Summary and Review Scope", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 NextGen Supplies fulfilled 18 bulk consolidated purchase orders in Q3 2026. While offering the lowest wholesale unit prices, "
        "freight consolidation resulted in an observed OTIF rate of 91.8% and delivery variance of +/- 2 business days. "
        "Best suited for planned bulk replenishment where delivery lead times are not tightly constrained.",
        styles["ClauseBody"]
    ))

    story.append(Paragraph("2.0 Key Performance Indicators Scorecard", styles["SectionHeading"]))
    kpi_data = [
        [
            Paragraph("KPI Dimension", styles["TableHeader"]),
            Paragraph("SLA Target", styles["TableHeader"]),
            Paragraph("Q3 Observed", styles["TableHeader"]),
            Paragraph("Variance", styles["TableHeader"]),
            Paragraph("Assessment", styles["TableHeader"]),
        ],
        [
            Paragraph("On-Time In-Full (OTIF)", styles["TableCellBold"]),
            Paragraph("92.0%", styles["TableCell"]),
            Paragraph("91.8%", styles["TableCell"]),
            Paragraph("-0.2%", styles["TableCell"]),
            Paragraph("Acceptable Bulk", styles["TableCell"]),
        ],
        [
            Paragraph("Bulk Order Fulfillment", styles["TableCellBold"]),
            Paragraph("&ge; 95.0%", styles["TableCell"]),
            Paragraph("96.5%", styles["TableCell"]),
            Paragraph("+1.5%", styles["TableCell"]),
            Paragraph("High Volume Passed", styles["TableCell"]),
        ],
        [
            Paragraph("Delivery Variance", styles["TableCellBold"]),
            Paragraph("&plusmn; 1 day", styles["TableCell"]),
            Paragraph("&plusmn; 2 days", styles["TableCell"]),
            Paragraph("-1 day", styles["TableCell"]),
            Paragraph("Elevated Variance", styles["TableCell"]),
        ],
    ]
    t_kpi = Table(kpi_data, colWidths=[120, 75, 80, 75, 137])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 8))

    story.append(Paragraph("3.0 Service Limitations in Constrained Delivery Windows", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 Delivery lead times cannot be accelerated for emergency orders. When delivery window is &le; 5 days, "
        "NextGen's 7-day transit results in negative delivery slack and potential stockout exposure. "
        "Retains Bulk Qualified standing for standard normal replenishments.",
        styles["ClauseBody"]
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated: {output_path}")


# =============================================================================
# MAIN ORCHESTRATION FUNCTION
# =============================================================================
def main():
    print("=" * 60)
    print("SMARTSUPPLY ELECTRONICS — DEMO DOCUMENT GENERATION & UPLOAD (8 DOCS)")
    print("=" * 60)

    db = SessionLocal()
    try:
        suppliers = db.execute(select(Supplier).where(Supplier.is_active == True)).scalars().all()
        supplier_map = {s.name: s.id for s in suppliers}
        print(f"Loaded {len(suppliers)} active suppliers from database:")
        for s in suppliers:
            print(f"  • ID {s.id}: {s.supplier_code} — {s.name}")

        techsource_id = supplier_map.get("TechSource Lanka")
        digital_id = supplier_map.get("Digital Distribution Lanka")
        nextgen_id = supplier_map.get("NextGen Supplies")

        if not all([techsource_id, digital_id, nextgen_id]):
            print("ERROR: Required suppliers not found in database!")
            sys.exit(1)

        user = db.execute(select(User).where(User.is_active == True)).scalars().first()
        if not user:
            print("ERROR: No active user found in database for authentication!")
            sys.exit(1)
        auth_token = create_access_token(user_id=user.id)
        print(f"Authenticated as user {user.email} (ID {user.id})")
    finally:
        db.close()

    output_dir = Path(settings.DOCUMENT_STORAGE_DIR).parent / "demo_generated_pdfs"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nTarget generation directory: {output_dir}")

    doc_specs = [
        {
            "id_tag": "DOC-1",
            "title": "SmartSupply Procurement Policy 2026",
            "document_type": DocumentType.PROCUREMENT_POLICY.value,
            "supplier_id": None,
            "filename": "smartsupply_procurement_policy_2026.pdf",
            "generator": lambda p: generate_procurement_policy(p),
        },
        {
            "id_tag": "DOC-2",
            "title": "SmartSupply Inventory Replenishment Policy 2026",
            "document_type": DocumentType.INVENTORY_REPLENISHMENT_POLICY.value,
            "supplier_id": None,
            "filename": "smartsupply_inventory_replenishment_policy_2026.pdf",
            "generator": lambda p: generate_inventory_replenishment_policy(p),
        },
        {
            "id_tag": "DOC-3",
            "title": "TechSource Lanka Service Level Agreement",
            "document_type": DocumentType.SUPPLIER_SLA.value,
            "supplier_id": techsource_id,
            "filename": "techsource_lanka_sla_2026.pdf",
            "generator": lambda p: generate_techsource_sla(p, techsource_id),
        },
        {
            "id_tag": "DOC-4",
            "title": "Digital Distribution Lanka Service Level Agreement",
            "document_type": DocumentType.SUPPLIER_SLA.value,
            "supplier_id": digital_id,
            "filename": "digital_distribution_lanka_sla_2026.pdf",
            "generator": lambda p: generate_digital_distribution_sla(p, digital_id),
        },
        {
            "id_tag": "DOC-5",
            "title": "NextGen Supplies Service Level Agreement",
            "document_type": DocumentType.SUPPLIER_SLA.value,
            "supplier_id": nextgen_id,
            "filename": "nextgen_supplies_sla_2026.pdf",
            "generator": lambda p: generate_nextgen_sla(p, nextgen_id),
        },
        {
            "id_tag": "DOC-6",
            "title": "TechSource Lanka Performance Review — Q3 2026",
            "document_type": DocumentType.SUPPLIER_PERFORMANCE_REPORT.value,
            "supplier_id": techsource_id,
            "filename": "supplier_performance_review_q3_2026_techsource.pdf",
            "generator": lambda p: generate_techsource_performance_review(p, techsource_id),
        },
        {
            "id_tag": "DOC-7",
            "title": "Digital Distribution Lanka Performance Review — Q3 2026",
            "document_type": DocumentType.SUPPLIER_PERFORMANCE_REPORT.value,
            "supplier_id": digital_id,
            "filename": "supplier_performance_review_q3_2026_digital.pdf",
            "generator": lambda p: generate_digital_performance_review(p, digital_id),
        },
        {
            "id_tag": "DOC-8",
            "title": "NextGen Supplies Performance Review — Q3 2026",
            "document_type": DocumentType.SUPPLIER_PERFORMANCE_REPORT.value,
            "supplier_id": nextgen_id,
            "filename": "supplier_performance_review_q3_2026_nextgen.pdf",
            "generator": lambda p: generate_nextgen_performance_review(p, nextgen_id),
        },
    ]

    print("\n--- Checking for existing demo documents to clean up ---")
    demo_titles = {spec["title"] for spec in doc_specs}
    demo_titles.add("Supplier Performance Review — Q3 2026") # historical title
    db_clean = SessionLocal()
    try:
        existing_docs = db_clean.execute(
            select(Document).where(Document.title.in_(demo_titles))
        ).scalars().all()
        for ed in existing_docs:
            print(f"  [-] Removing existing document record ID {ed.id}: '{ed.title}'")
            delete_document(db_clean, ed.id)
    finally:
        db_clean.close()

    print("\n--- Generating PDF files ---")
    generated_files = []
    for spec in doc_specs:
        file_path = output_dir / spec["filename"]
        spec["generator"](str(file_path))
        file_size = os.path.getsize(file_path)
        print(f"  [+] {spec['title']} ({file_size:,} bytes) -> {file_path.name}")
        generated_files.append((spec, file_path))

    print("\n--- Uploading via Document Management API (POST /api/v1/documents) ---")
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {auth_token}"}

    uploaded_records = []
    for spec, file_path in generated_files:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()

        form_data = {
            "title": spec["title"],
            "document_type": spec["document_type"],
        }
        if spec["supplier_id"] is not None:
            form_data["supplier_id"] = str(spec["supplier_id"])

        files = {
            "file": (spec["filename"], pdf_bytes, "application/pdf")
        }

        response = client.post(
            "/api/v1/documents",
            data=form_data,
            files=files,
            headers=headers,
        )

        if response.status_code != 201:
            print(f"FAILED to upload {spec['title']}: status={response.status_code}")
            print(f"Response: {response.text}")
            sys.exit(1)

        doc_json = response.json()
        uploaded_records.append(doc_json)
        print(f"  [OK] Uploaded ID {doc_json['id']}: '{doc_json['title']}'")

    print("\n" + "=" * 60)
    print("ALL 8 DEMO DOCUMENTS SUCCESSFULLY GENERATED, UPLOADED, AND INDEXED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
