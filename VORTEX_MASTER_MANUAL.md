# ⚡ VORTEX SUITE — Master Operational Manual (Enterprise Edition v2.0)
> **GitBook / Notion Edition**  
> *Automated Batch Recovery, Session Preservation & Anti-Detection System for 300–400 Inactive Google Accounts*  
> **Target Environment:** Windows 10/11 · ixBrowser (API & Offline Kernel) · Multi-Phone Fleet (OnePlus 9 Pro + Tecno Spark 5 Pro) · Jazz/Zong 4G Mobile Carrier

---

## 📑 Table of Contents
1. [Overview & Enterprise Architecture](#1-overview--enterprise-architecture)
2. [What Data You Need to Provide](#2-what-data-you-need-to-provide)
3. [Quick Start (3-Step Fast Track)](#3-quick-start-3-step-fast-track)
4. [300 Batch Auto-Recovery Engine (Autonomous Mode)](#4-300-batch-auto-recovery-engine-autonomous-mode)
5. [Multi-Phone Round-Robin Fleet (Lane B)](#5-multi-phone-round-robin-fleet-lane-b)
6. [ixBrowser Integration (API & Direct Kernel Offline Mode)](#6-ixbrowser-integration-api--direct-kernel-offline-mode)
7. [Google Authenticator Bulk Import Guide](#7-google-authenticator-bulk-import-guide)
8. [System Health Diagnostics & Troubleshooting](#8-system-health-diagnostics--troubleshooting)
9. [Post-Recovery Safety & Email Warmup Rules](#9-post-recovery-safety--email-warmup-rules)

---

## 1. Overview & Enterprise Architecture

VORTEX v2.0 is an autonomous, dual-lane hardware-in-the-loop (HIL) anti-detect suite designed specifically to bypass Google's **FIDO2 / caBLE QR Code Challenges** on dormant accounts at scale.

```
                            ┌────────────────────────────────────────┐
                            │    VORTEX BATCH ENGINE (300 Queue)     │
                            │      http://127.0.0.1:8765/dashboard   │
                            └───────────────────┬────────────────────┘
                                                │
                        ┌───────────────────────┴───────────────────────┐
                        ▼                                               ▼
           ┌────────────────────────┐                     ┌────────────────────────┐
           │  LANE A: ixBrowser     │                     │  LANE B: Multi-Phone   │
           │  (Anti-Detect Desktop) │                     │  (Physical Hardware)   │
           ├────────────────────────┤                     ├────────────────────────┤
           │ • Playwright CDP       │                     │ • UIAutomator2 Engine  │
           │ • API + Direct Kernel  │                     │ • Round-Robin Dispatch │
           │ • Password Waterfall   │                     │ • 4G Cellular IP Reset │
           │ • Live TOTP Injector   │                     │ • GMS Cache Purge      │
           │ • Local Storage State  │                     │ • Zero caBLE Challenge │
           │ • 9 Local Disk Profiles│                     │ • OnePlus & Tecno Fleet│
           └────────────────────────┘                     └────────────────────────┘
```

---

## 2. What Data You Need to Provide

| Asset | Format | Location | Purpose |
|---|---|---|---|
| **Google Authenticator QR** | Screenshots or Live Screen | `qr_images/` or direct via ADB | Decodes 300 Base32 TOTP secret keys into `vault.db`. |
| **Waterfall Passwords** | 2 to 3 candidate passwords | `config.json` | 80% / 15% / 5% password waterfall attempts. |
| **Recovery Emails** | Email addresses | `config.json` | Used when Google prompts for secondary verification. |
| **Appeal Message** | Text & contact email | `config.json` | Auto-appeal for dormant accounts flagged as disabled. |
| **Active 4G SIM Cards** | Physical SIMs in phones | Active in connected phones | Dynamic cellular IP assignment via carrier toggle. |

---

## 3. Quick Start (3-Step Fast Track)

```mermaid
graph LR
    A[Step 1: Authenticator QR] --> B[Step 2: Run Decoder]
    B --> C[Step 3: Launch Suite]
    C --> D[Step 4: ▶ Start Batch Auto]
```

### Step 1: Decode Authenticator Codes
Run in your project directory:
```powershell
python decode_authenticator_qr.py
```
> **Tip:** If your phone is plugged in with USB debugging, the decoder can auto-capture the QR code directly from the phone screen!

### Step 2: System Health Audit
Double-click:
🚀 **`Diagnostics.bat`**  
Verifies Python, ADB, connected phones, ixBrowser profiles, SQLite database, and TOTP generation.

### Step 3: Launch Web Dashboard
Double-click:
🚀 **`Launch_Suite.bat`**  
Opens the web dashboard automatically at **`http://127.0.0.1:8765`**.

---

## 4. 300 Batch Auto-Recovery Engine (Autonomous Mode)

No more clicking individual buttons for 300 accounts. The Batch Engine handles the entire queue automatically:

1. Click **`▶ Start Batch Auto`** at the top of the dashboard.
2. The engine loads all pending accounts from `vault.db`.
3. **Smart Routing:**
   - Accounts with ixBrowser profiles are routed to **Lane A (Playwright CDP)**.
   - Other accounts are routed to **Lane B (Android Hardware Fleet)**.
4. **Rate-Limiting Protection:**
   - 8–15 second randomized jitter delay between accounts to evade Google Socrates bot-detection.
   - Periodic 4G IP rotation every 3 accounts.
   - Controls available at any moment: **Pause (⏸)**, **Resume (▶)**, and **Stop (⏹)**.

---

## 5. Multi-Phone Round-Robin Fleet (Lane B)

Instead of relying on slow screen capture, Lane B uses **UIAutomator2 element automation**:
- Direct resource ID targeting (`identifierId`, `password`, `totpPin`).
- Average recovery time per account: **40–50 seconds** (vs 3–5 minutes manually).
- **Fleet Balancing:** If both your **OnePlus 9 Pro** and **Tecno Spark 5 Pro** are connected, the engine alternates accounts between them (Account 1 on Phone A, Account 2 on Phone B).
- **Safety Quota:** Maximum 15 accounts per phone per 24 hours to prevent hardware attestation rate-limits.

---

## 6. ixBrowser Integration (API & Direct Kernel Offline Mode)

VORTEX v2.0 supports two modes for ixBrowser:

1. **Local API v2 Mode (Port 53200):**  
   Active when ixBrowser client is running with Local API enabled.
2. **Direct Kernel Offline Mode:**  
   If ixBrowser client is closed, VORTEX auto-detects profiles on disk (`%APPDATA%/ixBrowser/Browser Data`) and launches ixBrowser's custom Chromium binary directly (`ixBrowser-Resources\chrome\151-0005\chrome.exe`) with a remote debugging port.
3. **Session Persistence Backup:**  
   Every successful login dumps an encrypted session backup into `vault_sessions/<email>.json`.

---

## 7. Google Authenticator Bulk Import Guide

* Google Authenticator compresses **10 to 12 accounts per QR code**.
* 300 accounts require only **25 to 30 QR codes**.
* You can either:
  - Place screenshot images in `qr_images/` and run `python decode_authenticator_qr.py`.
  - Or open Authenticator on your connected phone and run `python decode_authenticator_qr.py` to auto-capture directly from the screen!

---

## 8. System Health Diagnostics & Troubleshooting

| Check / Issue | Cause | Fix |
|---|---|---|
| **`No USB Android phone connected`** | Cable disconnected or USB debugging OFF | Re-plug cable, enable Developer Options > USB Debugging. |
| **`ixBrowser Local API Offline`** | ixBrowser application not running | Open ixBrowser. (Direct kernel mode will still function for local disk profiles). |
| **`WRONG_PASSWORD` on batch** | Password candidate rejected | Update `passwords_waterfall` in `config.json`. |
| **`NEEDS_SMS` status** | Account requires physical SIM SMS code | Check SMS on phone with the registered SIM card. |

---

## 9. Post-Recovery Safety & Email Warmup Rules

> [!WARNING]
> **48-Hour Cooldown Rule:** Do not connect newly recovered accounts to email warmup tools (Smartlead / Instantly) immediately. Wait 48 hours to allow the security session to settle.

Export warmup CSV at any time by clicking **`⬇ Export for Warmup`** in the dashboard.
