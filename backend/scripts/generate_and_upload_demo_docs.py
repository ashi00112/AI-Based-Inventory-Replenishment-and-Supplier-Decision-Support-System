"""
SmartSupply Electronics — Demo Document Generation & API Upload Script.

Generates 6 valid, professional PDF documents using ReportLab and uploads them
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
    """Builds a cohesive, modern typographic hierarchy for enterprise PDFs."""
    styles = getSampleStyleSheet()
    
    # Custom color palette
    c_primary = colors.HexColor("#0F172A")    # Slate 900
    c_blue = colors.HexColor("#1D4ED8")       # Blue 700
    c_accent = colors.HexColor("#0369A1")     # Sky 700
    c_body = colors.HexColor("#334155")       # Slate 700
    c_muted = colors.HexColor("#64748B")      # Slate 500

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
        textColor=c_blue,
        spaceAfter=12,
    ))

    styles.add(ParagraphStyle(
        name="MetaLabel",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=c_muted,
    ))

    styles.add(ParagraphStyle(
        name="MetaValue",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=c_primary,
    ))

    styles.add(ParagraphStyle(
        name="SectionHeading",
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=c_primary,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="SubSectionHeading",
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13,
        textColor=c_accent,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    ))

    styles.add(ParagraphStyle(
        name="ClauseBody",
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=c_body,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="ClauseBodyBold",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=13,
        textColor=c_primary,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        name="BulletText",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=c_body,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3,
    ))

    styles.add(ParagraphStyle(
        name="CalloutText",
        fontName="Helvetica-Oblique",
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1E293B"),
    ))

    styles.add(ParagraphStyle(
        name="TableHeader",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    ))

    styles.add(ParagraphStyle(
        name="TableCell",
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=c_body,
    ))

    styles.add(ParagraphStyle(
        name="TableCellBold",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
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

    # 4 columns: Label1, Val1, Label2, Val2
    t = Table(data, colWidths=[110, 135, 100, 142])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor("#E2E8F0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
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
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
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

    # Title block
    story.append(Paragraph("SmartSupply Procurement Policy 2026", styles["DocTitle"]))
    story.append(Paragraph("Enterprise Commercial Directives & Supply Chain Governance Guidelines", styles["DocSubtitle"]))
    
    meta_items = [
        [("Document Identifier", "POL-PROC-2026-V1"), ("Effective Date", "January 01, 2026")],
        [("Governance Authority", "Executive Procurement Council"), ("Applicability", "Enterprise-Wide / Global")],
        [("Document Type", "Procurement Policy"), ("Review Cadence", "Annual Mandatory Review")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 14))

    # 1.0 Objectives & Governance
    story.append(Paragraph("1.0 Strategic Procurement Objectives and Principles", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 The principal mission of SmartSupply Electronics is to maintain continuous availability of high-quality electronics, "
        "accessories, and computing peripherals while minimizing total cost of ownership (TCO) and operational risk across the distribution network.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "1.2 All purchasing activities shall operate under four core principles: commercial transparency, competitive bidding, strict ethical integrity, "
        "and vendor accountability. Procurement officers must ensure that supplier selections optimize lead time, product reliability, and financial terms.",
        styles["ClauseBody"]
    ))

    # 2.0 Approved Supplier Qualification
    story.append(Paragraph("2.0 Approved Supplier Qualification and Onboarding", styles["SectionHeading"]))
    story.append(Paragraph(
        "2.1 Only certified vendors registered on the SmartSupply Approved Vendor List (AVL) may receive commercial purchase commitments. "
        "Prospective suppliers must undergo a formal qualification process including validation of business registration, statutory tax compliance "
        "(VAT/TIN), financial solvency checks, and adherence to international product safety and environmental certifications (RoHS, CE, and ISO 9001).",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "2.2 Active vendors are subject to annual performance accreditation. Suppliers that maintain an On-Time In-Full (OTIF) rate above 95% and a product "
        "defect rate below 1.5% qualify for preferred vendor status, receiving priority allocation in high-volume product categories.",
        styles["ClauseBody"]
    ))

    # 3.0 Purchase Approval Authority & Financial Thresholds
    story.append(Paragraph("3.0 Purchase Approval Authority & Expenditure Thresholds", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 To enforce financial governance, all procurement commitments must obtain prior written authorization in accordance with graduated spending tiers. "
        "Splitting purchase requisitions to evade delegated financial authority levels is strictly forbidden and constitutes a material compliance violation.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "• <b>Tier 1 (Up to LKR 100,000):</b> Operational Purchasing Supervisor approval required. Applicable to standard recurring replenishment orders within budget.",
        styles["BulletText"]
    ))
    story.append(Paragraph(
        "• <b>Tier 2 (LKR 100,001 to LKR 500,000):</b> Procurement Manager approval required. Requires comparative price evaluation across at least two approved suppliers.",
        styles["BulletText"]
    ))
    story.append(Paragraph(
        "• <b>Tier 3 (Exceeding LKR 500,000):</b> High-value purchase approval requiring joint sign-off from the Chief Financial Officer (CFO) and the Vice President of Operations.",
        styles["BulletText"]
    ))
    story.append(Spacer(1, 4))
    story.append(create_callout_box(
        styles,
        "What approval is needed for a high-value purchase? Any procurement commitment exceeding LKR 500,000 requires joint executive authorization "
        "from the Chief Financial Officer (CFO) and the Vice President of Operations following competitive bid review.",
        "GOVERNANCE RULE"
    ))
    story.append(Spacer(1, 6))

    # 4.0 Emergency Procurement Protocol
    story.append(Paragraph("4.0 Emergency Procurement Protocol and Lead-Time Prioritization", styles["SectionHeading"]))
    story.append(Paragraph(
        "4.1 An emergency procurement condition is declared when critical stock depletion directly threatens fulfillment operations, key retail partnerships, "
        "or warranty replacement guarantees.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "4.2 <b>Can emergency orders prioritize delivery speed over price?</b> Yes. In declared emergency procurement scenarios, the Procurement Department is "
        "expressly authorized to prioritize supplier delivery speed and immediate stock availability over the lowest purchase price. "
        "Procurement officers may select premium expedited suppliers and accept pricing up to 20% above standard contract benchmarks if the supplier guarantees delivery within 48 hours.",
        styles["ClauseBodyBold"]
    ))
    story.append(Paragraph(
        "4.3 All emergency purchase orders must be documented with an Emergency Justification Form and submitted to the Procurement Manager within 48 business hours of issuance.",
        styles["ClauseBody"]
    ))

    # 5.0 Supplier Selection Principles
    story.append(Paragraph("5.0 Supplier Selection Principles and Dual Sourcing", styles["SectionHeading"]))
    story.append(Paragraph(
        "5.1 Commercial awards shall be determined using a weighted supplier scorecard: Unit Price and Commercial Terms (30%), Demonstrated On-Time Delivery Reliability (25%), "
        "Historical Quality and Defect Rates (25%), and Warranty/RMA Turnaround Speed (20%).",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "5.2 For revenue-critical product lines (Class A inventory), SmartSupply mandates a dual-sourcing model. The primary supplier shall receive approximately 60% to 70% "
        "of volume, while a secondary approved vendor retains 30% to 40% to preserve operational redundancy and rapid surge fulfillment capability.",
        styles["ClauseBody"]
    ))

    # 6.0 Quality Standards and Defect Handling
    story.append(Paragraph("6.0 Quality Standards, Receiving Inspection, and Defect Handling", styles["SectionHeading"]))
    story.append(Paragraph(
        "6.1 All inbound shipments must pass receiving quality inspection at the central distribution center. Shipments must conform strictly to specifications.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "6.2 The enterprise maximum allowable defect rate is established at 1.5% of delivered lot quantity. If incoming sampling detects a defect rate exceeding 1.5%, "
        "the entire batch shall be quarantined. The supplier must issue a Return Merchandise Authorization (RMA) within 48 hours and cover all return logistics costs.",
        styles["ClauseBody"]
    ))

    # 7.0 Delivery Schedules and Packaging Standards
    story.append(Paragraph("7.0 Delivery Schedules, Logistics, and Packaging Standards", styles["SectionHeading"]))
    story.append(Paragraph(
        "7.1 Suppliers must achieve an aggregate On-Time Delivery (OTD) rate of no less than 95.0%. Deliveries are deemed on-time only when received at the designated warehouse "
        "dock on or before the contractual delivery date stated on the Purchase Order.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "7.2 Electronic components and computer peripherals must be packaged in electrostatic discharge (ESD) protective containers, moisture-barrier bags, and barcode-labeled cartons "
        "identifying the SmartSupply SKU code, purchase order number, and batch number.",
        styles["ClauseBody"]
    ))

    # 8.0 Supplier Escalation and Non-Performance Remediation
    story.append(Paragraph("8.0 Supplier Escalation and Non-Performance Remediation", styles["SectionHeading"]))
    story.append(Paragraph(
        "8.1 <b>When can a supplier be escalated for poor performance?</b> A supplier shall be subject to formal escalation under any of the following non-performance triggers: "
        "(a) On-Time In-Full delivery rate falls below 90.0% across two consecutive monthly reporting cycles; "
        "(b) Product defect rate exceeds 2.5% in any single delivery batch or 1.5% on a 60-day moving average; "
        "(c) Failure to resolve open RMA warranty replacements within contractual SLA turnaround limits; or "
        "(d) Repeated failure to provide advance late-delivery notices.",
        styles["ClauseBodyBold"]
    ))
    story.append(Paragraph(
        "8.2 Escalation follows a three-stage remediation framework: "
        "Stage 1 requires a Corrective Action Plan (CAP) submitted within 5 business days; "
        "Stage 2 freezes new purchase order awards and re-allocates volume to secondary suppliers; "
        "Stage 3 initiates supplier disqualification and contractual de-listing.",
        styles["ClauseBody"]
    ))

    # 9.0 Exceptions and Documentation Requirements
    story.append(Paragraph("9.0 Exceptions, Waivers, and Documentation Compliance", styles["SectionHeading"]))
    story.append(Paragraph(
        "9.1 Sole-source vendor engagements or policy exemptions require written justification signed by the Head of Supply Chain and the Financial Controller prior to PO commitment.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "9.2 To maintain strict audit readiness, accounts payable operates under a mandatory Three-Way Matching protocol: the Purchase Order (PO), warehouse Goods Received Note (GRN), "
        "and the Supplier Tax Invoice must match perfectly in SKU quantity and agreed unit price before payment disbursement. All records must be archived digitally for 7 years.",
        styles["ClauseBody"]
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

    # Title block
    story.append(Paragraph("SmartSupply Inventory Replenishment Policy 2026", styles["DocTitle"]))
    story.append(Paragraph("Standard Operating Procedures for Inventory Planning, Safety Stock & Stockout Mitigation", styles["DocSubtitle"]))
    
    meta_items = [
        [("Document Identifier", "POL-INVR-2026-V1"), ("Effective Date", "January 01, 2026")],
        [("Operational Scope", "Distribution Warehouses & Retail Hubs"), ("Applicability", "Enterprise Inventory Management")],
        [("Document Type", "Inventory Replenishment Policy"), ("Target Service Level", "98% Class A / 95% Class B")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 14))

    # 1.0 Operational Scope & Objectives
    story.append(Paragraph("1.0 Purpose and Operational Scope", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 This policy establishes the standard replenishment principles, mathematical reorder-point calculations, and emergency inventory mitigation protocols "
        "for SmartSupply Electronics. The overarching objective is to maintain uninterrupted product availability while optimizing working capital and warehouse holding costs.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "1.2 Inventory planning parameters apply across all distribution centers, regional fulfillment hubs, and retail outlets, governing both regular automated ordering "
        "and contingency replenishment procedures.",
        styles["ClauseBody"]
    ))

    # 2.0 Reorder Point (ROP) Usage and Formula
    story.append(Paragraph("2.0 Reorder Point (ROP) Methodology and Safety Stock Calculation", styles["SectionHeading"]))
    story.append(Paragraph(
        "2.1 All inventory items are managed through an automated continuous-review inventory control system. A replenishment purchase requisition is automatically triggered "
        "whenever the Net Available Inventory falls to or below the calculated Reorder Point (ROP).",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "2.2 <b>Standard ROP Calculation Formula:</b><br/>"
        "<code>Reorder Point (ROP) = (Average Daily Demand × Supplier Lead Time in Days) + Safety Stock</code><br/>"
        "Where Average Daily Demand is derived from a 30-day exponentially smoothed sales velocity, and Supplier Lead Time reflects the supplier's verified contractual delivery window.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "2.3 Safety Stock is mathematically calibrated based on demand volatility and supplier lead-time standard deviation. Target service levels are defined as: "
        "98.0% availability for Class A fast-moving peripherals (e.g. Wireless Mice, SSDs, AC1200 Routers), 95.0% for Class B regular accessories, and 90.0% for Class C slow consumables.",
        styles["ClauseBody"]
    ))

    # 3.0 Lead Time Demand & Pipeline Accounting
    story.append(Paragraph("3.0 Demand During Lead Time and Pipeline Stock Consideration", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 Demand during lead time represents the total projected sales volume between purchase order transmission and dock receiving. "
        "Planners must continuously audit actual vendor lead time performance against contractual parameters to detect fulfillment drift.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "3.2 <b>Incoming Pipeline Stock Consideration:</b> Replenishment triggers must strictly account for open purchase orders in the pipeline. "
        "The system evaluates Net Available Stock rather than physical on-hand stock alone:<br/>"
        "<code>Net Available Stock = (Physical On-Hand Stock + Confirmed In-Transit Open POs) - (Unfulfilled Customer Backorders + Allocated Shipments)</code><br/>"
        "New purchase orders shall not be generated if open in-transit POs are sufficient to raise the inventory position above the target maximum level.",
        styles["ClauseBody"]
    ))

    # 4.0 Stockout Risk Handling
    story.append(Paragraph("4.0 Stockout-Risk Handling and Critical Item Prioritization", styles["SectionHeading"]))
    story.append(Paragraph(
        "4.1 <b>How should high stockout risk affect replenishment?</b> When physical on-hand stock falls below 50% of the allocated safety stock, or when projected days "
        "of inventory coverage fall below 3 business days for Class A items, the SKU is immediately designated as 'High Stockout Risk'. "
        "Under high stockout risk conditions, the following mandatory actions occur:<br/>"
        "• <b>Immediate Purchase Order Release:</b> Replenishment orders are generated immediately without waiting for standard weekly batch ordering cycles.<br/>"
        "• <b>Buffer Quantity Uplift:</b> The calculated economic order quantity is automatically increased by a 25% contingency buffer.<br/>"
        "• <b>Fast-Lead-Time Supplier Routing:</b> If the primary supplier's standard lead time exceeds 3 days, purchasing is authorized to place orders with pre-approved rapid-delivery suppliers (e.g., Digital Distribution Lanka) to secure immediate bridge stock.<br/>"
        "• <b>Executive Escalation:</b> Daily inventory exception alerts are transmitted directly to the Inventory Control Manager until stock levels recover above ROP.",
        styles["ClauseBodyBold"]
    ))
    story.append(Spacer(1, 4))
    story.append(create_callout_box(
        styles,
        "High Stockout Risk mandates immediate order release, a 25% replenishment buffer uplift, authorization for expedited supplier routing, and daily management escalation.",
        "RISK PROTOCOL"
    ))
    story.append(Spacer(1, 6))

    # 5.0 Emergency Replenishment Operations
    story.append(Paragraph("5.0 Emergency Replenishment Operations and Order Splitting", styles["SectionHeading"]))
    story.append(Paragraph(
        "5.1 When an unexpected demand spike or supplier stockout threatens zero physical inventory, the emergency replenishment protocol is engaged. "
        "Expedited logistics surcharges and courier air-freight options are authorized to protect customer delivery commitments.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "5.2 <b>Dual-Supplier Order Splitting:</b> In severe shortage situations, large replenishment batches may be split across two qualified vendors: "
        "a 30% expedited emergency tranche dispatched via a rapid-lead supplier (2-3 day delivery), paired with a 70% bulk commercial tranche dispatched via a cost-competitive bulk supplier (5-7 day delivery).",
        styles["ClauseBody"]
    ))

    # 6.0 Slow-Moving and Obsolete Inventory (SLOB)
    story.append(Paragraph("6.0 Slow-Moving and Obsolete Inventory (SLOB) Management", styles["SectionHeading"]))
    story.append(Paragraph(
        "6.1 Any SKU with zero outbound commercial transactions for 90 consecutive days is formally classified as Slow-Moving. "
        "Items with zero movement for 180 days are categorized as Dormant/Obsolete. A monthly inventory carrying penalty of 2.0% is attributed to slow-moving inventory balances.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "6.2 Remediation procedures for SLOB items include: (a) exercising supplier contract stock rotation provisions for exchange into fast-moving SKUs; "
        "(b) promotional channel bundling; (c) progressive price markdowns; and (d) formal disposal or salvage write-downs with CFO approval.",
        styles["ClauseBody"]
    ))

    # 7.0 Review & Escalation Cadence
    story.append(Paragraph("7.0 Review Cadence, Escalation Hierarchy, and Audit Rules", styles["SectionHeading"]))
    story.append(Paragraph(
        "7.1 A cross-functional Inventory Exceptions Committee (comprising Inventory Planners, Procurement Specialists, and Warehouse Managers) meets weekly to review "
        "stockout incidents, stockout-risk SKUs, safety stock parameter variances, and vendor lead time drifts.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "7.2 Any stockout incident affecting Class A products must be formally documented with a Root Cause Analysis (RCA) report and submitted to the VP of Supply Chain within 3 business days.",
        styles["ClauseBody"]
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

    # Title block
    story.append(Paragraph("TechSource Lanka Service Level Agreement", styles["DocTitle"]))
    story.append(Paragraph("Master Commercial Supply & Service Level Terms — Balanced Service Profile", styles["DocSubtitle"]))
    
    meta_items = [
        [("Vendor Name", "TechSource Lanka"), ("Supplier Code", "DEMO-SUP-001")],
        [("Agreement Ref", f"SLA-TSL-2026-ID{supplier_id}"), ("Effective Date", "January 01, 2026")],
        [("Document Type", "Supplier Service Level Agreement"), ("Review Cycle", "Annual Commercial Review")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 14))

    # 1.0 Parties and Scope
    story.append(Paragraph("1.0 Agreement Parties and Strategic Operational Scope", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 This Service Level Agreement (SLA) is entered into between SmartSupply Electronics Pvt Ltd and TechSource Lanka "
        "(Business Registration: PV-89104, Registered Address: 45 R.A. De Mel Mawatha, Colombo 03, Sri Lanka).",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "1.2 TechSource Lanka serves as a strategic, balanced-tier supplier providing standard computer peripherals, wireless input devices, "
        "aluminum ergonomic laptop stands, high-speed HDMI cables, USB storage media, and high-volume office supplies across the SmartSupply retail catalog.",
        styles["ClauseBody"]
    ))

    # 2.0 Order Processing and Commercial Terms Governance
    story.append(Paragraph("2.0 Order Processing and Commercial Terms Governance", styles["SectionHeading"]))
    story.append(Paragraph(
        "2.1 <b>Commercial Terms and Order Processing:</b> Product-specific MOQ, unit cost, and standard lead time are maintained in "
        "SmartSupply's approved supplier commercial records. This SLA governs service obligations and exceptions. "
        "TechSource Lanka commits to fulfilling purchase orders according to the operational parameters established in SmartSupply's central catalog.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "2.2 Formal written order acknowledgement must be transmitted to SmartSupply within 24 business hours of PO receipt, confirming delivery dates and SKU allocations.",
        styles["ClauseBody"]
    ))

    # 3.0 Delivery Expectations & Late Delivery
    story.append(Paragraph("3.0 Delivery Expectations, Late Delivery Notification, and Penalties", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 TechSource Lanka commits to maintaining a minimum monthly On-Time Delivery (OTD) rate of 95.0%.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "3.2 <b>What happens if a supplier delivers late?</b> If TechSource Lanka anticipates any schedule slippage, it is contractually required to provide formal "
        "written notification to SmartSupply at least 24 hours prior to the scheduled delivery date, specifying the cause and revised delivery schedule. "
        "If delivery is delayed beyond the confirmed date without prior written approval, SmartSupply is entitled to deduct a late-delivery penalty rebate of 1.5% "
        "of the delayed order value for each calendar week of delay (or fraction thereof), up to a maximum cap of 10.0%. "
        "If delay exceeds 14 calendar days, SmartSupply reserves the contractual right to cancel the order without cancellation liability and procure replacement goods "
        "from an alternative vendor, with TechSource Lanka liable for any proven purchase price variance.",
        styles["ClauseBodyBold"]
    ))
    story.append(Spacer(1, 4))
    story.append(create_callout_box(
        styles,
        "Late delivery requires 24h advance notice. Penalty rebate is 1.5% per week of delay up to a 10.0% cap. Orders delayed > 14 days may be cancelled with supplier covering price variances.",
        "LATE DELIVERY CLAUSE"
    ))
    story.append(Spacer(1, 6))

    # 4.0 Damaged Shipments & Defective Goods
    story.append(Paragraph("4.0 Damaged Shipments, Inspection Window, and Return Logistics", styles["SectionHeading"]))
    story.append(Paragraph(
        "4.1 SmartSupply shall inspect received cartons within 3 business days of dock delivery. In the event of physical transit damage, packaging breaches, "
        "or carton discrepancies, SmartSupply will submit written notification and photographic documentation to <code>orders@techsourcelanka.lk</code>.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "4.2 TechSource Lanka shall arrange and pay for all return courier and freight charges for non-conforming or damaged shipments. Damaged units shall be credited or replaced within 5 business days.",
        styles["ClauseBody"]
    ))

    # 5.0 Replacement and Warranty Conditions
    story.append(Paragraph("5.0 Replacement Policy, Warranty Conditions, and RMA Turnaround", styles["SectionHeading"]))
    story.append(Paragraph(
        "5.1 <b>What is the replacement policy for defective goods?</b> TechSource Lanka provides a standard 12-month manufacturer replacement warranty across all electronic products. "
        "When defective or non-functional items are identified and reported under Return Merchandise Authorization (RMA), TechSource Lanka guarantees full replacement with brand-new, "
        "factory-sealed units within 5 business days of RMA confirmation. For critical retail customer warranty returns, TechSource Lanka supports advance replacement dispatch within 48 hours upon mutual agreement.",
        styles["ClauseBodyBold"]
    ))
    story.append(Paragraph(
        "5.2 Replacement units carry the full balance of the original warranty period or 90 days, whichever is longer.",
        styles["ClauseBody"]
    ))

    # 6.0 Order Cancellation Rules
    story.append(Paragraph("6.0 Order Cancellation Rules and Restocking Conditions", styles["SectionHeading"]))
    story.append(Paragraph(
        "6.1 SmartSupply may cancel any confirmed Purchase Order free of charge provided written cancellation notice is received prior to warehouse dispatch "
        "(minimum 24 hours prior to scheduled carrier pick-up). If cancellation is submitted after dispatch, a nominal restocking fee of 5.0% applies to non-custom items.",
        styles["ClauseBody"]
    ))

    # 7.0 Emergency Order Handling
    story.append(Paragraph("7.0 Emergency Order Handling and Expedited Dispatch", styles["SectionHeading"]))
    story.append(Paragraph(
        "7.1 TechSource Lanka supports an emergency fast-track fulfillment service for critical stockout mitigation. Emergency purchase orders receive prioritized warehouse queue handling, "
        "guaranteeing dispatch within 48 hours of order confirmation.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "7.2 Emergency orders are subject to a 10.0% expedited logistics surcharge and a minimum order batch of 15 units. SmartSupply is permitted up to two emergency expedited orders per calendar month.",
        styles["ClauseBody"]
    ))

    # 8.0 Escalation Procedure & Governance
    story.append(Paragraph("8.0 Escalation Procedure, Account Management, and Governance", styles["SectionHeading"]))
    story.append(Paragraph(
        "8.1 Operational communications and daily order coordination are managed through designated contacts:<br/>"
        "• <b>Level 1 (Account Operations):</b> Kamal Silva, Senior Key Account Manager | Tel: +94 11 234 1101 | Email: orders@techsourcelanka.lk<br/>"
        "• <b>Level 2 (Executive Escalation):</b> Nuwan Jayasuriya, Commercial Operations Director | Tel: +94 11 234 1100 | Email: nuwan.j@techsourcelanka.lk",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "8.2 Formal executive review meetings shall take place quarterly to review delivery scorecards, RMA resolution speed, and upcoming inventory forecasts.",
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

    # Title block
    story.append(Paragraph("Digital Distribution Lanka Service Level Agreement", styles["DocTitle"]))
    story.append(Paragraph("Master Commercial Supply & Service Level Terms — Rapid Fulfillment & Emergency Support Profile", styles["DocSubtitle"]))
    
    meta_items = [
        [("Vendor Name", "Digital Distribution Lanka"), ("Supplier Code", "DEMO-SUP-002")],
        [("Agreement Ref", f"SLA-DDL-2026-ID{supplier_id}"), ("Effective Date", "January 01, 2026")],
        [("Document Type", "Supplier Service Level Agreement"), ("Specialization", "Fast Lead Times & Express Peripherals")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 14))

    # 1.0 Strategic Role & Scope
    story.append(Paragraph("1.0 Agreement Parties and Strategic Commercial Scope", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 This Service Level Agreement (SLA) is established between SmartSupply Electronics Pvt Ltd and Digital Distribution Lanka "
        "(Business Registration: PV-77412, Registered Address: 112 Duplication Road, Colombo 04, Sri Lanka).",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "1.2 Digital Distribution Lanka is designated as SmartSupply's primary rapid-fulfillment partner, specializing in ultra-short lead times, high-speed automated dispatch, "
        "solid-state storage, USB-C multi-port hubs, premium audio headsets, and fast-response emergency replenishment.",
        styles["ClauseBody"]
    ))

    # 2.0 Order Processing and Commercial Terms Governance
    story.append(Paragraph("2.0 Order Processing and Commercial Terms Governance", styles["SectionHeading"]))
    story.append(Paragraph(
        "2.1 <b>Commercial Terms and Rapid Order Processing:</b> Product-specific MOQ, unit cost, and standard lead time are maintained in "
        "SmartSupply's approved supplier commercial records. This SLA governs service obligations and exceptions. "
        "Digital Distribution Lanka operates automated high-density warehouse picking and prioritizes expedited fulfillment pipelines across all catalog categories.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "2.2 Automated Electronic Data Interchange (EDI) and email order confirmations are generated within 4 business hours of order placement.",
        styles["ClauseBody"]
    ))

    # 3.0 Delivery Expectations & Late Delivery
    story.append(Paragraph("3.0 High-Delivery Reliability, Late Delivery Notice, and Strict Penalties", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 Digital Distribution Lanka contractually commits to an industry-leading On-Time Delivery (OTD) rate of 98.0%.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "3.2 <b>What happens if a supplier delivers late?</b> Given the premium rapid-fulfillment status of Digital Distribution Lanka, delay thresholds are strictly enforced. "
        "The supplier must provide written notice to SmartSupply within 12 hours of identifying any operational or transportation impediment. "
        "If an order is not delivered within the contractual lead time, a late-delivery penalty of 2.0% of the affected shipment value is assessed for each calendar day of delay, "
        "up to a maximum penalty cap of 15.0%. Any delivery exceeding 5 business days of delay constitutes a fundamental breach, entitling SmartSupply to immediate cancellation "
        "and full refund of any deposits, plus liquidated damages for stockout remediation.",
        styles["ClauseBodyBold"]
    ))
    story.append(Spacer(1, 4))
    story.append(create_callout_box(
        styles,
        "Late delivery notice required within 12 hours. Daily penalty of 2.0% per business day up to a 15.0% maximum cap. Delays over 5 days permit immediate contract default remedies.",
        "STRICT SLA CLAUSE"
    ))
    story.append(Spacer(1, 6))

    # 4.0 Damaged Shipments & Immediate Cross-Shipment
    story.append(Paragraph("4.0 Damaged Shipments and Immediate Cross-Shipment Protocol", styles["SectionHeading"]))
    story.append(Paragraph(
        "4.1 Receiving inspection must be concluded within 48 hours of dock arrival. Transit claims must be filed via email to <code>supply@digitaldistribution.lk</code> with photographic evidence.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "4.2 <b>Immediate Cross-Shipment Replacement:</b> Upon receipt of valid photo documentation of shipping damage or defective items, Digital Distribution Lanka dispatches "
        "replacement units immediately within 24 hours, without requiring the returned items to reach its facility first. Digital Distribution Lanka covers all reverse freight.",
        styles["ClauseBodyBold"]
    ))

    # 5.0 Replacement and Warranty Conditions
    story.append(Paragraph("5.0 Rapid Replacement Policy and Extended Storage Warranty", styles["SectionHeading"]))
    story.append(Paragraph(
        "5.1 <b>What is the replacement policy for defective goods?</b> Digital Distribution Lanka guarantees an expedited RMA turnaround cycle of 48 to 72 hours for all verified "
        "hardware defects. Returned items are inspected at a dedicated rapid-diagnostic test bench, and brand-new replacements are dispatched immediately.",
        styles["ClauseBodyBold"]
    ))
    story.append(Paragraph(
        "5.2 SSD storage and semiconductor components carry a comprehensive 24-month manufacturer warranty. For mission-critical storage failures, advance buffer replacement is permanently supported.",
        styles["ClauseBody"]
    ))

    # 6.0 Order Cancellation Rules
    story.append(Paragraph("6.0 Order Cancellation Rules and Automated Fulfillment Constraints", styles["SectionHeading"]))
    story.append(Paragraph(
        "6.1 Due to automated robotic fulfillment and same-day packaging workflows, purchase orders can only be cancelled within 6 hours of electronic submission. "
        "Once a shipment enters the automated packing queue, orders are strictly non-cancellable.",
        styles["ClauseBody"]
    ))

    # 7.0 Emergency & Same-Day Replenishment
    story.append(Paragraph("7.0 Emergency Replenishment and Same-Day Courier Dispatch", styles["SectionHeading"]))
    story.append(Paragraph(
        "7.1 Digital Distribution Lanka maintains a dedicated emergency replenishment pipeline capable of dispatching stock within 24 hours of emergency order confirmation for critical stockout emergencies.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "7.2 Emergency orders are subject to a 15.0% expedited logistics surcharge and a minimum order batch of 20 units per SKU. Delivery is executed via dedicated priority courier.",
        styles["ClauseBody"]
    ))

    # 8.0 Escalation Procedure & Governance
    story.append(Paragraph("8.0 Escalation Procedure and Dedicated Key Account Support", styles["SectionHeading"]))
    story.append(Paragraph(
        "8.1 Dedicated commercial and technical points of contact:<br/>"
        "• <b>Level 1 (Account Lead):</b> Dilani Perera, Senior Account Manager | Tel: +94 11 258 2202 | Email: supply@digitaldistribution.lk<br/>"
        "• <b>Level 2 (Executive Escalation):</b> Kanishka Wickramaratne, General Manager of Operations | Tel: +94 11 258 2200 | Email: kanishka@digitaldistribution.lk",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "8.2 Monthly operational SLA compliance reviews are conducted digitally on the 5th of each month, tracking 30-day fulfillment velocity and warranty statistics.",
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

    # Title block
    story.append(Paragraph("NextGen Supplies Service Level Agreement", styles["DocTitle"]))
    story.append(Paragraph("Master Commercial Supply & Service Level Terms — High-Volume Bulk & Cost-Competitive Profile", styles["DocSubtitle"]))
    
    meta_items = [
        [("Vendor Name", "NextGen Supplies"), ("Supplier Code", "DEMO-SUP-003")],
        [("Agreement Ref", f"SLA-NGS-2026-ID{supplier_id}"), ("Effective Date", "January 01, 2026")],
        [("Document Type", "Supplier Service Level Agreement"), ("Commercial Focus", "High-Volume Wholesale & Bulk Rebates")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 14))

    # 1.0 Strategic Role & Commercial Focus
    story.append(Paragraph("1.0 Agreement Parties and Strategic Commercial Scope", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 This Service Level Agreement (SLA) is entered into between SmartSupply Electronics Pvt Ltd and NextGen Supplies "
        "(Business Registration: PV-62391, Registered Address: 88 High Level Road, Nugegoda, Sri Lanka).",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "1.2 NextGen Supplies is designated as SmartSupply's primary high-volume commercial wholesale partner, providing the most competitive bulk unit economics "
        "across computer mice, mechanical keyboards, multi-port USB hubs, external SSDs, high-performance Wi-Fi routers, and mobile accessories.",
        styles["ClauseBody"]
    ))

    # 2.0 Bulk Order Terms and Commercial Governance
    story.append(Paragraph("2.0 Bulk Order Terms and Commercial Governance", styles["SectionHeading"]))
    story.append(Paragraph(
        "2.1 <b>Commercial Pricing and Minimum Order Terms:</b> Product-specific MOQ, unit cost, and standard lead time are maintained in "
        "SmartSupply's approved supplier commercial records. This SLA governs service obligations and exceptions. "
        "NextGen Supplies provides high-volume commercial wholesale fulfillment and volume discount rebates across approved catalog lines.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "2.2 <b>Tiered Volume Discount Rebate:</b> Single purchase orders exceeding 100 aggregated units across any product line automatically earn an additional "
        "4.0% commercial volume rebate, applied as a direct credit on the monthly commercial statement.",
        styles["ClauseBody"]
    ))

    # 3.0 Delivery Expectations & Late Delivery
    story.append(Paragraph("3.0 Delivery Expectations, Late Delivery Notice, and Rebates", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 NextGen Supplies commits to an On-Time In-Full (OTIF) fulfillment rate of 92.0%, reflecting consolidated bulk freight transit schedules.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "3.2 <b>What happens if a supplier delivers late?</b> NextGen Supplies must provide written notification at least 48 hours prior to the scheduled delivery date "
        "if container transit or customs delays arise. If an order is delayed beyond the confirmed delivery date without prior notification, SmartSupply is entitled to a credit note "
        "rebate of 1.0% of the delayed order value for each calendar week of delay, capped at a maximum of 6.0%. "
        "Due to volume shipping schedules, cancellation for delayed orders is permitted only after 21 calendar days of overdue status.",
        styles["ClauseBodyBold"]
    ))
    story.append(Spacer(1, 4))
    story.append(create_callout_box(
        styles,
        "Late delivery notice required 48 hours in advance. Credit note rebate is 1.0% per week of delay capped at 6.0%. Order cancellation permitted after 21 calendar days.",
        "BULK TERMS CLAUSE"
    ))
    story.append(Spacer(1, 6))

    # 4.0 Damaged Shipments & Batch RMA Policy
    story.append(Paragraph("4.0 Damaged Shipments, Inspection Window, and Batch RMA Reconciliation", styles["SectionHeading"]))
    story.append(Paragraph(
        "4.1 SmartSupply may inspect bulk carton receipts within 7 business days of warehouse delivery. Discrepancies shall be recorded on the delivery docket and reported to <code>sales@nextgensupplies.lk</code>.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "4.2 Damaged or defective units in bulk orders are consolidated into a monthly Batch RMA statement. NextGen Supplies issues account credit notes against pending invoices "
        "rather than individual replacement shipments, streamlining administrative reconciliation.",
        styles["ClauseBody"]
    ))

    # 5.0 Replacement and Extended Warranty Terms
    story.append(Paragraph("5.0 Replacement Policy, Extended Warranty, and Credit Notes", styles["SectionHeading"]))
    story.append(Paragraph(
        "5.1 <b>What is the replacement policy for defective goods?</b> NextGen Supplies provides an extended 18-month commercial warranty on all computer peripherals and networking hardware. "
        "Warranty RMA requests are processed within a standard turnaround window of 10 business days from receipt at the Nugegoda depot. "
        "For discontinued or superseded product lines, NextGen Supplies grants an immediate 100% financial credit note in lieu of physical replacement.",
        styles["ClauseBodyBold"]
    ))

    # 6.0 Flexible Order Cancellation Protocol
    story.append(Paragraph("6.0 Flexible Order Cancellation Protocol", styles["SectionHeading"]))
    story.append(Paragraph(
        "6.1 In alignment with wholesale bulk planning, SmartSupply may cancel or modify purchase orders without financial penalty up to 48 hours after electronic submission. "
        "Cancellations requested after 48 hours but prior to container dispatch incur a minor 3.0% administrative handling fee.",
        styles["ClauseBody"]
    ))

    # 7.0 Emergency Order Handling & Capacity Limits
    story.append(Paragraph("7.0 Emergency Order Handling and Wholesale Capacity Limits", styles["SectionHeading"]))
    story.append(Paragraph(
        "7.1 Due to bulk consolidated container movements, NextGen Supplies maintains limited emergency fulfillment capacity. "
        "SmartSupply is permitted a maximum of one emergency expedited order per calendar month, restricted to a maximum batch of 50 units.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "7.2 Expedited orders carry a 12.0% logistics fee and guarantee a 4-business-day expedited courier delivery to the Colombo central distribution facility.",
        styles["ClauseBody"]
    ))

    # 8.0 Escalation Procedure & Governance
    story.append(Paragraph("8.0 Escalation Procedure and Account Management", styles["SectionHeading"]))
    story.append(Paragraph(
        "8.1 Account coordination and commercial escalation structure:<br/>"
        "• <b>Level 1 (Wholesale Coordinator):</b> Rohan Wickramasinghe, Key Account Lead | Tel: +94 11 289 3303 | Email: sales@nextgensupplies.lk<br/>"
        "• <b>Level 2 (Executive Vice President):</b> Malinda Senanayake, VP of Commercial Distribution | Tel: +94 11 289 3300 | Email: malinda@nextgensupplies.lk",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "8.2 Formal volume rebate reviews and pricing index recalibrations are conducted semi-annually in June and December.",
        styles["ClauseBody"]
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated: {output_path}")


# =============================================================================
# DOCUMENT 6: Supplier Performance Review — Q3 2026
# =============================================================================
def generate_performance_review(output_path: str, supplier_id: int):
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

    # Title block
    story.append(Paragraph("Supplier Performance Review — Q3 2026", styles["DocTitle"]))
    story.append(Paragraph("Quarterly Vendor Evaluation & Contractual SLA Compliance Audit", styles["DocSubtitle"]))
    
    meta_items = [
        [("Vendor Evaluated", "TechSource Lanka"), ("Supplier Code", "DEMO-SUP-001")],
        [("Evaluation Period", "Q3 2026 (July 1 – Sept 30, 2026)"), ("Supplier ID Ref", f"SUP-{supplier_id}")],
        [("Document Type", "Supplier Performance Report"), ("Overall Score", "88.5 / 100 (Good Standing)")],
    ]
    story.append(create_meta_box(styles, meta_items))
    story.append(Spacer(1, 14))

    # 1.0 Executive Summary
    story.append(Paragraph("1.0 Executive Summary and Review Scope", styles["SectionHeading"]))
    story.append(Paragraph(
        "1.1 This performance evaluation report details the operational fulfillment, quality metrics, and SLA compliance of TechSource Lanka "
        "(Vendor Code: DEMO-SUP-001) for the third quarter of 2026 (July 01, 2026 to September 30, 2026).",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "1.2 During Q3 2026, SmartSupply Electronics issued a total of 28 Purchase Orders to TechSource Lanka, representing an aggregate procurement spend "
        "of LKR 4,680,000 across six major product categories. TechSource Lanka achieved an overall composite performance rating of 88.5 out of 100, "
        "satisfying core operational standards with minor variances in delivery timing.",
        styles["ClauseBody"]
    ))

    # 2.0 KPI Scorecard
    story.append(Paragraph("2.0 Key Performance Indicator (KPI) Scorecard", styles["SectionHeading"]))
    
    # Table data
    kpi_data = [
        [
            Paragraph("KPI Dimension", styles["TableHeader"]),
            Paragraph("SLA Target", styles["TableHeader"]),
            Paragraph("Q3 Actual", styles["TableHeader"]),
            Paragraph("Variance", styles["TableHeader"]),
            Paragraph("Status Assessment", styles["TableHeader"]),
        ],
        [
            Paragraph("On-Time In-Full (OTIF)", styles["TableCellBold"]),
            Paragraph("≥ 95.0%", styles["TableCell"]),
            Paragraph("94.2%", styles["TableCellBold"]),
            Paragraph("-0.8%", styles["TableCell"]),
            Paragraph("Minor Variance (Acceptable)", styles["TableCell"]),
        ],
        [
            Paragraph("Quality / Defect Rate", styles["TableCellBold"]),
            Paragraph("≤ 1.50%", styles["TableCell"]),
            Paragraph("1.28%", styles["TableCellBold"]),
            Paragraph("+0.22% (Better)", styles["TableCell"]),
            Paragraph("Compliant (Target Met)", styles["TableCell"]),
        ],
        [
            Paragraph("RMA Turnaround Speed", styles["TableCellBold"]),
            Paragraph("≤ 5.0 Days", styles["TableCell"]),
            Paragraph("4.2 Days", styles["TableCellBold"]),
            Paragraph("+0.8 Days (Better)", styles["TableCell"]),
            Paragraph("Exceeded SLA Benchmark", styles["TableCell"]),
        ],
        [
            Paragraph("Pricing & Invoice Accuracy", styles["TableCellBold"]),
            Paragraph("100.0%", styles["TableCell"]),
            Paragraph("100.0%", styles["TableCellBold"]),
            Paragraph("0.0%", styles["TableCell"]),
            Paragraph("Flawless Adherence", styles["TableCell"]),
        ],
        [
            Paragraph("Advance Delay Notice", styles["TableCellBold"]),
            Paragraph("≥ 24 Hours", styles["TableCell"]),
            Paragraph("36 Hours", styles["TableCellBold"]),
            Paragraph("+12 Hours", styles["TableCell"]),
            Paragraph("Proactive Notification", styles["TableCell"]),
        ],
    ]
    t_kpi = Table(kpi_data, colWidths=[120, 75, 75, 95, 122])
    t_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(t_kpi)
    story.append(Spacer(1, 10))

    # 3.0 SKU-Level Fulfillment Analysis
    story.append(Paragraph("3.0 SKU-Level Fulfillment Analysis & Performance Breakdown", styles["SectionHeading"]))
    story.append(Paragraph(
        "3.1 <b>TS-WM-01 (Wireless Mouse):</b> 8 purchase orders totaling 240 units were received with 100% on-time fulfillment and zero defective units detected during incoming inspection. "
        "Demonstrated outstanding production and delivery consistency in alignment with agreed catalog commitments.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "3.2 <b>TS-KB-RGB (Mechanical Keyboard):</b> 6 purchase orders totaling 90 units were fulfilled. One shipment suffered a 2-day delivery slip in mid-August due to Colombo customs port delays. "
        "Two units with unresponsive blue switches were identified; replacement units were dispatched by TechSource within 4 business days under RMA-2026-0814.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "3.3 <b>TS-LS-ALU (Laptop Stand) & TS-HDMI-2 (HDMI Cable):</b> Combined 10 orders totaling 350 units delivered with 100% on-time accuracy and pristine packaging compliance.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "3.4 <b>TS-PPR-A4 (Printer Paper):</b> 4 bulk orders (200 reams) fulfilled. One carton sustained minor external transit moisture damage, and TechSource Lanka immediately credited the damaged ream on Invoice INV-8921.",
        styles["ClauseBody"]
    ))

    # 4.0 Operational Incidents & Mitigations
    story.append(Paragraph("4.0 Operational Incidents and Corrective Resolutions", styles["SectionHeading"]))
    story.append(Paragraph(
        "4.1 <b>Incident LOG-2026-0814 (Customs Congestion):</b> On August 14, 2026, shipment PO-2026-0812 was impacted by logistics delays. "
        "Account Manager Kamal Silva formally alerted SmartSupply 36 hours in advance, allowing our inventory planning team to shift safety stock buffers and prevent retail backorders. "
        "TechSource voluntarily waived the shipping fee for that consignment.",
        styles["ClauseBody"]
    ))

    # 5.0 Escalation Triggers Evaluation
    story.append(Paragraph("5.0 Escalation Triggers and Corrective Action Plan (CAP) Review", styles["SectionHeading"]))
    story.append(Paragraph(
        "5.1 <b>When can a supplier be escalated for poor performance?</b> Under Section 8.3 of the SmartSupply Procurement Policy and Section 8.0 of the Master SLA, "
        "formal vendor escalation is triggered when: (a) OTIF delivery falls below 90.0% across two consecutive reporting cycles; (b) batch defect rates exceed 2.5%; "
        "or (c) open RMA replacements remain unresolved beyond 10 business days.",
        styles["ClauseBodyBold"]
    ))
    story.append(Paragraph(
        "5.2 <b>Evaluation Outcome:</b> TechSource Lanka's Q3 performance was reviewed against all three mandatory escalation thresholds:<br/>"
        "• OTIF achieved 94.2% (well above the 90.0% escalation trigger).<br/>"
        "• Defect rate registered at 1.28% (comfortably below the 2.5% single-batch and 1.5% average threshold).<br/>"
        "• RMA turnaround averaged 4.2 days (significantly better than the 10-day escalation ceiling).<br/>"
        "<b>Conclusion:</b> TechSource Lanka is NOT subject to formal Stage 1 or Stage 2 escalation. An informal advisory recommendation was issued requesting "
        "the maintenance of local safety stock at their Colombo 03 warehouse.",
        styles["ClauseBody"]
    ))
    story.append(Spacer(1, 4))
    story.append(create_callout_box(
        styles,
        "Formal escalation is not triggered as all performance metrics remain safely above contractual escalation floors (OTIF > 90%, Defect < 2.5%, RMA < 10 days).",
        "AUDIT FINDING"
    ))
    story.append(Spacer(1, 6))

    # 6.0 Strategic Recommendations for Q4
    story.append(Paragraph("6.0 Strategic Recommendations and Q4 2026 Performance Targets", styles["SectionHeading"]))
    story.append(Paragraph(
        "6.1 <b>Action 1 (Target OTD ≥ 96.0%):</b> TechSource Lanka will reserve dedicated buffer inventory of 50 units for fast-moving SKU TS-WM-01 to absorb year-end fourth-quarter demand surges.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "6.2 <b>Action 2 (Packaging Optimization):</b> Reinforce moisture-resistant outer shrink-wrap on all paper and cardboard packaging during the monsoon logistics period.",
        styles["ClauseBody"]
    ))
    story.append(Paragraph(
        "6.3 <b>Action 3 (Commercial SLA Review):</b> Convene the scheduled bi-annual commercial pricing and contract volume review in November 2026.",
        styles["ClauseBody"]
    ))
    story.append(Spacer(1, 10))

    # Signature Block
    sig_data = [
        [
            Paragraph("<b>Prepared by:</b><br/>Lead Procurement Specialist<br/>SmartSupply Electronics Pvt Ltd", styles["TableCell"]),
            Paragraph("<b>Reviewed & Confirmed:</b><br/>Kamal Silva, Key Account Manager<br/>TechSource Lanka", styles["TableCell"]),
            Paragraph("<b>Approved by:</b><br/>Head of Supply Chain & Logistics<br/>SmartSupply Electronics Pvt Ltd", styles["TableCell"]),
        ]
    ]
    t_sig = Table(sig_data, colWidths=[162, 162, 163])
    t_sig.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(KeepTogether([t_sig]))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Generated: {output_path}")


# =============================================================================
# MAIN ORCHESTRATION FUNCTION
# =============================================================================
def main():
    print("=" * 60)
    print("SMARTSUPPLY ELECTRONICS — DEMO DOCUMENT GENERATION & UPLOAD")
    print("=" * 60)

    # 1. Query seeded suppliers from database
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

        # Ensure an active user exists for authentication
        user = db.execute(select(User).where(User.is_active == True)).scalars().first()
        if not user:
            print("ERROR: No active user found in database for authentication!")
            sys.exit(1)
        auth_token = create_access_token(user_id=user.id)
        print(f"Authenticated as user {user.email} (ID {user.id})")
    finally:
        db.close()

    # 2. Directory for temporary generated PDFs
    output_dir = Path(settings.DOCUMENT_STORAGE_DIR).parent / "demo_generated_pdfs"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nTarget generation directory: {output_dir}")

    # 3. Document specifications
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
            "title": "Supplier Performance Review — Q3 2026",
            "document_type": DocumentType.SUPPLIER_PERFORMANCE_REPORT.value,
            "supplier_id": techsource_id,
            "filename": "supplier_performance_review_q3_2026_techsource.pdf",
            "generator": lambda p: generate_performance_review(p, techsource_id),
        },
    ]

    # Clean up any existing demo documents to ensure clean idempotent run
    print("\n--- Checking for existing demo documents to clean up ---")
    demo_titles = {spec["title"] for spec in doc_specs}
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

    # 4. Generate all 6 PDFs
    print("\n--- Generating PDF files ---")
    generated_files = []
    for spec in doc_specs:
        file_path = output_dir / spec["filename"]
        spec["generator"](str(file_path))
        file_size = os.path.getsize(file_path)
        print(f"  [+] {spec['title']} ({file_size:,} bytes) -> {file_path.name}")
        generated_files.append((spec, file_path))

    # 5. Upload via TestClient API endpoint
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
        print(f"       Type: {doc_json['document_type']}, Supplier ID: {doc_json.get('supplier_id')}")
        print(f"       Filename: {doc_json['original_filename']}, Size: {doc_json['file_size_bytes']:,} bytes")
        print(f"       SHA256: {doc_json['sha256_checksum']}")

    # 6. Verification: GET /api/v1/documents
    print("\n--- Verifying GET /api/v1/documents ---")
    list_response = client.get("/api/v1/documents", headers=headers)
    if list_response.status_code != 200:
        print(f"FAILED to list documents: {list_response.status_code}")
        sys.exit(1)

    all_docs = list_response.json()
    print(f"Total documents returned by API: {len(all_docs)}")
    for d in all_docs:
        sup_name = d["supplier"]["name"] if d.get("supplier") else "None (Company-Wide)"
        print(f"  * ID {d['id']:2d} | {d['document_type']:32s} | Supplier: {sup_name:28s} | {d['title']}")

    # 7. Verification: Verify physical files in configured storage directory
    print("\n--- Verifying Physical Files in Storage Directory ---")
    storage_dir = get_storage_dir()
    print(f"Storage directory: {storage_dir}")
    all_files_exist = True
    
    db_verify = SessionLocal()
    try:
        for d in uploaded_records:
            doc_row = db_verify.get(Document, d["id"])
            if not doc_row:
                print(f"  [FAIL] Document ID {d['id']} missing from DB!")
                all_files_exist = False
                continue
            
            stored_path = Path(storage_dir) / doc_row.storage_key
            exists = stored_path.is_file()
            if exists:
                file_bytes = stored_path.read_bytes()
                has_pdf_magic = file_bytes.startswith(b"%PDF-")
                size_matches = len(file_bytes) == doc_row.file_size_bytes
                sha_matches = hashlib.sha256(file_bytes).hexdigest() == doc_row.sha256_checksum
                print(f"  [OK] ID {doc_row.id:2d} | Storage Key: {doc_row.storage_key}")
                print(f"       File Exists={exists}, Valid %PDF- Magic={has_pdf_magic}, Size Match={size_matches}, Checksum Match={sha_matches}")
            else:
                print(f"  [FAIL] Storage Key {doc_row.storage_key}: MISSING on disk!")
                all_files_exist = False
    finally:
        db_verify.close()

    if not all_files_exist:
        print("ERROR: One or more physical files are missing!")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("ALL 6 DEMO DOCUMENTS SUCCESSFULLY GENERATED, UPLOADED, AND VERIFIED!")
    print("=" * 60)


if __name__ == "__main__":
    main()
