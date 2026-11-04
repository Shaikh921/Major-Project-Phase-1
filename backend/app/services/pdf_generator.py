"""
PDF Generator Service for CloudOps Intel.
Provides high-fidelity, publication-grade A4 PDF documents for:
1. Overall Infrastructure Monitoring Report (Multi-page, Fleet Analytics)
2. Individual Sensor / PC Performance Report (Dedicated Single-Host Deep Dive)
"""

import io
import os
import tempfile
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Enforce headless matplotlib configuration before importing pyplot
os.environ.setdefault("MPLCONFIGDIR", tempfile.gettempdir())
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable, Image
)
from reportlab.pdfgen import canvas

PRINT_WIDTH = 523.0  # Printable width on A4 with 36pt margins


# ==============================================================================
# NUMBERED CANVAS (TWO-PASS RUNNING HEADERS & FOOTERS)
# ==============================================================================

class OverallNumberedCanvas(canvas.Canvas):
    """Two-pass canvas for Overall Infrastructure Report."""
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
            return  # Skip decorations on cover page

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))

        # Top Header line
        self.drawString(36, 808, "CLOUDOPS INTEL — OVERALL INFRASTRUCTURE MONITORING REPORT")
        self.setFont("Helvetica", 8)
        self.drawRightString(559, 808, "FLEET SRE AUDIT | ENTERPRISE PLATFORM")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.75)
        self.line(36, 800, 559, 800)

        # Bottom Footer line
        self.line(36, 40, 559, 40)
        self.setFont("Helvetica", 7.5)
        self.drawString(36, 28, "Confidential — Enterprise SRE Operations & Infrastructure Auditing")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(559, 28, page_text)
        self.restoreState()


class HostNumberedCanvas(canvas.Canvas):
    """Two-pass canvas for Individual Sensor / PC Performance Report."""
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
            return

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#475569"))

        # Top Header line
        self.drawString(36, 808, "CLOUDOPS INTEL — INDIVIDUAL SENSOR PERFORMANCE REPORT")
        self.setFont("Helvetica", 8)
        self.drawRightString(559, 808, "WORKSTATION AUDIT & HARDWARE TELEMETRY")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.75)
        self.line(36, 800, 559, 800)

        # Bottom Footer line
        self.line(36, 40, 559, 40)
        self.setFont("Helvetica", 7.5)
        self.drawString(36, 28, "Confidential — Dedicated Sensor Diagnostics & Telemetry Review")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(559, 28, page_text)
        self.restoreState()


# ==============================================================================
# STYLES SETUP
# ==============================================================================

def get_report_styles():
    base_styles = getSampleStyleSheet()

    custom_styles = {
        "CoverOver": ParagraphStyle(
            "CoverOver",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#64748b"),
            spaceAfter=4,
        ),
        "CoverTitle": ParagraphStyle(
            "CoverTitle",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            textColor=colors.HexColor("#0f172a"),
            spaceAfter=6,
        ),
        "CoverSubtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#0284c7"),
            spaceAfter=14,
        ),
        "SectionH1": ParagraphStyle(
            "SectionH1",
            parent=base_styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=12,
            spaceAfter=5,
            keepWithNext=True,
        ),
        "SectionH2": ParagraphStyle(
            "SectionH2",
            parent=base_styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#1e3a8a"),
            spaceBefore=8,
            spaceAfter=3,
            keepWithNext=True,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#334155"),
            spaceAfter=4,
        ),
        "BodyBold": ParagraphStyle(
            "BodyBold",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#0f172a"),
        ),
        "Bullet": ParagraphStyle(
            "Bullet",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#334155"),
            leftIndent=12,
            firstLineIndent=-8,
            spaceAfter=2,
        ),
        "CodeText": ParagraphStyle(
            "CodeText",
            parent=base_styles["Normal"],
            fontName="Courier",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#0f172a"),
        ),
        "TableHeader": ParagraphStyle(
            "TableHeader",
            parent=base_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=10,
            textColor=colors.white,
        ),
        "TableCell": ParagraphStyle(
            "TableCell",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#1e293b"),
        ),
        "TableCellMono": ParagraphStyle(
            "TableCellMono",
            parent=base_styles["Normal"],
            fontName="Courier",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#0f172a"),
        ),
        "Callout": ParagraphStyle(
            "Callout",
            parent=base_styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11.5,
            textColor=colors.HexColor("#1e293b"),
        ),
    }

    return custom_styles


# ==============================================================================
# MATPLOTLIB CHART HELPERS
# ==============================================================================

def create_overall_telemetry_chart(timeline_data: List[Dict[str, Any]]) -> Optional[io.BytesIO]:
    """
    Renders multi-metric fleet average utilization over time.
    Expects timeline_data = [{'timestamp': dt, 'avg_cpu': float, 'avg_ram': float, 'avg_disk': float}]
    """
    if not timeline_data or len(timeline_data) < 2:
        return None

    try:
        timestamps = [d["timestamp"] for d in timeline_data]
        cpus = [d.get("avg_cpu", 0.0) for d in timeline_data]
        rams = [d.get("avg_ram", 0.0) for d in timeline_data]
        disks = [d.get("avg_disk", 0.0) for d in timeline_data]

        fig, ax = plt.subplots(figsize=(7.2, 2.4), dpi=150)
        ax.plot(timestamps, cpus, label="Avg CPU (%)", color="#0284c7", linewidth=1.5)
        ax.plot(timestamps, rams, label="Avg RAM (%)", color="#8b5cf6", linewidth=1.5)
        ax.plot(timestamps, disks, label="Avg Disk (%)", color="#10b981", linewidth=1.2, linestyle="--")

        ax.axhline(80.0, color="#f59e0b", linestyle=":", linewidth=0.9, label="Warning (80%)")
        ax.axhline(95.0, color="#ef4444", linestyle=":", linewidth=0.9, label="Critical (95%)")

        ax.set_ylim(0, 105)
        ax.set_ylabel("Utilization (%)", fontsize=8, color="#334155")
        ax.grid(True, linestyle="--", alpha=0.3, color="#94a3b8")
        ax.legend(loc="upper right", fontsize=7, framealpha=0.85)

        # Format X-axis with time
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        fig.autofmt_xdate(rotation=20, ha="right")
        ax.tick_params(axis="both", labelsize=7, colors="#475569")

        plt.title("Fleet Resource Utilization Timeline", fontsize=9, fontweight="bold", color="#0f172a", pad=6)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception:
        plt.close("all")
        return None


def create_host_timeseries_chart(
    timestamps: List[datetime],
    values: List[float],
    title: str,
    ylabel: str,
    color: str,
    warn_thresh: Optional[float] = None,
    crit_thresh: Optional[float] = None,
    max_val: Optional[float] = None,
) -> Optional[io.BytesIO]:
    """Generates a clean single-metric time-series chart for an individual host."""
    if not timestamps or len(timestamps) < 2 or len(values) != len(timestamps):
        return None

    try:
        fig, ax = plt.subplots(figsize=(7.2, 2.0), dpi=150)
        ax.plot(timestamps, values, color=color, linewidth=1.5, label=title)
        ax.fill_between(timestamps, values, alpha=0.12, color=color)

        if warn_thresh is not None:
            ax.axhline(warn_thresh, color="#f59e0b", linestyle=":", linewidth=0.9, label=f"Warning ({warn_thresh})")
        if crit_thresh is not None:
            ax.axhline(crit_thresh, color="#ef4444", linestyle=":", linewidth=0.9, label=f"Critical ({crit_thresh})")

        if max_val:
            ax.set_ylim(0, max_val)
        else:
            top_bound = max(values) * 1.15 if values and max(values) > 0 else 10
            ax.set_ylim(0, top_bound)

        ax.set_ylabel(ylabel, fontsize=7.5, color="#334155")
        ax.grid(True, linestyle="--", alpha=0.3, color="#94a3b8")
        ax.legend(loc="upper right", fontsize=6.5, framealpha=0.85)

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        fig.autofmt_xdate(rotation=15, ha="right")
        ax.tick_params(axis="both", labelsize=7, colors="#475569")

        plt.title(title, fontsize=8.5, fontweight="bold", color="#0f172a", pad=4)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception:
        plt.close("all")
        return None


def create_host_network_chart(
    timestamps: List[datetime],
    sent_mb: List[float],
    recv_mb: List[float],
) -> Optional[io.BytesIO]:
    """Generates dual-line network activity chart (sent vs received)."""
    if not timestamps or len(timestamps) < 2:
        return None

    try:
        fig, ax = plt.subplots(figsize=(7.2, 2.0), dpi=150)
        ax.plot(timestamps, sent_mb, color="#0284c7", linewidth=1.3, label="Network Out (MB)")
        ax.plot(timestamps, recv_mb, color="#10b981", linewidth=1.3, label="Network In (MB)")

        ax.set_ylabel("Traffic (MB)", fontsize=7.5, color="#334155")
        ax.grid(True, linestyle="--", alpha=0.3, color="#94a3b8")
        ax.legend(loc="upper right", fontsize=6.5, framealpha=0.85)

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        fig.autofmt_xdate(rotation=15, ha="right")
        ax.tick_params(axis="both", labelsize=7, colors="#475569")

        plt.title("Workstation Network Bandwidth Activity", fontsize=8.5, fontweight="bold", color="#0f172a", pad=4)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception:
        plt.close("all")
        return None


# ==============================================================================
# REPORT 1: OVERALL SYSTEM REPORT PDF BUILDER
# ==============================================================================

def build_overall_system_pdf(
    report_data: Dict[str, Any],
    timeline_samples: List[Dict[str, Any]],
    requester_email: str = "Authorized Operator",
) -> bytes:
    """
    Builds the full multi-page Overall Infrastructure Monitoring Report.
    Returns bytes of the compiled PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=40,
        bottomMargin=42,
    )

    styles = get_report_styles()
    story = []

    # ------------------ COVER PAGE / METADATA ------------------
    story.append(Spacer(1, 25))
    story.append(Paragraph("CLOUDOPS INTEL SRE PLATFORM &bull; ENTERPRISE OBSERVABILITY", styles["CoverOver"]))
    story.append(Paragraph("Overall Infrastructure Monitoring Report", styles["CoverTitle"]))
    story.append(Paragraph(
        "Consolidated Fleet Telemetry, Incident Triage, Security Posture, and Capacity Analysis",
        styles["CoverSubtitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0284c7"), spaceAfter=14))

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    start_str = str(report_data.get("time_window_start", "")).replace("T", " ")[:19] + " UTC"
    end_str = str(report_data.get("time_window_end", "")).replace("T", " ")[:19] + " UTC"

    meta_rows = [
        [Paragraph("<b>Report Identifier:</b>", styles["Body"]), Paragraph(f"<code>{report_data.get('report_id', 'RPT-N/A')}</code>", styles["CodeText"])],
        [Paragraph("<b>Generated Timestamp:</b>", styles["Body"]), Paragraph(now_str, styles["Body"])],
        [Paragraph("<b>Reporting Window:</b>", styles["Body"]), Paragraph(f"{start_str} &rarr; {end_str}", styles["Body"])],
        [Paragraph("<b>Environment Scope:</b>", styles["Body"]), Paragraph(str(report_data.get("environment", "All Environments")), styles["Body"])],
        [Paragraph("<b>Monitored Fleet Size:</b>", styles["Body"]), Paragraph(f"{report_data.get('summary_metrics', {}).get('total_hosts', 0)} Enrolled Hosts / Workstations", styles["Body"])],
        [Paragraph("<b>Requested By:</b>", styles["Body"]), Paragraph(requester_email, styles["Body"])],
        [Paragraph("<b>Heartbeat Threshold:</b>", styles["Body"]), Paragraph(f"{report_data.get('summary_metrics', {}).get('offline_threshold_seconds', 90)} seconds cutoff", styles["Body"])],
        [Paragraph("<b>Security Classification:</b>", styles["Body"]), Paragraph("CONFIDENTIAL — Enterprise SRE Operations & System Audit", styles["BodyBold"])],
    ]
    meta_table = Table(meta_rows, colWidths=[130, 393])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4.5),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # Executive Overview Notice Box
    exec_text = (
        f"<b>Executive Summary Notice:</b> This audit report reflects monitored compute assets and physical sensor nodes "
        f"within the <b>{report_data.get('environment', 'All Environments')}</b> scope. Connectivity liveness is evaluated "
        f"against high-frequency telemetry samples using an active threshold of <b>{report_data.get('summary_metrics', {}).get('offline_threshold_seconds', 90)} seconds</b>. "
        f"Missing metric measurements are explicitly distinguished from zero resource utilization."
    )
    exec_table = Table([[Paragraph(exec_text, styles["Callout"])]], colWidths=[PRINT_WIDTH])
    exec_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#e0f2fe")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#38bdf8")),
        ('PADDING', (0,0), (-1,-1), 6.5),
    ]))
    story.append(exec_table)

    story.append(PageBreak())

    # ------------------ SECTION 2: EXECUTIVE SUMMARY & KPIS ------------------
    story.append(Paragraph("2. Executive Summary & Fleet Health Metrics", styles["SectionH1"]))

    sm = report_data.get("summary_metrics", {})
    total_hosts = sm.get("total_hosts", 0)
    online_hosts = report_data.get("online_hosts_count", sm.get("online_hosts", 0))
    offline_hosts = report_data.get("offline_hosts_count", sm.get("offline_hosts", 0))
    unseen_hosts = report_data.get("unseen_hosts_count", sm.get("unseen_hosts", 0))

    crit_alerts = sm.get("critical_alerts", 0)
    warn_alerts = sm.get("warning_alerts", 0)
    sec_events = report_data.get("security_events_count", 0)

    avg_cpu = report_data.get("avg_cpu_percent")
    avg_mem = report_data.get("avg_memory_percent")
    avg_disk = report_data.get("avg_disk_percent")

    kpi_rows = [
        [
            Paragraph("<b>Total Registered Hosts:</b>", styles["TableCell"]), Paragraph(str(total_hosts), styles["TableCellMono"]),
            Paragraph("<b>Online Hosts:</b>", styles["TableCell"]), Paragraph(f"<font color='#059669'><b>{online_hosts}</b></font>", styles["TableCell"]),
        ],
        [
            Paragraph("<b>Offline Hosts:</b>", styles["TableCell"]), Paragraph(f"<font color='#dc2626'><b>{offline_hosts}</b></font>", styles["TableCell"]),
            Paragraph("<b>Missing Telemetry:</b>", styles["TableCell"]), Paragraph(f"<font color='#64748b'><b>{unseen_hosts}</b></font>", styles["TableCell"]),
        ],
        [
            Paragraph("<b>Critical Alerts:</b>", styles["TableCell"]), Paragraph(f"<font color='#dc2626'><b>{crit_alerts}</b></font>", styles["TableCell"]),
            Paragraph("<b>Warning Alerts:</b>", styles["TableCell"]), Paragraph(f"<font color='#d97706'><b>{warn_alerts}</b></font>", styles["TableCell"]),
        ],
        [
            Paragraph("<b>Security Events:</b>", styles["TableCell"]), Paragraph(f"<b>{sec_events}</b>", styles["TableCellMono"]),
            Paragraph("<b>Avg Fleet CPU:</b>", styles["TableCell"]), Paragraph(f"{avg_cpu}%" if avg_cpu is not None else "—", styles["TableCellMono"]),
        ],
        [
            Paragraph("<b>Avg Fleet Memory:</b>", styles["TableCell"]), Paragraph(f"{avg_mem}%" if avg_mem is not None else "—", styles["TableCellMono"]),
            Paragraph("<b>Avg Fleet Disk:</b>", styles["TableCell"]), Paragraph(f"{avg_disk}%" if avg_disk is not None else "—", styles["TableCellMono"]),
        ],
    ]
    kpi_table = Table(kpi_rows, colWidths=[140, 121, 140, 122])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 8))

    # Health assessment statement
    fleet_sec = next((s for s in report_data.get("sections", []) if s.get("section_title") == "Fleet Overview & Health"), None)
    assessment_detail = fleet_sec.get("details", "") if fleet_sec else "Fleet status is operating within monitored parameters."
    story.append(Paragraph(f"<b>System Health Assessment:</b> {assessment_detail}", styles["Body"]))
    story.append(Spacer(1, 10))

    # ------------------ SECTION 3: FLEET INVENTORY & CONNECTIVITY ------------------
    story.append(Paragraph("3. Fleet Inventory & Workstation Connectivity", styles["SectionH1"]))

    inv_list = report_data.get("host_inventories", [])
    inv_header = [
        Paragraph("<b>Hostname</b>", styles["TableHeader"]),
        Paragraph("<b>ID</b>", styles["TableHeader"]),
        Paragraph("<b>IP Address</b>", styles["TableHeader"]),
        Paragraph("<b>Env</b>", styles["TableHeader"]),
        Paragraph("<b>Room/Loc</b>", styles["TableHeader"]),
        Paragraph("<b>Status</b>", styles["TableHeader"]),
        Paragraph("<b>Last Heartbeat</b>", styles["TableHeader"]),
        Paragraph("<b>CPU</b>", styles["TableHeader"]),
        Paragraph("<b>RAM</b>", styles["TableHeader"]),
        Paragraph("<b>Disk</b>", styles["TableHeader"]),
    ]
    inv_rows = [inv_header]

    for h in inv_list:
        st = h.get("status", "NO_DATA")
        if st == "ONLINE":
            st_cell = "<font color='#059669'><b>ONLINE</b></font>"
        elif st == "OFFLINE":
            st_cell = "<font color='#dc2626'><b>OFFLINE</b></font>"
        else:
            st_cell = "<font color='#64748b'><b>NO DATA</b></font>"

        ls = h.get("last_seen")
        ls_str = str(ls).replace("T", " ")[:19] if ls else "—"

        cpu_str = f"{h.get('cpu_percent')}%" if h.get("cpu_percent") is not None else "—"
        ram_str = f"{h.get('memory_percent')}%" if h.get("memory_percent") is not None else "—"
        disk_str = f"{h.get('disk_percent')}%" if h.get("disk_percent") is not None else "—"

        inv_rows.append([
            Paragraph(str(h.get("hostname", "—")), styles["TableCellBold" if "TableCellBold" in styles else "TableCell"]),
            Paragraph(str(h.get("host_id", "—")), styles["TableCellMono"]),
            Paragraph(str(h.get("ip_address", "—")), styles["TableCellMono"]),
            Paragraph(str(h.get("environment", "—")), styles["TableCell"]),
            Paragraph(str(h.get("room", "—")), styles["TableCell"]),
            Paragraph(st_cell, styles["TableCell"]),
            Paragraph(ls_str, styles["TableCellMono"]),
            Paragraph(cpu_str, styles["TableCellMono"]),
            Paragraph(ram_str, styles["TableCellMono"]),
            Paragraph(disk_str, styles["TableCellMono"]),
        ])

    if len(inv_rows) == 1:
        inv_rows.append([Paragraph("No monitored hosts found in this scope.", styles["TableCell"])] + [Paragraph("—", styles["TableCell"])] * 9)

    # 523 printable width distributed
    inv_table = Table(inv_rows, colWidths=[80, 24, 75, 45, 55, 48, 86, 36, 36, 38], repeatRows=1)
    inv_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('PADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(inv_table)

    story.append(PageBreak())

    # ------------------ SECTION 4: PERFORMANCE ANALYSIS & CHARTS ------------------
    story.append(Paragraph("4. Infrastructure Performance & Historical Telemetry", styles["SectionH1"]))
    story.append(Paragraph(
        "Historical telemetry trends aggregated across active sensors. Evaluates CPU, memory, and storage utilization over the requested horizon.",
        styles["Body"]
    ))

    chart_buf = create_overall_telemetry_chart(timeline_samples)
    if chart_buf:
        story.append(Spacer(1, 4))
        story.append(Image(chart_buf, width=PRINT_WIDTH, height=172))
        story.append(Spacer(1, 8))
    else:
        no_chart_text = "<i>Historical time-series chart requires at least two telemetry samples across the requested reporting horizon.</i>"
        story.append(Paragraph(no_chart_text, styles["Body"]))
        story.append(Spacer(1, 6))

    # ------------------ SECTION 5: ALERT & INCIDENT ANALYSIS ------------------
    story.append(Paragraph("5. Alert and Incident Analysis", styles["SectionH1"]))

    recent_alerts = report_data.get("recent_alerts", [])
    alert_header = [
        Paragraph("<b>Timestamp</b>", styles["TableHeader"]),
        Paragraph("<b>Host</b>", styles["TableHeader"]),
        Paragraph("<b>Severity</b>", styles["TableHeader"]),
        Paragraph("<b>Category</b>", styles["TableHeader"]),
        Paragraph("<b>Metric</b>", styles["TableHeader"]),
        Paragraph("<b>Message / Reason</b>", styles["TableHeader"]),
        Paragraph("<b>Status</b>", styles["TableHeader"]),
    ]
    alert_rows = [alert_header]

    for a in recent_alerts[:15]:  # show up to 15 recent alerts
        sev = a.get("severity", "info").lower()
        if sev == "critical":
            sev_cell = "<font color='#dc2626'><b>CRITICAL</b></font>"
        elif sev == "warning":
            sev_cell = "<font color='#d97706'><b>WARNING</b></font>"
        else:
            sev_cell = "<font color='#0284c7'><b>INFO</b></font>"

        ts_str = str(a.get("created_at", "")).replace("T", " ")[:19]
        alert_rows.append([
            Paragraph(ts_str, styles["TableCellMono"]),
            Paragraph(str(a.get("hostname", "—")), styles["TableCell"]),
            Paragraph(sev_cell, styles["TableCell"]),
            Paragraph(str(a.get("kind", "—")), styles["TableCell"]),
            Paragraph(str(a.get("metric", "—")), styles["TableCellMono"]),
            Paragraph(str(a.get("message", "—")), styles["TableCell"]),
            Paragraph(str(a.get("status", "—")).upper(), styles["TableCellMono"]),
        ])

    if len(alert_rows) == 1:
        alert_rows.append([Paragraph("Zero active or triggered alerts recorded within the reporting timeframe.", styles["TableCell"])] + [Paragraph("—", styles["TableCell"])] * 6)

    alert_table = Table(alert_rows, colWidths=[80, 75, 48, 55, 60, 150, 55], repeatRows=1)
    alert_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('PADDING', (0,0), (-1,-1), 3),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(alert_table)
    story.append(Spacer(1, 10))

    # ------------------ SECTION 6: SECURITY MONITORING ------------------
    story.append(Paragraph("6. Security Monitoring & Threat Observations", styles["SectionH1"]))

    sec_sec = next((s for s in report_data.get("sections", []) if s.get("section_title") == "Security & Threat Observations"), None)
    sec_details = sec_sec.get("details", "") if sec_sec else "No threat signatures detected."
    story.append(Paragraph(f"<b>Security Posture Findings:</b> {sec_details}", styles["Body"]))

    recent_sec = report_data.get("recent_security_events", [])
    if recent_sec:
        sec_rows = [
            [
                Paragraph("<b>Timestamp</b>", styles["TableHeader"]),
                Paragraph("<b>Event Type</b>", styles["TableHeader"]),
                Paragraph("<b>Severity</b>", styles["TableHeader"]),
                Paragraph("<b>Host</b>", styles["TableHeader"]),
                Paragraph("<b>Source IP</b>", styles["TableHeader"]),
                Paragraph("<b>Description</b>", styles["TableHeader"]),
            ]
        ]
        for se in recent_sec[:10]:
            ts_str = str(se.get("timestamp", "")).replace("T", " ")[:19]
            sec_rows.append([
                Paragraph(ts_str, styles["TableCellMono"]),
                Paragraph(str(se.get("event_type", "—")), styles["TableCellMono"]),
                Paragraph(str(se.get("severity", "—")).upper(), styles["TableCell"]),
                Paragraph(str(se.get("hostname", "—")), styles["TableCell"]),
                Paragraph(str(se.get("source_ip", "—")), styles["TableCellMono"]),
                Paragraph(str(se.get("description", "—")), styles["TableCell"]),
            ])
        sec_table = Table(sec_rows, colWidths=[80, 85, 48, 70, 75, 165], repeatRows=1)
        sec_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
            ('PADDING', (0,0), (-1,-1), 3),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(sec_table)
    else:
        story.append(Paragraph("<i>No suspicious network intrusions or unauthorized authentication attempts logged.</i>", styles["Body"]))

    story.append(Spacer(1, 6))

    # Security Disclaimer Box (Mandatory requirement)
    disclaimer_text = f"<b>Security Audit Qualification:</b> {report_data.get('security_audit_disclaimer', '')}"
    sec_box = Table([[Paragraph(disclaimer_text, styles["Callout"])]], colWidths=[PRINT_WIDTH])
    sec_box.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#fffbeb")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#f59e0b")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(sec_box)

    story.append(PageBreak())

    # ------------------ SECTION 7: COST & OPTIMIZATION ANALYSIS ------------------
    story.append(Paragraph("7. Cost & Infrastructure Optimization Analysis", styles["SectionH1"]))
    spend = report_data.get("estimated_monthly_spend_usd", 0.0)
    savings = report_data.get("potential_savings_usd", 0.0)

    cost_rows = [
        [Paragraph("<b>Estimated Monthly Fleet Spend:</b>", styles["TableCell"]), Paragraph(f"<b>${spend:.2f} USD</b>", styles["TableCellMono"])],
        [Paragraph("<b>Identified Optimization Savings:</b>", styles["TableCell"]), Paragraph(f"<font color='#059669'><b>${savings:.2f} USD / month</b></font>", styles["TableCellMono"])],
    ]
    cost_table = Table(cost_rows, colWidths=[200, 323])
    cost_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(cost_table)
    story.append(Spacer(1, 6))

    cost_sec = next((s for s in report_data.get("sections", []) if s.get("section_title") == "Cost Efficiency & Optimization"), None)
    if cost_sec:
        story.append(Paragraph(f"<b>Resource Optimization Findings:</b> {cost_sec.get('details', '')}", styles["Body"]))
    story.append(Spacer(1, 10))

    # ------------------ SECTION 8: SYSTEM HEALTH & RECOMMENDATIONS ------------------
    story.append(Paragraph("8. Operational Health Findings & Recommendations", styles["SectionH1"]))
    recommendations = report_data.get("recommendations", [])
    if not recommendations:
        # Generate default evidence-based recommendations
        if offline_hosts > 0:
            recommendations.append(f"Investigate {offline_hosts} workstation(s) that have stopped emitting heartbeats beyond the cutoff threshold.")
        if crit_alerts > 0:
            recommendations.append(f"Triage {crit_alerts} critical alert(s) across affected hosts to prevent node instability.")
        if unseen_hosts > 0:
            recommendations.append(f"Deploy sensor agent to {unseen_hosts} enrolled host(s) currently exhibiting zero recorded telemetry.")
        if not recommendations:
            recommendations.append("All monitored systems are operating within configured performance boundaries. Maintain active polling schedule.")

    for rec in recommendations:
        story.append(Paragraph(f"• {rec}", styles["Bullet"]))

    story.append(Spacer(1, 12))

    # ------------------ SECTION 9: TECHNICAL NOTES & METHODOLOGY ------------------
    story.append(Paragraph("9. Technical Notes & Data Integrity Methodology", styles["SectionH1"]))
    methodology_text = (
        "<b>Data Freshness & Integrity:</b><br/>"
        f"• <b>Heartbeat Threshold:</b> Workstation online/offline state is calculated using an active threshold of <b>{report_data.get('summary_metrics', {}).get('offline_threshold_seconds', 90)} seconds</b>. Telemetry gaps exceeding this window transition the node to <i>OFFLINE</i>.<br/>"
        "• <b>Missing Telemetry Treatment:</b> Cells showing '—' indicate unrecorded or missing sensor data. Missing readings are strictly isolated from arithmetic aggregations and are never treated as zero utilization.<br/>"
        "• <b>Metric Aggregations:</b> Averages, maximums, and percentiles are computed across verified valid telemetry samples ingested into the persistent database.<br/>"
        "• <b>Timezone Baseline:</b> All timestamps in this document are expressed in UTC unless explicitly designated otherwise."
    )
    method_table = Table([[Paragraph(methodology_text, styles["Callout"])]], colWidths=[PRINT_WIDTH])
    method_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94a3b8")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(method_table)

    doc.build(story, canvasmaker=OverallNumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()


# ==============================================================================
# REPORT 2: INDIVIDUAL SENSOR / PC REPORT BUILDER
# ==============================================================================

def build_individual_host_pdf(
    host_data: Dict[str, Any],
    metric_samples: List[Dict[str, Any]],
    requester_email: str = "Authorized Operator",
) -> bytes:
    """
    Builds the dedicated Individual Sensor / PC Performance Report PDF.
    Contains strictly the selected host's data.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=40,
        bottomMargin=42,
    )

    styles = get_report_styles()
    story = []

    hi = host_data.get("host_identity", {})
    hostname = hi.get("hostname", "Unknown Host")
    host_id = hi.get("host_id", 0)

    # ------------------ COVER HEADER ------------------
    story.append(Spacer(1, 15))
    story.append(Paragraph("CLOUDOPS INTEL SRE PLATFORM &bull; SENSOR NODE DIAGNOSTICS", styles["CoverOver"]))
    story.append(Paragraph("Individual Sensor Performance Report", styles["CoverTitle"]))
    story.append(Paragraph(
        f"Workstation Telemetry, Resource Profiling, Incident History & Health Audit for <b>{hostname}</b>",
        styles["CoverSubtitle"]
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0284c7"), spaceAfter=12))

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    start_str = str(host_data.get("time_window_start", "")).replace("T", " ")[:19] + " UTC"
    end_str = str(host_data.get("time_window_end", "")).replace("T", " ")[:19] + " UTC"

    # ------------------ SECTION 1: HOST IDENTITY ------------------
    story.append(Paragraph("1. Workstation & Sensor Identification", styles["SectionH1"]))

    id_rows = [
        [
            Paragraph("<b>Hostname:</b>", styles["TableCell"]), Paragraph(f"<b>{hostname}</b>", styles["TableCell"]),
            Paragraph("<b>Host ID:</b>", styles["TableCell"]), Paragraph(f"<code>{host_id}</code>", styles["TableCellMono"]),
        ],
        [
            Paragraph("<b>Assigned Name:</b>", styles["TableCell"]), Paragraph(str(hi.get("assigned_name") or "—"), styles["TableCell"]),
            Paragraph("<b>Device UUID:</b>", styles["TableCell"]), Paragraph(f"<code>{str(hi.get('device_uuid') or '—')[:24]}...</code>" if hi.get("device_uuid") else "—", styles["TableCellMono"]),
        ],
        [
            Paragraph("<b>IP Address:</b>", styles["TableCell"]), Paragraph(f"<code>{hi.get('ip_address') or '—'}</code>", styles["TableCellMono"]),
            Paragraph("<b>MAC Address:</b>", styles["TableCell"]), Paragraph(f"<code>{hi.get('mac_address') or '—'}</code>", styles["TableCellMono"]),
        ],
        [
            Paragraph("<b>Environment:</b>", styles["TableCell"]), Paragraph(str(hi.get("environment") or "—"), styles["TableCell"]),
            Paragraph("<b>Room / Lab:</b>", styles["TableCell"]), Paragraph(f"{hi.get('lab_name') or ''} {hi.get('room') or '—'}".strip(), styles["TableCell"]),
        ],
        [
            Paragraph("<b>Operating System:</b>", styles["TableCell"]), Paragraph(str(hi.get("os_version") or "Windows (NT Kernel)"), styles["TableCell"]),
            Paragraph("<b>Agent Version:</b>", styles["TableCell"]), Paragraph(str(hi.get("agent_version") or "v3.6.0"), styles["TableCell"]),
        ],
        [
            Paragraph("<b>Report Identifier:</b>", styles["TableCell"]), Paragraph(f"<code>{host_data.get('report_id', 'RPT-HOST')}</code>", styles["TableCellMono"]),
            Paragraph("<b>Audit Horizon:</b>", styles["TableCell"]), Paragraph(f"{host_data.get('reporting_period_hours', 24)} Hours", styles["TableCell"]),
        ],
    ]
    id_table = Table(id_rows, colWidths=[120, 141, 120, 142])
    id_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 4),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(id_table)
    story.append(Spacer(1, 10))

    # ------------------ SECTION 2: HEALTH SUMMARY ------------------
    story.append(Paragraph("2. Individual PC Health Summary & Telemetry Freshness", styles["SectionH1"]))

    conn_status = host_data.get("connectivity_status", "NO_DATA")
    if conn_status == "ONLINE":
        status_badge = "<font color='#059669'><b>ONLINE (Receiving Telemetry)</b></font>"
    elif conn_status == "OFFLINE":
        status_badge = "<font color='#dc2626'><b>OFFLINE (Heartbeat Ceased)</b></font>"
    else:
        status_badge = "<font color='#64748b'><b>NO TELEMETRY RECORDED</b></font>"

    lh = host_data.get("last_heartbeat")
    lh_str = str(lh).replace("T", " ")[:19] + " UTC" if lh else "Never Recorded"

    avail_pct = host_data.get("telemetry_availability_pct")
    avail_str = f"{avail_pct:.1f}%" if avail_pct is not None else "—"

    cpu_s = host_data.get("cpu_stats", {})
    mem_s = host_data.get("memory_stats", {})
    disk_s = host_data.get("disk_stats", {})
    net_sent = host_data.get("network_sent_stats", {})
    net_recv = host_data.get("network_recv_stats", {})

    health_rows = [
        [
            Paragraph("<b>Connectivity Status:</b>", styles["TableCell"]), Paragraph(status_badge, styles["TableCell"]),
            Paragraph("<b>Last Heartbeat:</b>", styles["TableCell"]), Paragraph(lh_str, styles["TableCellMono"]),
        ],
        [
            Paragraph("<b>Latest CPU Utilization:</b>", styles["TableCell"]), Paragraph(f"{cpu_s.get('latest')}%" if cpu_s.get("latest") is not None else "—", styles["TableCellMono"]),
            Paragraph("<b>Latest RAM Utilization:</b>", styles["TableCell"]), Paragraph(f"{mem_s.get('latest')}%" if mem_s.get("latest") is not None else "—", styles["TableCellMono"]),
        ],
        [
            Paragraph("<b>Latest Disk Storage:</b>", styles["TableCell"]), Paragraph(f"{disk_s.get('latest')}%" if disk_s.get("latest") is not None else "—", styles["TableCellMono"]),
            Paragraph("<b>Latest Net Traffic (Out/In):</b>", styles["TableCell"]), Paragraph(f"{net_sent.get('latest', 0.0):.1f} / {net_recv.get('latest', 0.0):.1f} MB", styles["TableCellMono"]),
        ],
        [
            Paragraph("<b>Active Host Alerts:</b>", styles["TableCell"]), Paragraph(f"<b>{host_data.get('active_alerts_count', 0)}</b> active ({host_data.get('total_alerts', 0)} total)", styles["TableCell"]),
            Paragraph("<b>Telemetry Availability:</b>", styles["TableCell"]), Paragraph(f"<b>{avail_str}</b> ({host_data.get('total_samples', 0)} samples)", styles["TableCell"]),
        ],
    ]
    health_table = Table(health_rows, colWidths=[130, 131, 130, 132])
    health_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 4.5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(health_table)
    story.append(Spacer(1, 10))

    # ------------------ SECTION 3: RESOURCE PERFORMANCE & CHARTS ------------------
    story.append(Paragraph("3. Resource Performance History & Statistical Analysis", styles["SectionH1"]))

    # Statistical Summary Table
    def fmt_stat(val):
        return f"{val:.1f}" if val is not None else "—"

    def fmt_ts(dt_val):
        if not dt_val:
            return "—"
        return str(dt_val).replace("T", " ")[:19]

    stats_rows = [
        [
            Paragraph("<b>Subsystem</b>", styles["TableHeader"]),
            Paragraph("<b>Latest</b>", styles["TableHeader"]),
            Paragraph("<b>Average</b>", styles["TableHeader"]),
            Paragraph("<b>Peak (Max)</b>", styles["TableHeader"]),
            Paragraph("<b>Peak Timestamp</b>", styles["TableHeader"]),
            Paragraph("<b>Minimum</b>", styles["TableHeader"]),
            Paragraph("<b>Valid Samples</b>", styles["TableHeader"]),
        ],
        [
            Paragraph("<b>CPU Utilization</b>", styles["TableCell"]),
            Paragraph(f"{fmt_stat(cpu_s.get('latest'))}%", styles["TableCellMono"]),
            Paragraph(f"{fmt_stat(cpu_s.get('avg'))}%", styles["TableCellMono"]),
            Paragraph(f"<b>{fmt_stat(cpu_s.get('max'))}%</b>", styles["TableCellMono"]),
            Paragraph(fmt_ts(cpu_s.get("peak_timestamp")), styles["TableCellMono"]),
            Paragraph(f"{fmt_stat(cpu_s.get('min'))}%", styles["TableCellMono"]),
            Paragraph(str(cpu_s.get("sample_count", 0)), styles["TableCellMono"]),
        ],
        [
            Paragraph("<b>Memory (RAM)</b>", styles["TableCell"]),
            Paragraph(f"{fmt_stat(mem_s.get('latest'))}%", styles["TableCellMono"]),
            Paragraph(f"{fmt_stat(mem_s.get('avg'))}%", styles["TableCellMono"]),
            Paragraph(f"<b>{fmt_stat(mem_s.get('max'))}%</b>", styles["TableCellMono"]),
            Paragraph(fmt_ts(mem_s.get("peak_timestamp")), styles["TableCellMono"]),
            Paragraph(f"{fmt_stat(mem_s.get('min'))}%", styles["TableCellMono"]),
            Paragraph(str(mem_s.get("sample_count", 0)), styles["TableCellMono"]),
        ],
        [
            Paragraph("<b>Disk Storage</b>", styles["TableCell"]),
            Paragraph(f"{fmt_stat(disk_s.get('latest'))}%", styles["TableCellMono"]),
            Paragraph(f"{fmt_stat(disk_s.get('avg'))}%", styles["TableCellMono"]),
            Paragraph(f"<b>{fmt_stat(disk_s.get('max'))}%</b>", styles["TableCellMono"]),
            Paragraph(fmt_ts(disk_s.get("peak_timestamp")), styles["TableCellMono"]),
            Paragraph(f"{fmt_stat(disk_s.get('min'))}%", styles["TableCellMono"]),
            Paragraph(str(disk_s.get("sample_count", 0)), styles["TableCellMono"]),
        ],
        [
            Paragraph("<b>Network Out (MB)</b>", styles["TableCell"]),
            Paragraph(f"{fmt_stat(net_sent.get('latest'))}", styles["TableCellMono"]),
            Paragraph(f"{fmt_stat(net_sent.get('avg'))}", styles["TableCellMono"]),
            Paragraph(f"<b>{fmt_stat(net_sent.get('max'))}</b>", styles["TableCellMono"]),
            Paragraph(fmt_ts(net_sent.get("peak_timestamp")), styles["TableCellMono"]),
            Paragraph(f"{fmt_stat(net_sent.get('min'))}", styles["TableCellMono"]),
            Paragraph(str(net_sent.get("sample_count", 0)), styles["TableCellMono"]),
        ],
        [
            Paragraph("<b>Network In (MB)</b>", styles["TableCell"]),
            Paragraph(f"{fmt_stat(net_recv.get('latest'))}", styles["TableCellMono"]),
            Paragraph(f"{fmt_stat(net_recv.get('avg'))}", styles["TableCellMono"]),
            Paragraph(f"<b>{fmt_stat(net_recv.get('max'))}</b>", styles["TableCellMono"]),
            Paragraph(fmt_ts(net_recv.get("peak_timestamp")), styles["TableCellMono"]),
            Paragraph(f"{fmt_stat(net_recv.get('min'))}", styles["TableCellMono"]),
            Paragraph(str(net_recv.get("sample_count", 0)), styles["TableCellMono"]),
        ],
    ]
    stats_table = Table(stats_rows, colWidths=[95, 60, 60, 65, 115, 60, 68])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('PADDING', (0,0), (-1,-1), 3.5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 8))

    # Time-Series Charts (CPU & RAM)
    ts_list = [m["timestamp"] for m in metric_samples if "timestamp" in m]
    cpu_list = [m["cpu_percent"] for m in metric_samples if "cpu_percent" in m and m["cpu_percent"] is not None]
    ram_list = [m["memory_percent"] for m in metric_samples if "memory_percent" in m and m["memory_percent"] is not None]
    disk_list = [m["disk_percent"] for m in metric_samples if "disk_percent" in m and m["disk_percent"] is not None]
    sent_list = [m.get("network_sent_mb", 0.0) for m in metric_samples]
    recv_list = [m.get("network_received_mb", 0.0) for m in metric_samples]

    cpu_chart_buf = create_host_timeseries_chart(
        ts_list, cpu_list, "CPU Utilization (%) Over Time", "CPU %", "#0284c7", warn_thresh=80.0, crit_thresh=95.0, max_val=100.0
    )
    if cpu_chart_buf:
        story.append(Image(cpu_chart_buf, width=PRINT_WIDTH, height=135))
        story.append(Spacer(1, 6))

    ram_chart_buf = create_host_timeseries_chart(
        ts_list, ram_list, "RAM Utilization (%) Over Time", "RAM %", "#8b5cf6", warn_thresh=85.0, crit_thresh=95.0, max_val=100.0
    )
    if ram_chart_buf:
        story.append(Image(ram_chart_buf, width=PRINT_WIDTH, height=135))
        story.append(Spacer(1, 6))

    if not cpu_chart_buf and not ram_chart_buf:
        story.append(Paragraph("<i>Insufficient historical samples to plot continuous time-series curves.</i>", styles["Body"]))

    story.append(PageBreak())

    # ------------------ SECTION 3 CONT: DISK & NETWORK CHARTS ------------------
    story.append(Paragraph("Storage & Network Bandwidth Profiling", styles["SectionH2"]))

    disk_chart_buf = create_host_timeseries_chart(
        ts_list, disk_list, "Storage Utilization (%) Over Time", "Disk %", "#10b981", warn_thresh=85.0, crit_thresh=95.0, max_val=100.0
    )
    if disk_chart_buf:
        story.append(Image(disk_chart_buf, width=PRINT_WIDTH, height=135))
        story.append(Spacer(1, 6))

    net_chart_buf = create_host_network_chart(ts_list, sent_list, recv_list)
    if net_chart_buf:
        story.append(Image(net_chart_buf, width=PRINT_WIDTH, height=135))
        story.append(Spacer(1, 8))

    # ------------------ SECTION 4: CONNECTIVITY & AGENT AUDIT ------------------
    story.append(Paragraph("4. Connectivity & Sensor Agent Reliability", styles["SectionH1"]))
    conn_text = (
        f"Workstation <b>{hostname}</b> recorded <b>{host_data.get('total_samples', 0)}</b> valid telemetry samples "
        f"across the requested window. Current connectivity status is <b>{conn_status}</b> with a telemetry "
        f"availability ratio of <b>{avail_str}</b>. Heartbeats are validated against the standard 90s cutoff."
    )
    story.append(Paragraph(conn_text, styles["Body"]))
    story.append(Spacer(1, 8))

    # ------------------ SECTION 5: INDIVIDUAL PC ALERTS ------------------
    story.append(Paragraph("5. Workstation Alert & Anomaly Incident History", styles["SectionH1"]))

    alerts = host_data.get("alerts", [])
    alert_header = [
        Paragraph("<b>Timestamp</b>", styles["TableHeader"]),
        Paragraph("<b>Severity</b>", styles["TableHeader"]),
        Paragraph("<b>Category</b>", styles["TableHeader"]),
        Paragraph("<b>Metric</b>", styles["TableHeader"]),
        Paragraph("<b>Reason / Threshold</b>", styles["TableHeader"]),
        Paragraph("<b>Status</b>", styles["TableHeader"]),
    ]
    alert_rows = [alert_header]

    for a in alerts[:15]:
        sev = a.get("severity", "warning").lower()
        if sev == "critical":
            sev_cell = "<font color='#dc2626'><b>CRITICAL</b></font>"
        elif sev == "warning":
            sev_cell = "<font color='#d97706'><b>WARNING</b></font>"
        else:
            sev_cell = "<font color='#0284c7'><b>INFO</b></font>"

        ts_str = str(a.get("timestamp", "")).replace("T", " ")[:19]
        reason_str = a.get("message", "—")
        if a.get("threshold"):
            reason_str += f" (Threshold: {a.get('threshold')})"

        alert_rows.append([
            Paragraph(ts_str, styles["TableCellMono"]),
            Paragraph(sev_cell, styles["TableCell"]),
            Paragraph(str(a.get("kind", "—")), styles["TableCell"]),
            Paragraph(str(a.get("metric", "—")), styles["TableCellMono"]),
            Paragraph(reason_str, styles["TableCell"]),
            Paragraph(str(a.get("status", "—")).upper(), styles["TableCellMono"]),
        ])

    if len(alert_rows) == 1:
        alert_rows.append([Paragraph("No active or historical alerts recorded for this workstation.", styles["TableCell"])] + [Paragraph("—", styles["TableCell"])] * 5)

    alert_table = Table(alert_rows, colWidths=[85, 55, 60, 65, 198, 60], repeatRows=1)
    alert_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('PADDING', (0,0), (-1,-1), 3.5),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(alert_table)

    story.append(PageBreak())

    # ------------------ SECTION 6: INDIVIDUAL SECURITY EVENTS ------------------
    story.append(Paragraph("6. Workstation Security & Authentication Events", styles["SectionH1"]))

    sec_events = host_data.get("security_events", [])
    if sec_events:
        sec_rows = [
            [
                Paragraph("<b>Timestamp</b>", styles["TableHeader"]),
                Paragraph("<b>Event Type</b>", styles["TableHeader"]),
                Paragraph("<b>Severity</b>", styles["TableHeader"]),
                Paragraph("<b>Description</b>", styles["TableHeader"]),
                Paragraph("<b>Status</b>", styles["TableHeader"]),
            ]
        ]
        for se in sec_events[:10]:
            ts_str = str(se.get("timestamp", "")).replace("T", " ")[:19]
            sec_rows.append([
                Paragraph(ts_str, styles["TableCellMono"]),
                Paragraph(str(se.get("event_type", "—")), styles["TableCellMono"]),
                Paragraph(str(se.get("severity", "—")).upper(), styles["TableCell"]),
                Paragraph(str(se.get("description", "—")), styles["TableCell"]),
                Paragraph(str(se.get("status", "—")).upper(), styles["TableCellMono"]),
            ])
        sec_table = Table(sec_rows, colWidths=[85, 95, 55, 228, 60], repeatRows=1)
        sec_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
            ('PADDING', (0,0), (-1,-1), 3.5),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(sec_table)
    else:
        story.append(Paragraph("<i>Zero anomalous authentication attempts or flow breaches logged specifically for this host.</i>", styles["Body"]))

    story.append(Spacer(1, 6))
    sec_disclaimer = Table([[Paragraph(f"<b>Security Notice:</b> {host_data.get('security_disclaimer', '')}", styles["Callout"])]], colWidths=[PRINT_WIDTH])
    sec_disclaimer.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#fffbeb")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#f59e0b")),
        ('PADDING', (0,0), (-1,-1), 5.5),
    ]))
    story.append(sec_disclaimer)
    story.append(Spacer(1, 10))

    # ------------------ SECTION 7: TECHNICAL ASSESSMENT ------------------
    story.append(Paragraph("7. Workstation Technical Assessment", styles["SectionH1"]))
    story.append(Paragraph(host_data.get("technical_assessment", "Assessment pending telemetry evaluation."), styles["Body"]))
    story.append(Spacer(1, 10))

    # ------------------ SECTION 8: ACTIONABLE RECOMMENDATIONS ------------------
    story.append(Paragraph("8. SRE Operations & Maintenance Recommendations", styles["SectionH1"]))
    for rec in host_data.get("recommendations", []):
        story.append(Paragraph(f"• {rec}", styles["Bullet"]))

    story.append(Spacer(1, 14))

    # Verification Footer
    footer_text = (
        f"<b>Audit Baseline:</b> Report generated for <b>{hostname}</b> (Host ID: {host_id}) at {now_str} by {requester_email}. "
        f"Data extracted directly from SQLite database in WAL mode with strict host scoping."
    )
    footer_table = Table([[Paragraph(footer_text, styles["Callout"])]], colWidths=[PRINT_WIDTH])
    footer_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 5.5),
    ]))
    story.append(footer_table)

    doc.build(story, canvasmaker=HostNumberedCanvas)
    buffer.seek(0)
    return buffer.getvalue()
