import os
import sys
import subprocess
import shutil
import time
import base64
from typing import Optional, Dict, Any, List

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_adb_path() -> str:
    """Find system or portable adb.exe."""
    local_adb = os.path.join(SCRIPT_DIR, "platform-tools", "adb.exe")
    if os.path.exists(local_adb):
        return local_adb
    if shutil.which("adb"):
        return "adb"
    return local_adb

ADB_BIN = get_adb_path()

def run_adb_cmd(cmd: List[str], timeout: int = 15, device_id: Optional[str] = None) -> str:
    """Execute raw ADB command with optional specific device target."""
    if device_id:
        full = [ADB_BIN, "-s", device_id] + cmd
    else:
        full = [ADB_BIN] + cmd

    try:
        res = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
        if res.returncode != 0:
            err = res.stderr.strip() or res.stdout.strip()
            return f"ERROR: {err}" if err else f"ERROR: ADB returned code {res.returncode}"
        return res.stdout.strip()
    except subprocess.TimeoutExpired:
        return "ERROR: ADB command timed out"
    except Exception as e:
        return f"ERROR: {e}"

_device_cache = {
    "timestamp": 0.0,
    "devices": []
}

def get_all_connected_devices() -> List[Dict[str, Any]]:
    """Return telemetry for ALL connected Android phones with 6s TTL cache to eliminate USB polling lag."""
    now = time.time()
    devices_out = run_adb_cmd(["devices"])
    if "ERROR" in devices_out:
        return []

    lines = [line.strip() for line in devices_out.splitlines() if line.strip()]
    current_serials = sorted([line.split("\t")[0] for line in lines[1:] if "\tdevice" in line])

    cached_serials = sorted([d["id"] for d in _device_cache.get("devices", [])])
    if current_serials == cached_serials and (now - _device_cache.get("timestamp", 0.0)) < 6.0:
        return _device_cache["devices"]

    devs = []
    for dev_id in current_serials:
        batch_cmd = (
            "echo MODEL:$(getprop ro.product.model);"
            "echo BRAND:$(getprop ro.product.brand);"
            "echo ANDROID:$(getprop ro.build.version.release);"
            "echo SIM:$(getprop gsm.sim.operator.alpha);"
            "dumpsys battery | grep level:"
        )
        output = run_adb_cmd(["shell", batch_cmd], timeout=8, device_id=dev_id)

        model = brand = android_ver = sim_operator = "Unknown"
        battery_level = "--"

        for bline in output.splitlines():
            bline = bline.strip()
            if bline.startswith("MODEL:"):
                model = bline[6:].strip() or "Unknown"
            elif bline.startswith("BRAND:"):
                brand = bline[6:].strip() or "Unknown"
            elif bline.startswith("ANDROID:"):
                android_ver = bline[8:].strip() or "Unknown"
            elif bline.startswith("SIM:"):
                sim_operator = bline[4:].strip() or ""
            elif "level:" in bline:
                try:
                    battery_level = bline.split(":")[1].strip() + "%"
                except Exception:
                    pass

        devs.append({
            "id": dev_id,
            "name": f"{brand.capitalize()} {model}",
            "model": model,
            "brand": brand,
            "android": f"Android {android_ver}",
            "carrier": sim_operator or "Sim Active (4G/LTE)",
            "battery": battery_level,
            "status": "ONLINE"
        })

    _device_cache["timestamp"] = now
    _device_cache["devices"] = devs
    return devs

def get_connected_device() -> Optional[Dict[str, Any]]:
    """Detect first connected phone for backward compatibility."""
    devs = get_all_connected_devices()
    return devs[0] if devs else None

def capture_screenshot(device_id: Optional[str] = None) -> Optional[bytes]:
    """Capture real-time phone screen as PNG bytes."""
    if device_id:
        full = [ADB_BIN, "-s", device_id, "exec-out", "screencap", "-p"]
    else:
        full = [ADB_BIN, "exec-out", "screencap", "-p"]

    try:
        proc = subprocess.run(full, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
        if proc.returncode == 0 and len(proc.stdout) > 1000:
            return proc.stdout
    except Exception:
        pass
    return None

def get_phone_public_ip(device_id: Optional[str] = None) -> str:
    """Query real public IP directly from the Android phone."""
    res = run_adb_cmd(["shell", "curl", "-s", "--max-time", "6", "https://api.ipify.org"], device_id=device_id)
    if res and "ERROR" not in res and len(res.strip()) <= 45 and "." in res:
        return res.strip()
    res2 = run_adb_cmd(["shell", "curl", "-s", "--max-time", "6", "https://ifconfig.me/ip"], device_id=device_id)
    if res2 and "ERROR" not in res2 and len(res2.strip()) <= 45 and "." in res2:
        return res2.strip()
    return "Unknown (Check 4G Data)"

def rotate_carrier_ip(device_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Modern 4G IP rotation:
    1. Force kill Wi-Fi so traffic never leaks over home broadband
    2. Toggle cellular mobile data (svc data disable -> svc data enable)
    3. Fallback to airplane mode toggle if needed
    4. Dynamically poll for carrier reconnection
    """
    # Force disable WiFi first
    run_adb_cmd(["shell", "svc", "wifi", "disable"], timeout=5, device_id=device_id)

    # Fast cellular toggle
    r_data = run_adb_cmd(["shell", "svc", "data", "disable"], timeout=5, device_id=device_id)
    time.sleep(1.5)
    run_adb_cmd(["shell", "svc", "data", "enable"], timeout=5, device_id=device_id)

    # If svc data had error, fall back to airplane mode
    if "ERROR" in str(r_data):
        run_adb_cmd(["shell", "cmd", "connectivity", "airplane-mode", "enable"], device_id=device_id)
        time.sleep(3)
        run_adb_cmd(["shell", "cmd", "connectivity", "airplane-mode", "disable"], device_id=device_id)

    # Dynamic poll for reconnection (up to 12s)
    for _ in range(12):
        time.sleep(1)
        net_info = run_adb_cmd(["shell", "dumpsys", "connectivity"], timeout=5, device_id=device_id)
        if "CONNECTED" in net_info and ("MOBILE" in net_info or "mobile" in net_info.lower()):
            break

    time.sleep(1.5)
    new_ip = get_phone_public_ip(device_id)
    return {"status": "SUCCESS", "new_ip": new_ip, "timestamp": time.strftime("%H:%M:%S")}

def purge_gms_quota(device_id: Optional[str] = None) -> Dict[str, Any]:
    """Purge Play Services and GSF SQLite rate-limit databases."""
    r1 = run_adb_cmd(["shell", "pm", "clear", "com.google.android.gms"], device_id=device_id)
    r2 = run_adb_cmd(["shell", "pm", "clear", "com.google.android.gsf"], device_id=device_id)
    if "ERROR" in str(r1) or "ERROR" in str(r2):
        return {"status": "ERROR", "message": f"GMS clear: {r1} | {r2}"}
    return {"status": "SUCCESS", "message": "Play Services rate-limit reset to 0"}

def launch_native_add_account(device_id: Optional[str] = None) -> str:
    """Launch native Android Add-Account activity (No-QR Flow)."""
    return run_adb_cmd(["shell", "am", "start", "-a", "android.settings.ADD_ACCOUNT_SETTINGS"], device_id=device_id)

def inject_text(text: str, device_id: Optional[str] = None) -> str:
    """Safely inject text into focused Android field via ADB without shell interpolation."""
    if not text:
        return ""

    special_chars = set('@#$&!|;`"\\<>{}()[]^~%')
    needs_charbychar = any(c in special_chars for c in text)

    if needs_charbychar:
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        cmd = f"echo {b64} | base64 -d | clip"
        result = run_adb_cmd(["shell", cmd], device_id=device_id)

        if "ERROR" in str(result):
            safe = text.replace("\\", "\\\\").replace("'", "\\'").replace(" ", "%s").replace("@", "\\@")
            return run_adb_cmd(["shell", f"input text '{safe}'"], device_id=device_id)
        else:
            return run_adb_cmd(["shell", "input", "keyevent", "279"], device_id=device_id)
    else:
        safe_text = text.replace("'", "\\'").replace(" ", "%s")
        return run_adb_cmd(["shell", f"input text '{safe_text}'"], device_id=device_id)

def inject_key(keycode: int = 66, device_id: Optional[str] = None):
    """Press Android key (66 = ENTER, 4 = BACK, 3 = HOME)."""
    return run_adb_cmd(["shell", "input", "keyevent", str(keycode)], device_id=device_id)

def inject_tap(x: int, y: int, device_id: Optional[str] = None):
    """Tap coordinates on mobile screen."""
    return run_adb_cmd(["shell", "input", "tap", str(x), str(y)], device_id=device_id)
