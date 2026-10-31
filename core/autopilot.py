import threading
import time
from typing import Dict, Any, List
from core import device, totp, database

# FIX BUG-04: Thread-safe lock for STATE dictionary
_state_lock = threading.Lock()

STATE: Dict[str, Any] = {
    "running": False,
    "current_email": None,
    "step": "IDLE",  # IDLE, ROTATING_IP, CLEARING_GMS, LAUNCHING_LOGIN, TYPING_EMAIL, TYPING_PASSWORD, TYPING_2FA, WAITING_USER, DONE
    "logs": []
}

def log(msg: str, level: str = "INFO"):
    """Thread-safe logging to STATE."""
    t_str = time.strftime("%H:%M:%S")
    entry = {"time": t_str, "msg": msg, "level": level}
    # FIX BUG-04: Acquire lock before modifying shared STATE
    with _state_lock:
        STATE["logs"].append(entry)
        if len(STATE["logs"]) > 200:
            STATE["logs"].pop(0)
    print(f"[{t_str}] [{level}] {msg}")

def get_state() -> Dict[str, Any]:
    """Thread-safe state read."""
    with _state_lock:
        return {
            "running": STATE["running"],
            "current_email": STATE["current_email"],
            "step": STATE["step"],
            "logs": list(STATE["logs"][-30:])  # Copy last 30 logs for UI
        }

def _set_state(**kwargs):
    """Thread-safe state update."""
    with _state_lock:
        STATE.update(kwargs)

def run_single_step(action: str, email: str, extra: str = ""):
    """Execute interactive recovery action triggered from web dashboard."""
    if action == "rotate_ip":
        log("Triggering 4G Mobile IP rotation (Airplane mode toggle)...", "WARN")
        log("NOTE: IP rotation only works on 4G mobile data, not WiFi!", "WARN")
        # FIX BUG-11: Run in background thread so server doesn't block for 8s
        def _rotate():
            res = device.rotate_carrier_ip()
            log(f"New Public IP Assigned: {res.get('new_ip', 'Unknown')}", "SUCCESS")
        threading.Thread(target=_rotate, daemon=True).start()
        return {"status": "ROTATING", "message": "IP rotation started in background (takes ~8s)"}

    elif action == "clear_gms":
        log("Purging Play Services rate-limit databases...", "WARN")
        res = device.purge_gms_quota()
        log("Local device quota reset to 0.", "SUCCESS")
        return res

    elif action == "launch_native":
        log("Launching Android native Add-Account screen (No-QR Flow)...", "INFO")
        result = device.launch_native_add_account()
        if result and "ERROR" in str(result):
            log(f"Failed to launch native screen: {result}", "ERROR")
            return {"status": "ERROR", "message": result}
        log("Native screen open. Please tap 'Google' on phone.", "INFO")
        return {"status": "SUCCESS"}

    elif action == "type_email":
        log(f"Auto-injecting email: {email}", "INFO")
        result = device.inject_text(email)
        if result and "ERROR" in str(result):
            log(f"inject_text error: {result}", "ERROR")
            return {"status": "ERROR", "message": result}
        time.sleep(0.5)
        device.inject_key(66)  # Next/Enter
        log("Email submitted. Loading password field...", "SUCCESS")
        return {"status": "SUCCESS"}

    elif action == "type_password":
        log(f"Auto-injecting password for {email}...", "INFO")
        # FIX BUG-03: inject_text now handles special chars properly
        result = device.inject_text(extra)  # extra is password
        if result and "ERROR" in str(result):
            log(f"inject_text error: {result}", "ERROR")
            return {"status": "ERROR", "message": result}
        time.sleep(0.5)
        device.inject_key(66)  # Next/Enter
        log("Password submitted. Loading verification step...", "SUCCESS")
        return {"status": "SUCCESS"}

    elif action == "type_totp":
        if not extra:
            log("ERROR: No TOTP secret provided!", "ERROR")
            return {"status": "ERROR", "error": "TOTP secret required"}
        code, remaining = totp.generate_totp(extra)  # extra is totp secret
        if remaining < 5:
            log(f"TOTP expiring in {remaining}s — waiting {remaining + 1}s for fresh window...", "WARN")
            time.sleep(remaining + 1)
            code, remaining = totp.generate_totp(extra)
        log(f"Generated Live TOTP: {code} (Valid for {remaining}s). Injecting...", "SUCCESS")
        result = device.inject_text(code)
        if result and "ERROR" in str(result):
            log(f"inject_text error: {result}", "ERROR")
            return {"status": "ERROR", "message": result}
        time.sleep(0.5)
        device.inject_key(66)  # Next/Enter
        log("2FA code injected. Verify login on phone screen.", "SUCCESS")
        # NOTE: We do NOT mark as RECOVERED here — user must confirm via phone
        return {"status": "SUCCESS", "code": code, "note": "Verify on phone screen before marking recovered"}

    elif action == "inject_key":
        try:
            keycode = int(extra) if str(extra).isdigit() else 66
        except Exception:
            keycode = 66
        device.inject_key(keycode)
        log(f"Injected KeyCode: {keycode}", "INFO")
        return {"status": "SUCCESS", "keycode": keycode}

    elif action == "inject_tap":
        try:
            parts = str(extra).split(",")
            x, y = int(parts[0].strip()), int(parts[1].strip())
            device.inject_tap(x, y)
            log(f"Tapped coordinates ({x}, {y})", "INFO")
            return {"status": "SUCCESS"}
        except Exception as e:
            log(f"inject_tap error: {e}", "ERROR")
            return {"status": "ERROR", "error": str(e)}

    log(f"Unknown action received: {action}", "WARN")
    return {"status": "UNKNOWN_ACTION"}
