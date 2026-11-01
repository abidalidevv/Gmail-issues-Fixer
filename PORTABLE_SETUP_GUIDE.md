# 🚀 VORTEX SUITE — Portable PC / Laptop Setup Guide

> [!TIP]
> **Permanent Safe Location:** This project is permanently preserved at **`D:\Projects\gmail issue fix`**. Because Drive D: is an independent drive, all accounts, SQLite vault, session files, and code remain 100% intact even after a Windows reinstallation!

Follow these simple steps whenever you copy this folder to any other computer or laptop.

---

### 1. Requirements for New PC / Laptop
* **Operating System:** Windows 10 or Windows 11 (64-bit)
* **Python:** Python 3.10, 3.11, 3.12, 3.13, or 3.14  
  *(Download from [python.org](https://www.python.org/downloads/) — **IMPORTANT:** Tick the checkbox **"Add python.exe to PATH"** during installation).*
* **Hardware (Optional for Phone Mode):** USB cable for OnePlus 9 Pro / Tecno Spark 5 Pro with USB Debugging enabled.
* **ixBrowser (Optional for PC Profiles):** ixBrowser desktop application installed on that machine.

---

### 2. How to Run on a New PC (Only 2 Clicks!)

#### Step 1: Run One-Time Setup
Double-click:  
👉 **`Setup_Environment.bat`**  
*(This will automatically install Playwright, ZXing-CPP, Pillow, Requests, ixBrowser API, and initialize the database. Takes ~30 seconds).*

#### Step 2: Launch the Suite
Double-click:  
👉 **`Launch_Suite.bat`**  
*(This starts the local web server and automatically opens the Cyber-Luxury Dashboard in your default browser at `http://127.0.0.1:8765`).*

---

### 3. File & Folder Structure in Portable Build

| File / Folder | Purpose |
|---|---|
| 🚀 **`Launch_Suite.bat`** | Main launcher. Double-click to start the dashboard anytime. |
| 🩺 **`Diagnostics.bat`** | System health & diagnostic auditor. Checks phone, ixBrowser & DB. |
| 📦 **`Build_Release.bat`** | Compresses clean portable package for transferring to other PCs. |
| ⚙️ **`Setup_Environment.bat`** | One-time setup script for any new laptop/PC. |
| 📸 **`decode_authenticator_qr.py`** | Decodes Google Authenticator bulk export screenshots. |
| 📁 **`qr_images/`** | Drop your 25–30 QR code screenshots here for bulk import. |
| 🌐 **`documentation.html`** | Offline GitBook/Notion style manual with search, troubleshooting & guides. |
| 📱 **`platform-tools/`** | Bundled portable ADB binaries (no Android Studio installation required). |
| 🗄️ **`vault.db`** | Local SQLite encrypted vault holding accounts and live 2FA session states. |
| ⚙️ **`config.json`** | Password waterfall list, recovery emails, appeal templates, and 4G proxy settings. |
| 📡 **`core/proxy_engine.py`** | Huawei HiLink & ZTE 4G Dongle API rotator + Webhook proxy client. |
| ⚡ **`tests/test_performance_audit.py`** | Benchmark suite testing database indexing (20.2x speedup) & TOTP ops. |

---

### 4. Enterprise Capabilities in this Build
* **5x Parallel ixBrowser:** Select `5x Parallel Turbo` in the dashboard to recover up to 5 accounts at the same time.
* **4G Dongle & Proxy Rotation:** Plug your Huawei or ZTE 4G USB dongle and click `📡 4G Proxy & Dongle` to enable automatic carrier IP leases every 3 accounts.
* **20.2x Faster Database:** Functional SQLite indexing on `LOWER(email)` and `status` delivers sub-millisecond query responses across 300+ accounts.

---

### 5. What Stays With the Folder?
Everything! 
- The SQLite database (`vault.db`)
- All accounts and TOTP secret keys
- Configuration (`config.json`)
- Portable ADB tools (`platform-tools/`)

You can zip this entire folder, put it on a USB flash drive or Google Drive, paste it on any laptop, run `Setup_Environment.bat` once, and it will work immediately!
