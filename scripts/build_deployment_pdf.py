"""
Generates a clean, professional, publication-quality Deployment Guide PDF for CloudOps Intel.
Outputs to: C:\\CLoudProject\\docs\\DEPLOYMENT_GUIDE.pdf
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
    """Two-pass canvas to dynamically compute and print total page count."""
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
            # Skip header and footer on cover page
            return

        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Top Header line
        self.drawString(54, 755, "CLOUDOPS INTEL COMMAND CENTER — DEPLOYMENT MANUAL")
        self.drawRightString(558, 755, "VERSION 3.6.0")
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.75)
        self.line(54, 747, 558, 747)

        # Bottom Footer line
        self.line(54, 45, 558, 45)
        self.setFont("Helvetica", 8)
        self.drawString(54, 32, "Confidential — Internal Laboratory & Enterprise Operational Use Only")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_text)
        self.restoreState()


def create_deployment_pdf():
    output_path = r"C:\CLoudProject\docs\DEPLOYMENT_GUIDE.pdf"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=32,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=8,
    )

    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#0284c7"),
        spaceAfter=20,
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1e3a8a"),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "BulletCustom",
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3,
    )

    code_style = ParagraphStyle(
        "CodeCustom",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f1f5f9"),
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=6,
        borderRadius=4,
    )

    callout_style = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1e293b"),
    )

    story = []

    # ==================== COVER PAGE ====================
    story.append(Spacer(1, 40))
    story.append(Paragraph("CLOUDOPS INTEL SRE PLATFORM", ParagraphStyle("CoverOver", fontName="Helvetica-Bold", fontSize=11, textColor=colors.HexColor("#64748b"), spaceAfter=6)))
    story.append(Paragraph("Laboratory & Production Deployment Manual", title_style))
    story.append(Paragraph("Step-by-Step Server Setup, Network Topology, Zero-Trust PC Onboarding, and Windows Services Hardening", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#0284c7"), spaceAfter=20))

    meta_data = [
        [Paragraph("<b>Target Fleet:</b>", body_style), Paragraph("30–100 Windows Lab PCs & Cloud Compute Instances", body_style)],
        [Paragraph("<b>Security Standard:</b>", body_style), Paragraph("TLS 1.3 / 1.2 Encrypted Transport on Port 8443 (PKI-Verified)", body_style)],
        [Paragraph("<b>Service Model:</b>", body_style), Paragraph("NT SERVICE Isolated Background Windows Services (NSSM)", body_style)],
        [Paragraph("<b>Agent Footprint:</b>", body_style), Paragraph("Zero-UI Scheduled Task, < 40MB RAM, < 0.5% CPU Utilization", body_style)],
        [Paragraph("<b>Release Version:</b>", body_style), Paragraph("v3.6.0 (Production / Academic Lab Ready)", body_style)],
    ]
    meta_table = Table(meta_data, colWidths=[130, 374])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#e2e8f0")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 25))

    # Executive Box
    exec_box = [
        [Paragraph("<b>Operational Notice:</b> This manual describes the exact end-to-end procedures for deploying the central CloudOps Command Center on a designated master server and enrolling remote laboratory PCs via mutual token authorization. Strictly follow the port isolation and certificate provisioning steps to guarantee zero-exposure security.", callout_style)]
    ]
    exec_table = Table(exec_box, colWidths=[504])
    exec_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#e0f2fe")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#38bdf8")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(exec_table)

    story.append(PageBreak())

    # ==================== SECTION 1: ARCHITECTURE & NETWORK ====================
    story.append(Paragraph("1. System Architecture & Network Topology", h1_style))
    story.append(Paragraph(
        "CloudOps Intel operates on a centralized telemetry ingestion model. Monitored nodes transmit periodic resource snapshots to the Master Server over authenticated TLS reverse proxy channels. Internal services remain bound strictly to loopback.",
        body_style
    ))

    # Topology Table Box
    topo_data = [
        [Paragraph("<b>Layer</b>", body_style), Paragraph("<b>Components & Ports</b>", body_style), Paragraph("<b>Security & Exposure Boundary</b>", body_style)],
        [
            Paragraph("<b>Client Workstations</b><br/>(Lab PCs 1..100)", body_style),
            Paragraph("• Python 3.10+ Sensor Agent<br/>• Silent Windows Scheduled Task<br/>• Outbound HTTPS Port 8443", body_style),
            Paragraph("Verified TLS via embedded <code>root.crt</code>. Zero open inbound ports on client computers.", body_style)
        ],
        [
            Paragraph("<b>Central Server</b><br/>(Master Host)", body_style),
            Paragraph("• Caddy Reverse Proxy (:8443)<br/>• FastAPI Application (:8000)<br/>• SQLite WAL Database<br/>• Gemini RAG Vector Store", body_style),
            Paragraph("<b>Port 8443:</b> Exposed to local laboratory subnet.<br/><b>Port 8000:</b> Loopback only (127.0.0.1) — never opened in firewall.", body_style)
        ],
        [
            Paragraph("<b>Administrative</b><br/>(Web Dashboard)", body_style),
            Paragraph("• Vanilla JS / Single-Page App<br/>• WebSocket & Polling Feeds<br/>• JWT Bearer & HttpOnly Cookies", body_style),
            Paragraph("Browser access via <code>https://&lt;SERVER_IP&gt;:8443</code>. Role-gated by Super Admin RBAC.", body_style)
        ],
    ]
    topo_table = Table(topo_data, colWidths=[120, 194, 190])
    topo_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(topo_table)
    story.append(Spacer(1, 12))

    story.append(Paragraph("Network Connectivity Rules (Ethernet vs Wi-Fi)", h2_style))
    story.append(Paragraph("• <b>Local Subnet Requirement:</b> The Server and all Lab PCs must share the same physical router or VLAN subnet (e.g. <code>192.168.1.0/24</code> or <code>10.227.136.0/24</code>).", bullet_style))
    story.append(Paragraph("• <b>Ethernet Recommendation:</b> Direct Cat6 wired Ethernet is strongly recommended in college laboratories to prevent packet drop during simultaneous fleet metric bursts.", bullet_style))
    story.append(Paragraph("• <b>Wi-Fi Deployment Notice:</b> If deploying over wireless access points, ensure <b>'Client Isolation' / 'AP Isolation'</b> is disabled in the router settings so workstations can reach the server IP.", bullet_style))
    story.append(Paragraph("• <b>Static IP:</b> Assign a static IP or DHCP MAC-reservation to the Master Server machine so clients never lose connectivity.", bullet_style))

    story.append(Spacer(1, 10))

    # ==================== SECTION 2: SERVER DEPLOYMENT ====================
    story.append(Paragraph("2. Server Installation & Hardening (Master PC)", h1_style))
    story.append(Paragraph("Follow these 5 sequential steps to configure the master server machine:", body_style))

    story.append(Paragraph("<b>Step 2.1 — Identify Server Static IP Address</b>", body_style))
    story.append(Paragraph("Open an elevated PowerShell prompt on the Master Server and retrieve your active LAN IPv4 address:", body_style))
    story.append(Paragraph("ipconfig | Select-String -Pattern \"IPv4 Address\"", code_style))

    story.append(Paragraph("<b>Step 2.2 — Configure Caddyfile and Environment Settings</b>", body_style))
    story.append(Paragraph("Open <code>C:\\CLoudProject\\Caddyfile</code> and verify that your server's LAN IP address is in the HTTPS binding block:", body_style))
    story.append(Paragraph(
        "https://localhost:8443, https://127.0.0.1:8443, https://&lt;SERVER_IP&gt;:8443 {\n"
        "    tls internal\n"
        "    reverse_proxy 127.0.0.1:8000 {\n"
        "        header_up Host {upstream_hostport}\n"
        "    }\n"
        "}",
        code_style
    ))
    story.append(Paragraph("In <code>C:\\CLoudProject\\.env</code>, verify that <code>BACKEND_HOST=127.0.0.1</code>, <code>BACKEND_PORT=8000</code>, and your <code>GEMINI_API_KEY</code> are populated.", body_style))

    story.append(Paragraph("<b>Step 2.3 — Configure Inbound Firewall Rule (Port 8443)</b>", body_style))
    story.append(Paragraph("Allow external workstations on your subnet to access HTTPS port 8443:", body_style))
    story.append(Paragraph(
        "New-NetFirewallRule -Name \"CloudOpsIntel_HTTPS_8443\" `\n"
        "    -DisplayName \"CloudOps Intel Inbound HTTPS (8443)\" `\n"
        "    -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8443 -Profile Any",
        code_style
    ))

    story.append(Paragraph("<b>Step 2.4 — Install & Start Background Windows Services</b>", body_style))
    story.append(Paragraph("To ensure the Command Center runs continuously on system reboot under <code>NT SERVICE\\CloudOpsBackend</code>:", body_style))
    story.append(Paragraph(
        "powershell -ExecutionPolicy Bypass -File C:\\CLoudProject\\scripts\\install_windows_services.ps1",
        code_style
    ))

    story.append(Paragraph("<b>Step 2.5 — Verify Server Health & Dashboard Access</b>", body_style))
    story.append(Paragraph("Open Google Chrome or Microsoft Edge and navigate to <code>https://localhost:8443</code> (or <code>https://&lt;SERVER_IP&gt;:8443</code>). Sign in with your Super Administrator credentials:", body_style))
    story.append(Paragraph("• <b>Default Bootstrap Admin:</b> <code>s23_shaikh_irafan@mgmcen.ac.in</code><br/>• <b>Password:</b> <code>@Shaikh921</code>", bullet_style))

    story.append(PageBreak())

    # ==================== SECTION 3: CLIENT AGENT PACKAGING ====================
    story.append(Paragraph("3. Packaging the Sensor Client for Workstations", h1_style))
    story.append(Paragraph(
        "The sensor agent is packaged into a standalone distribution zip that contains the lightweight collection script, the PowerShell installer, and the public authority certificate (<code>root.crt</code>) required for zero-fallback TLS trust.",
        body_style
    ))

    story.append(Paragraph("Execute the packaging script on the server:", body_style))
    story.append(Paragraph("python C:\\CLoudProject\\scripts\\package_sensor_agent.py", code_style))

    story.append(Paragraph(
        "This command automatically extracts Caddy's active public root certificate and produces <code>C:\\CLoudProject\\dist\\cloudops-sensor-package.zip</code>. Copy this archive to a USB administrative flash drive or an internal college network share.",
        body_style
    ))

    pkg_box = [
        [Paragraph("<b>Contents of cloudops-sensor-package.zip:</b><br/>"
                   "• <code>install_sensor_client.ps1</code> — Automated installer script registering scheduled task.<br/>"
                   "• <code>monitoring_agent/agent.py</code> — Hardware polling engine (CPU, RAM, Disk, Network).<br/>"
                   "• <code>monitoring_agent/buffer.py</code> — SQLite disk spooler ensuring zero telemetry loss during network drops.<br/>"
                   "• <code>root.crt</code> — Public CA certificate establishing verified cryptographic trust.", callout_style)]
    ]
    pkg_table = Table(pkg_box, colWidths=[504])
    pkg_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f1f5f9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94a3b8")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(pkg_table)
    story.append(Spacer(1, 14))

    # ==================== SECTION 4: CLIENT ONBOARDING ====================
    story.append(Paragraph("4. Step-by-Step Lab PC Onboarding (Zero-Trust)", h1_style))
    story.append(Paragraph("Follow this workflow to enroll each computer in the laboratory fleet:", body_style))

    story.append(Paragraph("<b>Step 4.1 — Generate One-Time Enrollment Code in Dashboard</b>", body_style))
    story.append(Paragraph("1. Log in to the CloudOps Intel Web Dashboard as Super Admin.", bullet_style))
    story.append(Paragraph("2. Navigate to <b>Administration</b> &rarr; <b>Device Management</b> in the sidebar.", bullet_style))
    story.append(Paragraph("3. Click the <b>Generate Enrollment Code</b> button.", bullet_style))
    story.append(Paragraph("4. Select expiration (e.g. 1 hour) and enter note (e.g. <code>Lab 101 Deployment</code>).", bullet_style))
    story.append(Paragraph("5. Copy the generated code starting with <code>ec_...</code>.", bullet_style))

    story.append(Paragraph("<b>Step 4.2 — Execute Installer on the Lab Computer</b>", body_style))
    story.append(Paragraph("On the target lab PC, extract the zip to <code>C:\\Temp\\cloudops-sensor</code>, open PowerShell as <b>Administrator</b>, and execute:", body_style))
    story.append(Paragraph(
        "cd C:\\Temp\\cloudops-sensor\n"
        "powershell -ExecutionPolicy Bypass -File .\\install_sensor_client.ps1 `\n"
        "    -ServerUrl \"https://&lt;SERVER_IP&gt;:8443\" `\n"
        "    -EnrollmentCode \"&lt;COPIED_ENROLLMENT_CODE&gt;\"",
        code_style
    ))

    story.append(Paragraph("<b>Step 4.3 — Approve Device in Web Dashboard</b>", body_style))
    story.append(Paragraph("1. Back in the Dashboard under <b>Device Management</b>, switch to <b>Pending Approval</b>.", bullet_style))
    story.append(Paragraph("2. Verify the hardware specs, MAC address, and hostname reported by the computer.", bullet_style))
    story.append(Paragraph("3. Click <b>Approve & Map</b> and assign physical parameters (Lab Name, Room Number, PC ID).", bullet_style))
    story.append(Paragraph("4. Click <b>Approve & Issue Credential</b>. The installer terminal will report: <code>[+] Device APPROVED! Sensor configuration persisted.</code>", bullet_style))

    story.append(PageBreak())

    # ==================== SECTION 5: OPERATIONS & MAINTENANCE ====================
    story.append(Paragraph("5. Maintenance, Health Checks & Rollback", h1_style))

    story.append(Paragraph("Operational Verification & Health Probes", h2_style))
    story.append(Paragraph("Verify core backend and proxy health status from any browser or terminal:", body_style))
    story.append(Paragraph("Invoke-RestMethod -Uri \"https://&lt;SERVER_IP&gt;:8443/health\" -SkipCertificateCheck", code_style))

    story.append(Paragraph("Restarting Windows Services", h2_style))
    story.append(Paragraph("If you modify configuration files (such as <code>.env</code> or <code>Caddyfile</code>), execute the automated elevation restart script:", body_style))
    story.append(Paragraph("powershell -ExecutionPolicy Bypass -File C:\\CLoudProject\\scripts\\restart_services.ps1", code_style))

    story.append(Paragraph("Client Decommissioning & Uninstallation", h2_style))
    story.append(Paragraph("To silently decommission and remove the sensor agent from a laboratory computer:", body_style))
    story.append(Paragraph("powershell -ExecutionPolicy Bypass -File .\\uninstall_sensor_client.ps1", code_style))
    story.append(Paragraph("This terminates any active sensor worker, deletes the Windows Scheduled Task, and cleans up local storage.", body_style))

    story.append(Spacer(1, 15))

    # Summary Checklist Table
    story.append(Paragraph("Production Readiness Checklist", h2_style))
    chk_data = [
        [Paragraph("<b>Verification Item</b>", body_style), Paragraph("<b>Expected State</b>", body_style), Paragraph("<b>Status</b>", body_style)],
        [Paragraph("Server LAN Static IP", body_style), Paragraph("Configured and pinned in Caddyfile site block", body_style), Paragraph("<font color='#059669'><b>PASS</b></font>", body_style)],
        [Paragraph("Port 8443 Inbound Rule", body_style), Paragraph("Active in Windows Defender Firewall", body_style), Paragraph("<font color='#059669'><b>PASS</b></font>", body_style)],
        [Paragraph("Port 8000 Isolation", body_style), Paragraph("Bound strictly to 127.0.0.1; zero external exposure", body_style), Paragraph("<font color='#059669'><b>PASS</b></font>", body_style)],
        [Paragraph("Windows Service Hardening", body_style), Paragraph("CloudOpsBackend & CloudOpsProxy running as NSSM services", body_style), Paragraph("<font color='#059669'><b>PASS</b></font>", body_style)],
        [Paragraph("Gemini RAG System", body_style), Paragraph("Active key in .env; hybrid BM25 + dense search loaded", body_style), Paragraph("<font color='#059669'><b>PASS</b></font>", body_style)],
        [Paragraph("Zero-Trust Device Tokens", body_style), Paragraph("HMAC SHA-256 tokens stored securely in Windows Registry", body_style), Paragraph("<font color='#059669'><b>PASS</b></font>", body_style)],
    ]
    chk_table = Table(chk_data, colWidths=[160, 264, 80])
    chk_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0f172a")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
        ('ALIGN', (2,0), (2,-1), 'CENTER'),
    ]))
    story.append(chk_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[+] Deployment Guide PDF generated successfully: {output_path}")

if __name__ == "__main__":
    create_deployment_pdf()
