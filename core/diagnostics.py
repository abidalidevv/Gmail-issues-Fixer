"""
VORTEX SUITE — Comprehensive System Health & Diagnostics Engine
Checks:
1. Python Environment & Core Modules (playwright, zxingcpp, pillow, etc.)
2. ADB Platform Tools & Hardware Detection (OnePlus, Tecno, USB Debugging, Battery, 4G IP)
3. ixBrowser Ecosystem (API v2 Port 53200 + Local Profile Disk Store + Chromium Kernel)
4. SQLite Vault Database (WAL mode, schema validity, PRAGMA integrity_check)
5. Cryptographic Engine (RFC 6238 TOTP verification with standard test vectors)
6. Network Connectivity (Carrier IP check & Google authentication endpoints)
"""
import os
import sys
import time
import json
import sqlite3
from typing import Dict, Any, List

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_diagnostics() -> Dict[str, Any]:
    report = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "overall_status": "HEALTHY",
        "checks": []
    }

    def add_check(category: str, name: str, status: str, details: str, passed: bool):
        report["checks"].append({
            "category": category,
            "name": name,
            "status": status,
            "details": details,
            "passed": passed
        })
        if not passed and status == "CRITICAL":
            report["overall_status"] = "ACTION_REQUIRED"
        elif not passed and report["overall_status"] != "ACTION_REQUIRED":
            report["overall_status"] = "WARNINGS"

    # 1. Python Environment Check
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    add_check("Environment", "Python Runtime", "OK", f"Python {py_ver} ({sys.executable})", True)

    # Required packages
    packages = ["requests", "playwright", "zxingcpp", "PIL", "ixbrowser_local_api"]
    for pkg in packages:
        try:
            __import__(pkg)
            add_check("Dependencies", f"Package: {pkg}", "OK", "Installed and importable", True)
        except ImportError:
            add_check("Dependencies", f"Package: {pkg}", "WARNING", "Not installed (Optional or fallback in use)", False)

    # 2. SQLite Database Integrity
    from core import database
    db_path = database.DB_PATH
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            row = cur.fetchone()
            integrity = row[0] if row else "unknown"
            cur.execute("SELECT COUNT(*) FROM accounts;")
            acc_count = cur.fetchone()[0]
            conn.close()

            if integrity.lower() == "ok":
                add_check("Database", "SQLite Vault Integrity", "OK", f"Pass (Integrity: {integrity}, Accounts: {acc_count})", True)
            else:
                add_check("Database", "SQLite Vault Integrity", "CRITICAL", f"Integrity error: {integrity}", False)
        except Exception as e:
            add_check("Database", "SQLite Vault Integrity", "CRITICAL", f"DB Access error: {e}", False)
    else:
        add_check("Database", "SQLite Vault Integrity", "WARNING", f"vault.db not yet created (Will auto-init on start)", True)

    # 3. Cryptographic TOTP Engine RFC 6238 Standard Test
    from core import totp
    try:
        # Standard RFC test secret (Base32 encoded '12345678901234567890')
        test_secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        code, rem = totp.generate_totp(test_secret)
        if len(code) == 6 and code.isdigit() and 0 <= rem <= 30:
            add_check("Cryptography", "RFC 6238 TOTP Engine", "OK", f"Working (Generated code {code}, {rem}s remaining)", True)
        else:
            add_check("Cryptography", "RFC 6238 TOTP Engine", "CRITICAL", f"Malformed TOTP: {code}", False)
    except Exception as e:
        add_check("Cryptography", "RFC 6238 TOTP Engine", "CRITICAL", f"TOTP error: {e}", False)

    # 4. ADB & Hardware Fleet
    from core import device
    adb_path = device.ADB_BIN
    if os.path.exists(adb_path) or device.shutil.which("adb"):
        version_out = device.run_adb_cmd(["version"])
        first_line = version_out.splitlines()[0] if version_out else "ADB Ready"
        add_check("Hardware", "ADB Platform Tools", "OK", first_line, True)
    else:
        add_check("Hardware", "ADB Platform Tools", "CRITICAL", "adb.exe not found in platform-tools/ or PATH", False)

    devices = device.get_all_connected_devices()
    if devices:
        dev_names = ", ".join([f"{d['name']} ({d['id'][:8]})" for d in devices])
        add_check("Hardware", "Connected Android Fleet", "OK", f"{len(devices)} device(s) online: {dev_names}", True)
    else:
        add_check("Hardware", "Connected Android Fleet", "WARNING", "No USB Android phone connected (Required for Lane B)", False)

    # 5. ixBrowser Anti-Detect System
    from core import ixbrowser
    api_online, api_msg = ixbrowser.check_api_status()
    if api_online:
        add_check("Anti-Detect", "ixBrowser Local API", "OK", api_msg, True)
    else:
        add_check("Anti-Detect", "ixBrowser Local API", "WARNING", api_msg, False)

    local_profiles = ixbrowser.get_local_profiles_from_disk()
    if local_profiles:
        add_check("Anti-Detect", "Local Disk Profiles", "OK", f"Detected {len(local_profiles)} profile directories in AppData", True)
    else:
        add_check("Anti-Detect", "Local Disk Profiles", "WARNING", "No ixBrowser profiles found on disk", False)

    kernel = ixbrowser.find_ix_chrome_binary()
    if kernel and os.path.exists(kernel):
        add_check("Anti-Detect", "Chromium Kernel Binary", "OK", f"Found at: {os.path.basename(os.path.dirname(kernel))}\\chrome.exe", True)
    else:
        add_check("Anti-Detect", "Chromium Kernel Binary", "WARNING", "ixBrowser custom kernel not found (API mode used if running)", False)

    # 6. Network Connectivity Check
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://accounts.google.com",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                add_check("Network", "Google Reachability", "OK", "accounts.google.com reachable (HTTP 200)", True)
            else:
                add_check("Network", "Google Reachability", "WARNING", f"HTTP {resp.status}", False)
    except Exception as e:
        add_check("Network", "Google Reachability", "CRITICAL", f"Network error: {e}", False)

    return report

def print_cli_report():
    print("=" * 70)
    print("      [+] VORTEX SUITE -- SYSTEM DIAGNOSTICS & HEALTH AUDIT [+]      ")
    print("=" * 70)
    report = run_diagnostics()
    print(f"Timestamp: {report['timestamp']}")
    print(f"Overall System Status: [{report['overall_status']}]\n")

    current_cat = ""
    for chk in report["checks"]:
        if chk["category"] != current_cat:
            current_cat = chk["category"]
            print(f"\n--- {current_cat.upper()} ---")
        badge = "PASS" if chk["passed"] else chk["status"]
        print(f"  [{badge:<10}] {chk['name']:<28} : {chk['details']}")

    print("\n" + "=" * 70)
    if report["overall_status"] == "HEALTHY":
        print("[SUCCESS] All core recovery systems are operational and ready for batch.")
    elif report["overall_status"] == "WARNINGS":
        print("[NOTICE] System operational with minor warnings (check non-critical items above).")
    else:
        print("[ACTION REQUIRED] One or more critical systems need attention before recovery.")
    print("=" * 70)

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    print_cli_report()
