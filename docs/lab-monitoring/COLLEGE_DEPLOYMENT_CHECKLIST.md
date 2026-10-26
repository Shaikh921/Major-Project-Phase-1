# CloudOps Intel — College Deployment Readiness Checklist
**Document Version:** 1.0.0  
**Target Fleet:** 30–100 Windows Lab PCs  
**Deployment Boundary:** Staged Pilot (Requires Written IT Authorization)  

---

## 1. Explicit Scope Boundary Statement

> **CONFIRMATION:**  
> During this engineering phase, **ZERO** software was deployed to physical college PCs, **ZERO** network traffic was transmitted across the physical college network, and **ZERO** firewall or switch settings were modified. All implementations, packaging, and tests were conducted strictly in isolated local development environments on `C:\CLoudProject`.

---

## 2. Pre-Deployment Authorization Checklist

Before any sensor agent software is copied to, installed on, or executed across physical college lab computers, the following administrative and network prerequisites **MUST** be formally completed and signed off:

### Section A: Administrative Authorization
- [ ] **College IT Department Written Approval:** Formal approval to deploy monitoring sensor software on college-owned laboratory computers.
- [ ] **Named Administrator Assigned:** Identification of the designated college Super Administrator responsible for generating enrollment codes, reviewing pending devices, and approving physical mappings.
- [ ] **Pilot Group Definition:** Selection of a small, controlled pilot group (e.g. 2 to 5 test PCs in a single lab bench) before any fleet-wide rollout.

### Section B: Network & Server Infrastructure
- [ ] **Stable Server Address Established:** Confirmation of whether the server will use:
  - An approved static IP address (e.g. `10.x.x.x` or `192.168.x.x`); OR
  - An approved internal DNS name (e.g. `cloudops.lab.internal`).
- [ ] **Server Firewall Rule:** Creation of an inbound firewall allow rule on the server for **TCP Port 8443** limited to the laboratory subnet.
- [ ] **Client Outbound Connectivity:** Verification that lab workstations can reach the server on `https://<SERVER_IP_OR_DNS>:8443`.
- [ ] **Caddy SAN Configuration:** Update of `Caddyfile` on the server to include the approved static IP or DNS name in the site address block, followed by a Caddy reload (`caddy reload`).

### Section C: Package & Trust Distribution
- [ ] **Public Authority Certificate Extraction:** Verification that `root.crt` matches the active server authority and does **not** contain `root.key`.
- [ ] **Package Integrity Verification:** Computation of SHA-256 checksum on `cloudops-sensor-package.zip` and verification against the expected checksum file.
- [ ] **Installer Storage:** Placement of the verified sensor package zip on an authorized internal network share or USB administrative drive.

### Section D: Workstation Runtime Readiness
- [ ] **Operating System Compatibility:** Windows 10 x64, Windows 11 x64, or Windows Server.
- [ ] **Python Runtime Availability:** Python 3.10+ installed on target PCs (or portable runtime embedded).
- [ ] **Local Administrative Access:** Administrator credentials available to register the Windows Scheduled Task (`CloudOpsSensorAgent`) under `NT AUTHORITY\SYSTEM`.

---

## 3. Step-by-Step Pilot Deployment Walkthrough (One Test PC)

When authorized, follow this exact workflow for each workstation:

1. **Super Admin Log in:**
   - Log into the CloudOps Intel Web Dashboard (`https://<SERVER>:8443`) using Super Admin credentials.
   - Navigate to **Administration** -> **Device Management**.
2. **Generate Enrollment Code:**
   - Click **Generate Enrollment Code**.
   - Select expiration (15 minutes).
   - Enter reference note: `Pilot Lab 1 - Bench 1`.
   - Copy the one-time raw code (`ec_...`).
3. **Execute Workstation Installer:**
   - On the pilot PC, open an Elevated PowerShell Prompt:
     ```powershell
     powershell -ExecutionPolicy Bypass -File .\install_sensor_client.ps1 `
         -ServerUrl "https://<SERVER_IP_OR_DNS>:8443" `
         -EnrollmentCode "<COPIED_ENROLLMENT_CODE>"
     ```
4. **Super Admin Approval:**
   - In the CloudOps Intel Dashboard, click **Pending Approval**.
   - Verify the reported Windows hostname against the physical tag on the computer.
   - Click **Approve & Map**.
   - Assign label: `PC-Lab1-01`, Lab: `Main Lab`, Room: `Room 101`, PC: `01`.
   - Click **Approve & Issue Credential**.
5. **Sensor Ingestion Verification:**
   - The installer terminal will report: `[+] Device APPROVED by Super Admin! Sensor configuration persisted.`
   - In the dashboard **Active Fleet** tab, verify that the workstation appears with status **ONLINE** and healthy telemetry.
   - Verify that CPU, Memory, Disk, and Network telemetry begin populating the **Lab PCs** view.
