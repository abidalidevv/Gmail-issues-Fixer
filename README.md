# ⚡ VORTEX SUITE — Enterprise Google Account Recovery & Identity Orchestrator
> **Autonomous Dual-Lane Anti-Detection Recovery Suite for 300+ Dormant / caBLE QR-Locked Google Accounts**  
> *Engineered for high-volume agency operations, warm-up preparation, and FIDO2 challenge bypass.*

---

## 🌟 Key Highlights & Capabilities

* **🚀 300 Batch Auto-Recovery Engine:** Autonomous queue runner with pause, resume, and rate-limit cooldowns.
* **🌐 Multi-Threaded Parallel ixBrowser (5x Speed):** Simultaneous profile recovery with dynamic CDP debugging port isolation (`9222`, `9227`, `9232`, `9237`, `9242`).
* **📡 4G Mobile Dongle & Rotating Proxy Integration:**
  * **Huawei HiLink 4G Wingles / Modems** (`192.168.8.1` HiLink API - E8372, E3372, E5573, B310).
  * **ZTE 4G Wingles & Modems** (`192.168.0.1` Web API - MF79U, MF833V, MF920).
  * **Rotating Webhook Mobile Proxies** (iProxy.online / MobileProxy URLs).
  * **HTTP / SOCKS5 Dynamic Proxy Injection** into Playwright Chromium kernels.
* **📱 Multi-Phone Hardware Fleet (Lane B):** UIAutomator2 element automation with round-robin load-balancing across multiple connected Android devices (e.g., OnePlus 9 Pro + Tecno Spark 5 Pro).
* **🏎️ Sub-Second Database Engine (SQLite WAL):** Functional case-insensitive indexing (`idx_accounts_email_lower`, `idx_accounts_status`) delivering **92,000+ lookups/sec (20.2x speedup)**.
* **📸 Google Authenticator Bulk Decoder:** Decodes 25–30 exported QR screenshots (or captures live via phone ADB screen) into 300 Base32 secret keys in under 2 seconds.
* **🩺 Integrated System Diagnostics:** Automated health checks for Python, ADB, SQLite WAL integrity, RFC 6238 TOTP compliance, ixBrowser profiles, and Google reachability.

---

## 🏗️ System Architecture

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
            │ • 5x Parallel Workers  │                     │ • Round-Robin Dispatch │
            │ • Dynamic Port Matrix  │                     │ • 4G Cellular IP Reset │
            │ • Resource Intercept   │                     │ • GMS Cache Purge      │
            │ • Offline Kernel Launch│                     │ • Zero caBLE Challenge │
            │ • Session JSON Vault   │                     │ • OnePlus & Tecno Fleet│
            └────────────────────────┘                     └────────────────────────┘
```

---

## ⚡ Empirical Performance Benchmarks

Measured on Windows 11 with 1,000 accounts test vector (`tests/test_performance_audit.py`):

| Subsystem / Metric | Throughput | Latency | Status |
|---|---|---|---|
| **SQLite Case-Insensitive Lookup** | **92,424 ops/sec** | 0.010 ms | ⚡ 20.2x Faster (Indexed) |
| **SQLite Bulk Account Insert** | **202,233 ops/sec** | 0.005 ms | WAL Mode Memory Cache |
| **Dashboard Stats Aggregation** | **9,391 ops/sec** | 0.106 ms | ⚡ 7.8x Faster |
| **RFC 6238 TOTP Generation** | **101,913 codes/sec** | 9.81 µs | Standard Compliant |
| **Concurrent Multi-Worker Writes** | **150.7 updates/sec** | 6.63 ms | 0 Locks / 0 Timeouts |

---

## 🚀 Quick Start Guide

### Step 1: Clone & Setup
```powershell
git clone https://github.com/abidalidevv/Gmail-issues-Fixer.git
cd Gmail-issues-Fixer
```

### Step 2: One-Time Setup
Double-click:
👉 **`Setup_Environment.bat`**  
*(Installs Playwright, Requests, ZXing-CPP, Pillow, ixBrowser API, and initializes SQLite database).*

### Step 3: Run System Diagnostics
Double-click:
👉 **`Diagnostics.bat`**  
*(Verifies Python, connected Android phones, ADB, SQLite database integrity, and TOTP engine).*

### Step 4: Launch Web Dashboard
Double-click:
👉 **`Launch_Suite.bat`**  
*(Automatically opens the dashboard at **`http://127.0.0.1:8765`**).*

---

## ⚙️ Configuration (`config.json`)

```json
{
  "passwords_waterfall": [
    "Abidali@2xx",
    "Abidali@72xx",
    "Abidali2xx"
  ],
  "recovery_emails": [
    "abidmcs99@gmail.com",
    "abidmmp100@gmail.com"
  ],
  "appeal_settings": {
    "contact_email": "abidmcs99@gmail.com",
    "appeal_message": "This account is used for business social media management."
  },
  "proxy_settings": {
    "enabled": true,
    "mode": "HUAWEI_DONGLE",
    "dongle_gateway": "http://192.168.8.1",
    "rotate_webhook_url": "",
    "proxy_server": "",
    "rotate_every_n_accounts": 3
  }
}
```

---

## 📁 Repository Structure

```
Gmail-issues-Fixer/
├── app.py                      # Threading HTTP server & REST API
├── config.json                 # Password waterfall & proxy settings
├── Launch_Suite.bat            # 1-Click main launcher
├── Diagnostics.bat             # 1-Click system health auditor
├── Setup_Environment.bat       # 1-Click environment installer
├── Build_Release.bat           # Portable release package builder
├── decode_authenticator_qr.py  # Google Authenticator bulk export decoder
├── core/
│   ├── autopilot.py            # Orchestrator state & action dispatcher
│   ├── batch_engine.py         # 5x Parallel multi-worker queue engine
│   ├── database.py             # SQLite WAL vault with 20x indexing
│   ├── device.py               # Multi-phone ADB fleet with 6s caching
│   ├── device_u2.py            # UIAutomator2 sub-45s element engine
│   ├── diagnostics.py          # System health check audit module
│   ├── ixbrowser.py            # Playwright CDP direct kernel runner
│   ├── proxy_engine.py         # Huawei HiLink, ZTE & Webhook proxy router
│   └── totp.py                 # Cryptographic RFC 6238 TOTP generator
├── static/
│   ├── index.html              # Cyber-Luxury dashboard UI
│   ├── app.js                  # Frontend async telemetry & batch controller
│   ├── style.css               # Responsive dark styling
│   └── docs.html               # In-browser GitBook documentation
├── tests/
│   ├── test_stress.py          # 8-suite stress & concurrency test
│   └── test_performance_audit.py # Empirical benchmarking suite
└── documentation.html          # Full offline manual (Notion/GitBook style)
```

---

## 🛡️ License & Safety

* **48-Hour Cooldown:** Do not attach newly recovered accounts to email warm-up tools immediately. Allow security cookies to settle for 48 hours.
* **Privacy:** All account credentials and session states remain local inside your private SQLite database (`vault.db`) and are excluded from Git commits via `.gitignore`.

