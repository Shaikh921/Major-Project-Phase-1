# CloudOps Intel — Enrollment & Device Lifecycle Governance
**Document Version:** 1.0.0  
**Target Audience:** Super Administrators, System Engineers, Lab Technicians  

---

## 1. Overview & Threat Model

Enrolling physical laboratory PCs into a central observability platform introduces significant security considerations:
- Untrusted hardware could attempt to masquerade as an authorized lab workstation.
- Shared ingestion keys embedded in scripts could be extracted by students or unauthorized users.
- Network eavesdropping could intercept newly issued credentials.
- Compromised or retired machines could continue replaying stale telemetry.

To eliminate these vulnerabilities, CloudOps Intel enforces **zero-trust sensor enrollment**, separation of enrollment authority from human accounts, single-use enrollment tokens, physical workstation mapping, and single-use credential retrieval.

---

## 2. The 11-Step Enrollment Workflow

```
[Super Admin]                    [Lab Technician]                     [Sensor PC]                       [CloudOps Server]
      |                                 |                                  |                                    |
      | 1. Generate Enrollment Code     |                                  |                                    |
      |-------------------------------->|                                  |                                    |
      |    (Code: ec_a1b2c3d4...)       |                                  |                                    |
      |                                 | 2. Run install_sensor_client.ps1 |                                    |
      |                                 |--------------------------------->|                                    |
      |                                 |                                  | 3. Submit Enrollment Request       |
      |                                 |                                  |    (Hostname, UUID, Hash(Code))    |
      |                                 |                                  |----------------------------------->|
      |                                 |                                  |                                    | 4. Validate Code,
      |                                 |                                  |                                    |    Mark Code Used,
      |                                 |                                  |                                    |    Create PENDING record,
      |                                 |                                  |                                    |    Generate claim_token
      |                                 |                                  | 5. Return claim_token              |
      |                                 |                                  |<-----------------------------------|
      |                                 |                                  |                                    |
      |                                 |                                  | 6. Poll claim-credential           |
      |                                 |                                  |----------------------------------->| (Returns PENDING)
      | 7. Review Pending Workstations  |                                  |                                    |
      |    in Web Dashboard             |                                  |                                    |
      |    Inspect Hostname & UUID      |                                  |                                    |
      | 8. Assign Physical Mapping      |                                  |                                    |
      |    (Lab, Room, PC Label)        |                                  |                                    |
      | 9. Click "Approve & Issue Key"  |                                  |                                    |
      |-------------------------------------------------------------------------------------------------------->|
      |                                 |                                  |                                    | 10. Issue ak_lab_... Key,
      |                                 |                                  |                                    |     Store pending_raw_key,
      |                                 |                                  |                                    |     Mark APPROVED
      |                                 |                                  | 11. Next poll returns raw key      |
      |                                 |                                  |<-----------------------------------|
      |                                 |                                  |     (Key wiped from DB memory;     |
      |                                 |                                  |      Saved to sensor_config.json)  |
      |                                 |                                  |                                    |
      |                                 |                                  |===> Starts Ingestion Loop =========|
```

### Detailed Step Breakdown:
1. **Enrollment Code Generation:**
   - Super Admin clicks **Generate Enrollment Code** in `Device Management`.
   - Backend creates an ephemeral 32-character hex code (`ec_...`).
   - SHA-256 hash is saved to `enrollment_codes`. Raw code is shown to the Super Admin **only once**.
   - Code expires in 15 minutes by default.
2. **Technician Execution:**
   - Technician executes `install_sensor_client.ps1` with the code and server HTTPS URL.
3. **Sensor Submission:**
   - Sensor queries local Windows hostname (`socket.gethostname()`), hardware UUID, and primary IP.
   - Sensor submits `POST /api/v1/devices/enroll`.
4. **Server Validation:**
   - Server verifies code hash, checks expiration, and asserts `is_used == False`.
   - Code is immediately marked `is_used = True` (atomic single-use enforcement).
   - Server creates a `DeviceEnrollment` record in `PENDING` state and generates a high-entropy `claim_token`.
5. **Pending Isolation:**
   - Sensor receives `claim_token` and begins polling `POST /api/v1/devices/claim-credential` every 5 seconds.
   - The device **CANNOT** submit telemetry while in `PENDING` status. Any submission attempt is rejected with `HTTP 403 Forbidden`.
6. **Physical Verification & Mapping:**
   - Super Admin inspects the pending workstation in the dashboard.
   - Admin verifies that the reported hostname matches the physical sticker on the PC in the lab.
   - Admin enters the physical mapping:
     - Assigned Label: e.g. `PC-Lab1-05`
     - Lab Name: e.g. `Main Computer Center`
     - Room Number: e.g. `Room 304`
     - PC Number: e.g. `05`
7. **Approval & Credential Provisioning:**
   - Super Admin clicks **Approve & Issue Credential**.
   - Server provisions a unique `AgentApiKey` prefixed with `ak_lab_`.
   - The key hash is saved in `agent_api_keys` and linked to `device_uuid`.
   - The raw key is temporarily placed in `pending_raw_key` on the device record awaiting the claim handshake.
8. **One-Time Claim Delivery:**
   - Sensor's next poll presents `claim_token` and `device_uuid`.
   - Server validates claim token hash, returns `agent_key`, and **immediately nullifies** `pending_raw_key` and clears `claim_token_hash`.
   - Sensor saves the credential into `C:\ProgramData\CloudOpsIntel\Sensor\sensor_config.json` with restricted NTFS permissions.
   - Sensor transitions into active telemetry collection.

---

## 3. Workstation Lifecycle States

```
                +---------------------+
                |       PENDING       |  (Ingestion Blocked - HTTP 403)
                +---------------------+
                   |               |
         Super Admin Approve   Super Admin Reject
                   |               |
                   v               v
            +------------+   +------------+
            |  APPROVED  |   |  REJECTED  |  (Terminal State)
            +------------+   +------------+
               |      ^
      Disable  |      |  Re-enable
               v      |
            +------------+
            |  DISABLED  |  (Ingestion Suspended - HTTP 403)
            +------------+
                   |
             Super Admin Retire
                   |
                   v
            +------------+
            |  RETIRED   |  (Key Revoked Permanently - HTTP 403)
            +------------+
```

### 3.1 Disable Workstation
- Super Admin triggers **Disable** in the Web UI.
- Backend sets `device.status = "DISABLED"` and flags the associated `AgentApiKey` as `is_disabled = True`.
- Ingestion is blocked immediately at the API security layer (`HTTP 403 Forbidden`).
- Historical data, alert records, and device mapping are preserved.
- The sensor continues buffering metrics locally in its SQLite queue without data loss.

### 3.2 Re-Enable Workstation
- Super Admin triggers **Re-enable** in the Web UI.
- Backend clears `is_disabled` on the API key and restores device status to `APPROVED`.
- Sensor immediately resumes accepted telemetry dispatch and flushes its local queue backlog.

### 3.3 Decommission / Retire Workstation
- Super Admin triggers **Retire** in the Web UI.
- Backend permanently sets `key.is_active = False` and records `key.revoked_at`.
- Device status becomes `RETIRED`.
- Telemetry ingestion from this key is permanently rejected.
- To return a retired PC to service, it must undergo a fresh enrollment and approval workflow.

---

## 4. Uninstallation Protocol & Offline Retirement

When an administrator runs `uninstall_sensor_client.ps1`:
1. The uninstaller terminates the Windows Scheduled Task and agent processes.
2. If network connectivity to the server exists:
   - The agent sends `POST /api/v1/devices/uninstall-notice` with its `device_uuid` and key.
   - Server marks `retirement_requested = True` in the database and records an audit log.
   - Uninstaller reports: `[+] Remote retirement notice confirmed by server.`
3. If network connectivity is offline / server unreachable:
   - The uninstaller completes local file and service removal safely.
   - The uninstaller issues a **prominent security warning**:
     ```
     ==========================================================================
     [!] WARNING: REMOTE REVOCATION NOT CONFIRMED!
         The CloudOps Intel server could not be reached to confirm credential
         revocation at this time.
         Super Admin MUST confirm device retirement in the CloudOps Intel Web UI
         (Device Management) to permanently revoke this device credential.
     ==========================================================================
     ```
   - In the dashboard, the device displays a `Retirement Requested` badge, allowing the Super Admin to complete authoritative revocation server-side.
