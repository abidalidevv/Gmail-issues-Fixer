"""
VORTEX SUITE — 4G Mobile Dongle & Rotating Proxy Integration Engine
Supports:
1. Huawei HiLink 4G Dongles/Wingles (E8372, E3372, E5573, B310, etc. at 192.168.8.1)
2. ZTE 4G Modems/Wingles (MF79U, MF833V, MF920 at 192.168.0.1)
3. Custom Rotating Mobile Proxy Webhook URLs (iProxy.online, MobileProxy, etc.)
4. HTTP/SOCKS5 Dynamic Proxy Routing for Playwright and ixBrowser
5. Public IP verification & carrier detection
"""
import time
import json
import os
import re
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Tuple
import requests

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

def load_proxy_config() -> Dict[str, Any]:
    default_cfg = {
        "enabled": False,
        "mode": "PHONE_ADB",  # PHONE_ADB, HUAWEI_DONGLE, ZTE_DONGLE, ROTATING_WEBHOOK, DIRECT_PROXY
        "dongle_gateway": "http://192.168.8.1",
        "rotate_webhook_url": "",
        "proxy_server": "",
        "rotate_every_n_accounts": 3
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d.get("proxy_settings", default_cfg)
        except Exception:
            pass
    return default_cfg

def save_proxy_config(proxy_cfg: Dict[str, Any]) -> bool:
    try:
        cfg = {}
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["proxy_settings"] = proxy_cfg
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving proxy config: {e}")
        return False

_http_session = requests.Session()
_ip_cache = {
    "ip": "Unknown",
    "timestamp": 0.0
}

def get_public_ip(force: bool = False) -> str:
    """Query current public IP directly with 6-second in-memory TTL to avoid blocking latency."""
    now = time.time()
    if not force and _ip_cache["ip"] != "Unknown" and (now - _ip_cache["timestamp"]) < 6.0:
        return _ip_cache["ip"]

    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com"
    ]
    for url in services:
        try:
            r = _http_session.get(url, timeout=3)
            if r.status_code == 200 and len(r.text.strip()) <= 45 and "." in r.text:
                resolved = r.text.strip()
                _ip_cache["ip"] = resolved
                _ip_cache["timestamp"] = now
                return resolved
        except Exception:
            continue
    return _ip_cache["ip"] if _ip_cache["ip"] != "Unknown" else "Unknown"

# ─────────────────────────────────────────────────────────────────────────────
# 1. Huawei HiLink 4G Dongle/Wingle API (192.168.8.1)
# ─────────────────────────────────────────────────────────────────────────────
class HuaweiDongle:
    def __init__(self, gateway: str = "http://192.168.8.1"):
        self.gateway = gateway.rstrip("/")
        self.session = requests.Session()

    def get_token(self) -> Tuple[Optional[str], Optional[str]]:
        """Fetch HiLink session token and cookie."""
        try:
            r = self.session.get(f"{self.gateway}/api/webserver/SesTokInfo", timeout=3)
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                tok = root.findtext("TokInfo")
                ses = root.findtext("SesInfo")
                return tok, ses
        except Exception:
            pass
        return None, None

    def check_status(self) -> Dict[str, Any]:
        """Check connection state, carrier, and signal level."""
        try:
            r = self.session.get(f"{self.gateway}/api/monitoring/status", timeout=3)
            if r.status_code == 200:
                root = ET.fromstring(r.text)
                conn_status = root.findtext("ConnectionStatus")
                signal = root.findtext("SignalIcon")
                network_type = root.findtext("CurrentNetworkType")
                return {
                    "online": conn_status in ("901", "902", "903"),
                    "connection_status": conn_status,
                    "signal_bars": signal or "4",
                    "network_type": network_type or "LTE/4G"
                }
        except Exception as e:
            return {"online": False, "error": str(e)}
        return {"online": False}

    def rotate_ip(self) -> Dict[str, Any]:
        """Toggle mobile data on Huawei dongle to trigger fresh carrier IP lease."""
        tok, ses = self.get_token()
        headers = {
            "__RequestVerificationToken": tok or "",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        }
        if ses:
            self.session.cookies.set("SessionID", ses)

        # 1. Turn Mobile Data OFF
        xml_off = '<?xml version="1.0" encoding="UTF-8"?><request><dataswitch>0</dataswitch></request>'
        try:
            self.session.post(f"{self.gateway}/api/dialup/mobile-dataswitch", data=xml_off, headers=headers, timeout=5)
        except Exception as e:
            return {"status": "ERROR", "message": f"Huawei data switch off error: {e}"}

        time.sleep(2)

        # Refresh token for second call
        tok2, _ = self.get_token()
        if tok2:
            headers["__RequestVerificationToken"] = tok2

        # 2. Turn Mobile Data ON
        xml_on = '<?xml version="1.0" encoding="UTF-8"?><request><dataswitch>1</dataswitch></request>'
        try:
            self.session.post(f"{self.gateway}/api/dialup/mobile-dataswitch", data=xml_on, headers=headers, timeout=5)
        except Exception as e:
            return {"status": "ERROR", "message": f"Huawei data switch on error: {e}"}

        # Wait for carrier reconnection (up to 10s)
        time.sleep(4)
        new_ip = get_public_ip(force=True)
        return {"status": "SUCCESS", "new_ip": new_ip, "timestamp": time.strftime("%H:%M:%S"), "source": "Huawei 4G Dongle"}

# ─────────────────────────────────────────────────────────────────────────────
# 2. ZTE 4G Modem / Wingle API (192.168.0.1)
# ─────────────────────────────────────────────────────────────────────────────
class ZTEDongle:
    def __init__(self, gateway: str = "http://192.168.0.1"):
        self.gateway = gateway.rstrip("/")
        self.session = requests.Session()

    def check_status(self) -> Dict[str, Any]:
        try:
            r = self.session.get(f"{self.gateway}/goform/goform_get_cmd_process?cmd=modem_main_state,network_type", timeout=3)
            if r.status_code == 200:
                data = r.json()
                return {"online": True, "state": data.get("modem_main_state")}
        except Exception as e:
            return {"online": False, "error": str(e)}
        return {"online": False}

    def rotate_ip(self) -> Dict[str, Any]:
        """Disconnect and reconnect ZTE cellular connection."""
        headers = {"Referer": f"{self.gateway}/index.html"}
        try:
            # Disconnect
            self.session.post(
                f"{self.gateway}/goform/goform_set_cmd_process",
                data={"isTest": "false", "goformId": "DISCONNECT_NETWORK"},
                headers=headers,
                timeout=5
            )
            time.sleep(2)
            # Connect
            self.session.post(
                f"{self.gateway}/goform/goform_set_cmd_process",
                data={"isTest": "false", "goformId": "CONNECT_NETWORK"},
                headers=headers,
                timeout=5
            )
            time.sleep(4)
            new_ip = get_public_ip(force=True)
            return {"status": "SUCCESS", "new_ip": new_ip, "timestamp": time.strftime("%H:%M:%S"), "source": "ZTE 4G Dongle"}
        except Exception as e:
            return {"status": "ERROR", "message": f"ZTE rotate error: {e}"}

# ─────────────────────────────────────────────────────────────────────────────
# 3. Rotating Webhook URL (Commercial 4G Mobile Proxies)
# ─────────────────────────────────────────────────────────────────────────────
def rotate_via_webhook(webhook_url: str) -> Dict[str, Any]:
    """Trigger rotation endpoint on commercial rotating mobile proxy services."""
    if not webhook_url:
        return {"status": "ERROR", "message": "No webhook URL configured"}

    try:
        r = requests.get(webhook_url, timeout=12)
        time.sleep(3)  # Allow carrier lease to renew
        new_ip = get_public_ip(force=True)
        return {
            "status": "SUCCESS",
            "new_ip": new_ip,
            "response": r.text[:100],
            "timestamp": time.strftime("%H:%M:%S"),
            "source": "Rotating Proxy Webhook"
        }
    except Exception as e:
        return {"status": "ERROR", "message": f"Webhook error: {e}"}

# ─────────────────────────────────────────────────────────────────────────────
# 4. Universal IP Rotator Router
# ─────────────────────────────────────────────────────────────────────────────
def rotate_ip_universal(device_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Intelligently routes IP rotation request based on config:
    1. If Huawei Dongle enabled -> rotate via HiLink API
    2. If ZTE Dongle enabled -> rotate via ZTE API
    3. If Webhook enabled -> rotate via Webhook
    4. Default -> rotate via Android Phone cellular data toggle / airplane mode
    """
    cfg = load_proxy_config()
    mode = cfg.get("mode", "PHONE_ADB")

    if cfg.get("enabled"):
        if mode == "HUAWEI_DONGLE":
            gw = cfg.get("dongle_gateway", "http://192.168.8.1")
            d = HuaweiDongle(gw)
            return d.rotate_ip()

        elif mode == "ZTE_DONGLE":
            gw = cfg.get("dongle_gateway", "http://192.168.0.1")
            z = ZTEDongle(gw)
            return z.rotate_ip()

        elif mode == "ROTATING_WEBHOOK":
            url = cfg.get("rotate_webhook_url", "")
            return rotate_via_webhook(url)

    # Fallback to physical Android Phone via ADB
    from core import device
    return device.rotate_carrier_ip(device_id=device_id)

def check_all_proxy_sources() -> Dict[str, Any]:
    """Audit status of all proxy & dongle sources for diagnostics and UI."""
    cfg = load_proxy_config()
    current_ip = get_public_ip()

    huawei = HuaweiDongle(cfg.get("dongle_gateway", "http://192.168.8.1")).check_status()
    zte = ZTEDongle("http://192.168.0.1").check_status()

    return {
        "config": cfg,
        "current_public_ip": current_ip,
        "huawei_dongle": huawei,
        "zte_dongle": zte,
        "timestamp": time.strftime("%H:%M:%S")
    }

