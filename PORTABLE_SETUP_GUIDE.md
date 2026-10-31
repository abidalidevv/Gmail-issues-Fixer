# 🚀 VORTEX SUITE — Portable PC / Laptop Setup Guide

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
| ⚙️ **`config.json`** | Password waterfall list, recovery emails, and appeal templates. |

---

### 4. What Stays With the Folder?
Everything! 
- The SQLite database (`vault.db`)
- All accounts and TOTP secret keys
- Configuration (`config.json`)
- Portable ADB tools (`platform-tools/`)

You can zip this entire folder, put it on a USB flash drive or Google Drive, paste it on any laptop, run `Setup_Environment.bat` once, and it will work immediately!
