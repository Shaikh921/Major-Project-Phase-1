"""
Generates a comprehensive, illustrated, publication-grade Dashboard Feature Guide PDF.
Embeds real screenshots, architectural diagrams, feature tables, and RAG workflow explanations.
Outputs to: C:\\CLoudProject\\docs\\DASHBOARD_FEATURE_GUIDE.pdf
"""

import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable, Image
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to compute dynamic total page numbers and headers."""
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
        if self._pageNumber == 1:
            return  # Skip cover

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Top Header line
        self.drawString(54, 755, "CLOUDOPS INTEL SRE COMMAND CENTER — COMPREHENSIVE FEATURE GUIDE")
        self.drawRightString(558, 755, "DASHBOARD v3.6.0")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.75)
        self.line(54, 747, 558, 747)

        # Bottom Footer line
        self.line(54, 45, 558, 45)
        self.setFont("Helvetica", 8)
        self.drawString(54, 32, "CloudOps Intel — Operational Architecture & Engineering Reference")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_text)
        self.restoreState()


def create_feature_guide_pdf():
    output_path = r"C:\CLoudProject\docs\DASHBOARD_FEATURE_GUIDE.pdf"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    figures_dir = r"C:\CLoudProject\docs\figures"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Typography styles
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=8,
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#0284c7"),
        spaceAfter=18,
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=9,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=5,
    )

    bullet_style = ParagraphStyle(
        "BulletCustom",
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3,
    )

    caption_style = ParagraphStyle(
        "FigCaption",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#64748b"),
        alignment=1, # Center
        spaceBefore=4,
        spaceAfter=8,
    )

    code_style = ParagraphStyle(
        "CodeCustom",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f1f5f9"),
        borderPadding=5,
        spaceBefore=3,
        spaceAfter=5,
        borderRadius=3,
    )

    story = []

    # ==================== COVER PAGE ====================
    story.append(Spacer(1, 30))
    story.append(Paragraph("CLOUDOPS INTEL SRE PLATFORM", ParagraphStyle("CoverTag", fontName="Helvetica-Bold", fontSize=10, textColor=colors.HexColor("#64748b"), spaceAfter=5)))
    story.append(Paragraph("Command Center Dashboard & Feature Reference Guide", title_style))
    story.append(Paragraph("Complete Technical Documentation of Views, Anomaly Detection Engines, AI Incident Narrator (RAG), and Device Governance", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0284c7"), spaceAfter=18))

    meta_data = [
        [Paragraph("<b>Platform Version:</b>", body_style), Paragraph("v3.6.0 (Unified Enterprise Build)", body_style)],
        [Paragraph("<b>Intelligence Engine:</b>", body_style), Paragraph("RAG Hybrid Retrieval (BM25 + Dense) + Google Gemini LLM", body_style)],
        [Paragraph("<b>Machine Learning:</b>", body_style), Paragraph("Multivariate Isolation Forest & Deep LSTM Reconstruction Autoencoder", body_style)],
        [Paragraph("<b>Security & Transport:</b>", body_style), Paragraph("TLS 1.3 Reverse Proxy, Zero-Trust Device Tokens, Role-Based Access Control", body_style)],
        [Paragraph("<b>Supported Currencies:</b>", body_style), Paragraph("USD, EUR, GBP, JPY, CAD, AUD, INR, CHF (Real-time client conversion)", body_style)],
    ]
    meta_table = Table(meta_data, colWidths=[130, 374])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#e2e8f0")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))

    # Executive Summary Card
    exec_text = (
        "<b>Executive Overview:</b> The CloudOps Intel Command Center is an enterprise SRE observability and incident "
        "intelligence platform designed to correlate multi-domain signals across raw infrastructure telemetry, machine "
        "learning anomaly models, security flow logs, cloud cost catalogs, and collegiate lab computer fleets. "
        "This manual details each view, widget, and background engine powering the unified interface."
    )
    exec_table = Table([[Paragraph(exec_text, body_style)]], colWidths=[504])
    exec_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#e0f2fe")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#38bdf8")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(exec_table)

    story.append(PageBreak())

    # ==================== SECTION 1: GLOBAL NAVIGATION & SHELL ====================
    story.append(Paragraph("1. Global Shell, Navigation & Command Palette", h1_style))
    story.append(Paragraph(
        "The interface is structured around a responsive high-density SRE dark theme. The layout consists of a persistent "
        "collapsible sidebar, an omnibar global search header, and a dynamic workspace view container.",
        body_style
    ))

    # Embedded Screenshot: Sidebar
    sb_img_path = os.path.join(figures_dir, "verified_sidebar_headings.png")
    if os.path.exists(sb_img_path):
        story.append(Image(sb_img_path, width=420, height=85))
        story.append(Paragraph("Figure 1.1 — Persistent Sidebar Navigation with Categorized Operational Modules", caption_style))

    story.append(Paragraph("Navigation Structure & Modules", h2_style))
    story.append(Paragraph("• <b>Operations Category:</b> Overview (cluster health summary), Infrastructure (node inventory), Telemetry Stream (live metric charts), and Lab PCs (physical workstation layouts).", bullet_style))
    story.append(Paragraph("• <b>Detection & Triage Category:</b> Anomaly Center (Isolation Forest & LSTM residuals) and Incidents & Alerts (active priority queue with operator acknowledgment).", bullet_style))
    story.append(Paragraph("• <b>Intelligence Category:</b> Security Events (threat flow logs & firewall blocks), Cloud Cost (multi-cloud rightsizing ROI), and AI Incident Narrator (RAG reasoning engine).", bullet_style))
    story.append(Paragraph("• <b>Governance Category:</b> Device Management (Zero-trust lab enrollment), Administration (RBAC approvals & SMTP relay diagnostic), and Settings.", bullet_style))

    story.append(Spacer(1, 8))

    # Embedded Screenshot: Command Palette
    cp_img_path = os.path.join(figures_dir, "verified_command_palette_open.png")
    if os.path.exists(cp_img_path):
        story.append(Image(cp_img_path, width=420, height=135))
        story.append(Paragraph("Figure 1.2 — Interactive Global Command Palette (Ctrl+K / Cmd+K) with Real-Time Action & View Filtering", caption_style))

    story.append(Paragraph("Global Search & Fast Navigation (Ctrl + K)", h2_style))
    story.append(Paragraph(
        "Pressing <code>Ctrl + K</code> (or clicking the search input in the header) opens the spotlight modal. "
        "Operators can instantly jump between views, search for specific hosts (e.g. <code>prod-web-01</code> or <code>PC-Room1-01</code>), "
        "and trigger quick operational presets without touching the mouse.",
        body_style
    ))

    story.append(PageBreak())

    # ==================== SECTION 2: CORE OBSERVABILITY VIEWS ====================
    story.append(Paragraph("2. Core Observability & Telemetry Views", h1_style))

    story.append(Paragraph("A. Overview View (Cluster Health & Gauges)", h2_style))
    story.append(Paragraph(
        "The primary landing dashboard synthesizes fleet-wide health into immediate visual indicators:",
        body_style
    ))
    story.append(Paragraph("• <b>Fleet Health Gauge:</b> Real-time calculated health percentage based on active threshold breaches.", bullet_style))
    story.append(Paragraph("• <b>Host Status Counters:</b> Total Monitored Hosts, Online vs Offline Nodes, and Environment Distribution.", bullet_style))
    story.append(Paragraph("• <b>Active Alert Summary:</b> Severity badge counters (Critical, Warning, Info) with quick triage shortcuts.", bullet_style))
    story.append(Paragraph("• <b>Cluster Resource Utilization:</b> Real-time aggregate gauges for CPU Utilization (%), Memory Pressure (%), Disk Saturation (%), and Network Throughput (MB/s).", bullet_style))

    story.append(Paragraph("B. Infrastructure / Resources View", h2_style))
    story.append(Paragraph(
        "A comprehensive inventory table detailing every monitored bare-metal server, cloud VM, or laboratory computer:",
        body_style
    ))
    story.append(Paragraph("• <b>Metadata Tracking:</b> Hostname, IP address, Environment (production, staging, lab, development), Cloud Provider (AWS, GCP, Azure, Bare-Metal), and Region.", bullet_style))
    story.append(Paragraph("• <b>Source Type Classification:</b> Badges distinguish between <code>REAL_AGENT</code> (physical lab workstations transmitting live metrics) and <code>SIMULATED</code> cloud instances.", bullet_style))
    story.append(Paragraph("• <b>Filtering & Sorting:</b> Multi-column filtering by environment or connection status.", bullet_style))

    story.append(Paragraph("C. Telemetry Stream View (Live Time-Series)", h2_style))
    story.append(Paragraph(
        "Interactive SVG time-series charts rendering continuous telemetry trends across 1-hour, 6-hour, 24-hour, and 7-day windows. "
        "Operators can isolate metrics, view standard deviations, and inspect historical spikes.",
        body_style
    ))

    story.append(Paragraph("D. Lab PCs View (Physical Computer Fleet)", h2_style))
    story.append(Paragraph(
        "Dedicated collegiate laboratory fleet monitoring designed for physical workstation labs (e.g., Room 101, Bench A):",
        body_style
    ))
    story.append(Paragraph("• <b>Physical Mapping:</b> Displays computer assignment by Lab Name, Room Number, and PC Seat ID.", bullet_style))
    story.append(Paragraph("• <b>Offline Detection:</b> Real-time pulse indicator turns red if a student PC stops polling for > 90 seconds.", bullet_style))
    story.append(Paragraph("• <b>Hardware Telemetry:</b> Core count, RAM capacity, active disk volumes, and network adapter load.", bullet_style))

    story.append(Spacer(1, 10))

    # Core views comparison table
    obs_data = [
        [Paragraph("<b>View Name</b>", body_style), Paragraph("<b>Primary Data Sources</b>", body_style), Paragraph("<b>Key SRE Action / Value</b>", body_style)],
        [Paragraph("<b>Overview</b>", body_style), Paragraph("Metrics, Alerts, Host Heartbeats", body_style), Paragraph("Instant 5-second pulse check of total fleet health.", body_style)],
        [Paragraph("<b>Infrastructure</b>", body_style), Paragraph("Database Host Catalog, Tags", body_style), Paragraph("Inventory management and environment tagging.", body_style)],
        [Paragraph("<b>Telemetry Stream</b>", body_style), Paragraph("Time-series metric storage", body_style), Paragraph("Deep visual correlation of performance spikes.", body_style)],
        [Paragraph("<b>Lab PCs</b>", body_style), Paragraph("Device enrollments, Agent buffer", body_style), Paragraph("Physical lab workstation health & offline tracking.", body_style)],
    ]
    obs_table = Table(obs_data, colWidths=[110, 180, 214])
    obs_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(obs_table)

    story.append(PageBreak())

    # ==================== SECTION 3: AI DETECTION & FORECASTING ====================
    story.append(Paragraph("3. AI Anomaly Detection & Predictive Forecasting", h1_style))
    story.append(Paragraph(
        "CloudOps Intel integrates dual-tier unsupervised machine learning algorithms to detect operational degradation "
        "before static threshold alerts trigger.",
        body_style
    ))

    story.append(Paragraph("A. Anomaly Center (Isolation Forest & LSTM Autoencoder)", h2_style))
    story.append(Paragraph(
        "The Anomaly Center continuously evaluates multi-metric feature vectors across compute instances:",
        body_style
    ))
    story.append(Paragraph("• <b>Multivariate Isolation Forest:</b> Identifies anomalous metric combinations (e.g. moderate CPU combined with unexpected network sent bursts) by calculating recursive tree isolation depths.", bullet_style))
    story.append(Paragraph("• <b>Deep LSTM Autoencoder:</b> Evaluates 30-step temporal sequences. Measures reconstruction error residuals (Mean Squared Error) between expected system behavior and observed telemetry.", bullet_style))
    story.append(Paragraph("• <b>Feature Attribution Ranking:</b> Breaks down exactly which metric contributed most heavily to the anomaly score (e.g., 68% attributed to Disk I/O saturation).", bullet_style))

    story.append(Paragraph("B. Predictive Time-Series Forecasting", h2_style))
    story.append(Paragraph(
        "Linear and polynomial time-series regressors project telemetry trajectories 1 to 24 hours into the future. "
        "The engine computes a <b>Time-to-Threshold Countdown</b> (e.g. <i>'Memory exhaustion projected in 4 hours 18 minutes'</i>) "
        "with 95% confidence bounds, allowing proactive remediation before service outage.",
        body_style
    ))

    story.append(Spacer(1, 10))

    # ==================== SECTION 4: AI INCIDENT NARRATOR (RAG) ====================
    story.append(Paragraph("4. AI Incident Narrator & Grounded RAG Engine", h1_style))
    story.append(Paragraph(
        "The AI Incident Narrator (Module 5) provides natural-language incident explanations and actionable root-cause "
        "analysis. It uses a Retrieval-Augmented Generation (RAG) pipeline strictly grounded in operational runbooks "
        "and real-time telemetry to prevent hallucinations.",
        body_style
    ))

    # Embedded Screenshot: Search Redirect / Narrator View
    nr_img_path = os.path.join(figures_dir, "verified_search_redirect_success.png")
    if os.path.exists(nr_img_path):
        story.append(Image(nr_img_path, width=420, height=135))
        story.append(Paragraph("Figure 4.1 — AI Incident Narrator with Grounded Incident Explanation and Evidence Citations", caption_style))

    story.append(Paragraph("The 5-Stage RAG Pipeline Architecture", h2_style))
    rag_steps = [
        [Paragraph("<b>Stage</b>", body_style), Paragraph("<b>Mechanism & Optimization</b>", body_style)],
        [Paragraph("<b>1. Semantic Chunking</b>", body_style), Paragraph("Parses SRE markdown runbooks into structured 400-word blocks with section headers (Symptoms, Root Causes, Diagnostic Commands).", body_style)],
        [Paragraph("<b>2. 768-Dim Dense Embeddings</b>", body_style), Paragraph("Generates normalized semantic vectors using Google Gemini (<code>gemini-embedding-001</code>) with in-memory LRU query caching (&lt; 1ms).", body_style)],
        [Paragraph("<b>3. Hybrid BM25 Retrieval</b>", body_style), Paragraph("Executes Reciprocal Rank Fusion combining dense semantic cosine similarity with Okapi BM25 sparse keyword matching.", body_style)],
        [Paragraph("<b>4. Telemetry Augmentation</b>", body_style), Paragraph("Injects active cluster alerts, host hardware profiles, and security logs into the system prompt with deduplicated chunk tracking.", body_style)],
        [Paragraph("<b>5. Grounded Generation</b>", body_style), Paragraph("Google Gemini Flash synthesizes: <b>Executive Observation</b>, <b>Grounded Evidence</b>, <b>Inferred Root Cause</b>, and numbered <b>Actionable Remediation</b> commands.", body_style)],
    ]
    rag_table = Table(rag_steps, colWidths=[140, 364])
    rag_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(rag_table)

    story.append(PageBreak())

    # ==================== SECTION 5: OPERATIONAL & GOVERNANCE ====================
    story.append(Paragraph("5. Operational Management & Enterprise Governance", h1_style))

    story.append(Paragraph("A. Incidents & Alerts Management", h2_style))
    story.append(Paragraph(
        "A centralized triage board for threshold violations. Features rule-based deduplication, visual severity tags "
        "(Critical, Warning, Info), one-click operator acknowledgment, and feedback categorization (True Positive / False Positive).",
        body_style
    ))

    story.append(Paragraph("B. Cloud Cost Intelligence (Multi-Currency)", h2_style))
    story.append(Paragraph(
        "Tracks compute and storage expenditures with base USD accounting and real-time client conversion to 8 global currencies "
        "(USD, EUR, GBP, JPY, CAD, AUD, INR, CHF). Automatically identifies idle staging instances and generates rightsizing "
        "recommendations with projected monthly ROI.",
        body_style
    ))

    story.append(Paragraph("C. Security Events & Flow Auditing", h2_style))
    story.append(Paragraph(
        "Aggregates network perimeter flow events, unusual SSH/RDP connection frequency, failed authentication spikes, "
        "and automated firewall drop actions into an immutable chronological audit trail.",
        body_style
    ))

    story.append(Paragraph("D. Zero-Trust Device Management", h2_style))
    story.append(Paragraph(
        "Coordinates physical laboratory workstation onboarding. Super Administrators generate one-time cryptographically "
        "random enrollment codes (<code>ec_...</code>). When a client workstation installer runs, it requests enrollment. "
        "The computer enters the <b>Pending Approval</b> queue, where the administrator verifies the reported MAC address, "
        "assigns Lab/Room/Seat metadata, and issues an HMAC SHA-256 ingestion credential.",
        body_style
    ))

    story.append(Paragraph("E. Enterprise RBAC & User Administration", h2_style))
    story.append(Paragraph(
        "A 4-tier hierarchical access control model governing sensitive operational actions:",
        body_style
    ))
    story.append(Paragraph("• <b>SUPER_ADMIN:</b> Full platform control, device approval, role promotions, and live SMTP relay diagnostic tools.", bullet_style))
    story.append(Paragraph("• <b>ADMIN:</b> Metric rule configurations, incident management, and user provisioning.", bullet_style))
    story.append(Paragraph("• <b>OPERATOR:</b> Alert acknowledgment, telemetry inspection, and feedback tagging.", bullet_style))
    story.append(Paragraph("• <b>VIEWER:</b> Read-only access to dashboards and status streams.", bullet_style))

    story.append(Spacer(1, 12))

    # Summary Feature Matrix Table
    story.append(Paragraph("Master Feature Matrix & Module Map", h2_style))
    matrix_data = [
        [Paragraph("<b>Dashboard View</b>", body_style), Paragraph("<b>Route / ID</b>", body_style), Paragraph("<b>Minimum Role</b>", body_style), Paragraph("<b>Key Capability</b>", body_style)],
        [Paragraph("Overview", body_style), Paragraph("<code>#overview</code>", body_style), Paragraph("VIEWER", body_style), Paragraph("Cluster health score, gauges, alert badges.", body_style)],
        [Paragraph("Infrastructure", body_style), Paragraph("<code>#resources</code>", body_style), Paragraph("VIEWER", body_style), Paragraph("Full host inventory & cloud provider metadata.", body_style)],
        [Paragraph("Telemetry Stream", body_style), Paragraph("<code>#metrics</code>", body_style), Paragraph("VIEWER", body_style), Paragraph("Live SVG time-series metric graphs.", body_style)],
        [Paragraph("Lab PCs", body_style), Paragraph("<code>#lab</code>", body_style), Paragraph("OPERATOR", body_style), Paragraph("Physical lab workstation grid & offline tracking.", body_style)],
        [Paragraph("Anomaly Center", body_style), Paragraph("<code>#anomalies</code>", body_style), Paragraph("OPERATOR", body_style), Paragraph("Isolation Forest & LSTM Autoencoder residuals.", body_style)],
        [Paragraph("Incidents & Alerts", body_style), Paragraph("<code>#incidents</code>", body_style), Paragraph("OPERATOR", body_style), Paragraph("Threshold incident triage & acknowledgment.", body_style)],
        [Paragraph("Security Events", body_style), Paragraph("<code>#security</code>", body_style), Paragraph("OPERATOR", body_style), Paragraph("Network flow logs & threat audit trail.", body_style)],
        [Paragraph("Cloud Cost", body_style), Paragraph("<code>#cost</code>", body_style), Paragraph("ADMIN", body_style), Paragraph("Multi-currency spend & idle rightsizing ROI.", body_style)],
        [Paragraph("AI Narrator (RAG)", body_style), Paragraph("<code>#narrator</code>", body_style), Paragraph("OPERATOR", body_style), Paragraph("Gemini LLM grounded runbook reasoning.", body_style)],
        [Paragraph("Device Management", body_style), Paragraph("<code>#devices</code>", body_style), Paragraph("SUPER_ADMIN", body_style), Paragraph("Enrollment token creation & device approvals.", body_style)],
        [Paragraph("Admin Management", body_style), Paragraph("<code>#admin</code>", body_style), Paragraph("SUPER_ADMIN", body_style), Paragraph("User approval workflows & SMTP diagnostics.", body_style)],
        [Paragraph("System Settings", body_style), Paragraph("<code>#settings</code>", body_style), Paragraph("ADMIN", body_style), Paragraph("Alerting thresholds & currency selection.", body_style)],
    ]
    matrix_table = Table(matrix_data, colWidths=[95, 80, 80, 249])
    matrix_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(matrix_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[+] Dashboard Feature Guide PDF generated successfully: {output_path}")

if __name__ == "__main__":
    create_feature_guide_pdf()
