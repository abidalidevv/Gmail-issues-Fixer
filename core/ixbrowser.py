"""
VORTEX SUITE — ixBrowser Playwright Recovery Engine (Enterprise Edition)
Supports:
1. Official ixBrowser Local API v2 (port 53200)
2. Direct Kernel Offline Launch Mode (executes ixBrowser Chrome directly without API)
3. Local disk profile auto-detection from %APPDATA%/ixBrowser/Browser Data
4. Offline storageState.json cookie persistence (vault_sessions/)
5. Natural human keystroke timing, dynamic challenge bypass, and live TOTP
"""
import asyncio
import glob
import subprocess
import threading
import time
import json
import os
import re
from typing import Dict, Any, List, Optional, Tuple

try:
    from ixbrowser_local_api import IXBrowserClient
except ImportError:
    IXBrowserClient = None

from core import totp, database

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")
SESSIONS_DIR = os.path.join(SCRIPT_DIR, "vault_sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

# Common ixBrowser directories on Windows
IX_ROAMING = os.path.join(os.environ.get("APPDATA", ""), "ixBrowser")
IX_BROWSER_DATA = os.path.join(IX_ROAMING, "Browser Data")
IX_RESOURCES = os.path.join(os.environ.get("APPDATA", ""), "ixBrowser-Resources")

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "passwords_waterfall": ["Abidali@2xx", "Abidali@72xx", "Abidali2xx"],
        "recovery_emails": ["abidmcs99@gmail.com", "abidmmp100@gmail.com"],
        "appeal_settings": {
            "contact_email": "abidmcs99@gmail.com",
            "appeal_message": "This account is used for legitimate business social media management."
        }
    }

def check_api_status() -> Tuple[bool, str]:
    """Test if ixBrowser Local API v2 is active on port 53200."""
    try:
        import requests
        r = requests.post("http://127.0.0.1:53200/api/v2/profile-list", json={"page": 1, "limit": 1}, timeout=2)
        if r.status_code == 200:
            return True, "ixBrowser Local API v2 is ONLINE"
        return False, f"ixBrowser responded with HTTP {r.status_code}"
    except Exception:
        # Check if local profile files exist on disk even if API is closed
        local_count = len(get_local_profiles_from_disk())
        if local_count > 0:
            return False, f"ixBrowser API Offline (Found {local_count} local profiles on disk)"
        return False, "ixBrowser not reachable. Open ixBrowser or use Lane B (Phone)."

def get_local_profiles_from_disk() -> List[Dict[str, Any]]:
    """Scan disk for ixBrowser local profiles without needing API."""
    if not os.path.exists(IX_BROWSER_DATA):
        return []

    profiles = []
    try:
        for entry in os.listdir(IX_BROWSER_DATA):
            full_path = os.path.join(IX_BROWSER_DATA, entry)
            if os.path.isdir(full_path):
                # Verify it has Chrome profile structure
                local_state = os.path.join(full_path, "Local State")
                has_default = os.path.exists(os.path.join(full_path, "Default"))
                if os.path.exists(local_state) or has_default:
                    # Try to extract name
                    profile_name = f"Profile {entry[:8]}"
                    profiles.append({
                        "profile_id": entry,
                        "name": profile_name,
                        "path": full_path,
                        "type": "LOCAL_DISK"
                    })
    except Exception:
        pass
    return profiles

def find_ix_chrome_binary() -> Optional[str]:
    """Find installed ixBrowser customized Chromium kernel."""
    if not os.path.exists(IX_RESOURCES):
        return None
    pattern = os.path.join(IX_RESOURCES, "chrome", "*", "chrome.exe")
    found = glob.glob(pattern)
    if found:
        # Return latest version
        found.sort(reverse=True)
        return found[0]
    return None

def get_all_profiles(page: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch profiles from ixBrowser Local API v2 with disk fallback."""
    if IXBrowserClient:
        try:
            with IXBrowserClient() as client:
                profiles = client.get_profile_list(page=page, limit=limit)
                if profiles is not None:
                    return profiles
        except Exception:
            pass

    # Direct HTTP fallback
    try:
        import requests
        r = requests.post("http://127.0.0.1:53200/api/v2/profile-list", json={"page": page, "limit": limit}, timeout=3)
        data = r.json()
        if data.get("code") == 0 or data.get("data"):
            api_list = data.get("data", {}).get("list", []) or data.get("data", []) or []
            if api_list:
                return api_list
    except Exception:
        pass

    # Fallback to scanning disk profiles
    return get_local_profiles_from_disk()

def open_profile(profile_id: Any, worker_idx: int = 0, proxy_server: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Open an ixBrowser profile and return (debugging_address, error_message).
    Supports numeric ID (via API) or folder hash (via direct kernel).
    worker_idx assigns an isolated debugging port for parallel concurrency.
    proxy_server injects dynamic HTTP/SOCKS5 mobile proxy.
    """
    if not proxy_server:
        try:
            from core import proxy_engine
            pcfg = proxy_engine.load_proxy_config()
            if pcfg.get("enabled") and pcfg.get("proxy_server"):
                proxy_server = pcfg["proxy_server"].strip()
        except Exception:
            pass

    # Try official API first
    if str(profile_id).isdigit():
        if IXBrowserClient:
            try:
                with IXBrowserClient() as client:
                    res = client.open_profile(profile_id=int(profile_id), load_profile_info_page=False, cookies_backup=True)
                    if res and "debugging_address" in res:
                        return res["debugging_address"], None
            except Exception:
                pass

        try:
            import requests
            r = requests.post("http://127.0.0.1:53200/api/v2/profile-open", json={
                "profile_id": int(profile_id),
                "cookies_backup": True,
                "load_profile_info_page": False
            }, timeout=8)
            data = r.json()
            addr = data.get("data", {}).get("debugging_address")
            if addr:
                return addr, None
        except Exception:
            pass

    # Offline Direct Kernel Launch Fallback
    chrome_bin = find_ix_chrome_binary()
    profile_dir = os.path.join(IX_BROWSER_DATA, str(profile_id))
    if chrome_bin and os.path.exists(profile_dir):
        # Calculate distinct port for parallel multi-worker execution
        port = 9222 + (worker_idx * 5)
        cmd = [
            chrome_bin,
            f"--user-data-dir={profile_dir}",
            f"--remote-debugging-port={port}",
            "--no-first-run",
            "--no-default-browser-check",
        ]
        if proxy_server:
            cmd.append(f"--proxy-server={proxy_server}")
        cmd.append("about:blank")
        try:
            subprocess.Popen(cmd)
            time.sleep(2)
            return f"127.0.0.1:{port}", None
        except Exception as e:
            return None, f"Direct kernel launch error: {e}"

    return None, "Could not open profile via API or Direct Kernel"

def close_profile(profile_id: Any):
    """Close profile and sync cookies."""
    if str(profile_id).isdigit():
        try:
            import requests
            requests.post("http://127.0.0.1:53200/api/v2/profile-close", json={"profile_id": int(profile_id)}, timeout=5)
        except Exception:
            pass

async def human_type(locator, text: str, min_delay: int = 35, max_delay: int = 80):
    """Type text character-by-character with micro-jitter."""
    import random
    for char in text:
        await locator.type(char, delay=random.randint(min_delay, max_delay))

def _is_google_success_url(url: str) -> bool:
    """Strict positive URL check for Google logged-in state."""
    success_domains = [
        "myaccount.google.com",
        "mail.google.com",
        "accounts.google.com/b/",
        "google.com/intl"
    ]
    return any(domain in url for domain in success_domains)

async def handle_post_login_modals(page, log_cb=None):
    """Dismiss Google post-recovery dialogs."""
    buttons = [
        "button:has-text('Not now')",
        "button:has-text('Skip')",
        "button:has-text('No thanks')",
        "button:has-text('Continue')",
        "button:has-text('Confirm')",
        "button:has-text('Done')",
        "button:has-text('Yes, it\\'s me')",
        "button:has-text('I agree')"
    ]
    for _ in range(4):
        dismissed = False
        for btn in buttons:
            try:
                el = page.locator(btn).first
                if await el.count() > 0 and await el.is_visible():
                    if log_cb:
                        log_cb(f"Dismissing modal: {btn}")
                    await el.click(timeout=2000)
                    await page.wait_for_timeout(1200)
                    dismissed = True
                    break
            except Exception:
                continue
        if not dismissed:
            break

async def handle_suspended_appeal(page, contact_email: str, appeal_text: str, log_cb=None) -> str:
    """Auto-fill and submit Google's appeal form."""
    try:
        for sel in ["text=Try to restore", "text=Start appeal", "text=Appeal", "a:has-text('appeal')"]:
            try:
                el = page.locator(sel).first
                if await el.count() > 0 and await el.is_visible():
                    await el.click(timeout=3000)
                    await page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

        for sel in ['input[type="email"]', 'input[name="contactEmail"]', 'input[id*="contact"]']:
            try:
                fld = page.locator(sel).first
                if await fld.count() > 0 and await fld.is_visible():
                    await fld.fill(contact_email)
                    break
            except Exception:
                pass

        try:
            txt = page.locator('textarea').first
            if await txt.count() > 0 and await txt.is_visible():
                await txt.fill(appeal_text)
        except Exception:
            pass

        for sub_sel in ["button:has-text('Submit')", "input[type='submit']", "button:has-text('Send')"]:
            try:
                sub_btn = page.locator(sub_sel).first
                if await sub_btn.count() > 0 and await sub_btn.is_visible():
                    await sub_btn.click(timeout=3000)
                    await page.wait_for_timeout(2000)
                    if log_cb:
                        log_cb("Appeal form submitted successfully.")
                    return "APPEAL_SUBMITTED"
            except Exception:
                pass
        return "APPEAL_FORM_FOUND"
    except Exception as e:
        return f"APPEAL_ERROR: {e}"

async def login_google_in_profile(
    profile_id: Any,
    email: str,
    passwords: Optional[List[str]] = None,
    totp_secret: Optional[str] = None,
    appeal_email: str = "abidmcs99@gmail.com",
    appeal_text: str = "This delegation account is used for business social media management.",
    worker_idx: int = 0,
    proxy_server: Optional[str] = None,
    log_cb = None
) -> Dict[str, Any]:
    """Automate Google login inside ixBrowser profile via Playwright over CDP."""
    from playwright.async_api import async_playwright

    def _log(msg: str):
        if log_cb:
            log_cb(msg)
        print(f"[ixBrowser Worker #{worker_idx + 1} Profile {profile_id}] {msg}")

    cfg = load_config()
    if not passwords:
        passwords = cfg.get("passwords_waterfall", ["Abidali@2xx", "Abidali@72xx", "Abidali2xx"])

    _log(f"Opening ixBrowser profile {profile_id} (Worker #{worker_idx + 1})...")
    debug_addr, err = open_profile(profile_id, worker_idx=worker_idx, proxy_server=proxy_server)
    if not debug_addr:
        _log(f"Profile open error: {err}")
        return {"status": "FAILED", "reason": f"Could not open profile: {err}"}

    time.sleep(2)

    try:
        async with async_playwright() as p:
            _log(f"Connecting Playwright over CDP to {debug_addr}...")
            browser = await p.chromium.connect_over_cdp(f"http://{debug_addr}")
            ctx = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()

            _log(f"Navigating to accounts.google.com for {email}...")
            await page.goto("https://accounts.google.com/signin", wait_until="domcontentloaded", timeout=25000)
            await page.wait_for_timeout(2000)

            # Check if session is already active
            current_url = page.url
            if _is_google_success_url(current_url):
                _log("Already authenticated! Session is active.")
                database.update_account(email, status="RECOVERED", ixbrowser_profile_id=str(profile_id))
                # Save offline session storage state
                try:
                    s_path = os.path.join(SESSIONS_DIR, f"{re.sub(r'[^a-zA-Z0-9]', '_', email)}.json")
                    await ctx.storage_state(path=s_path)
                except Exception:
                    pass
                close_profile(profile_id)
                return {"status": "RECOVERED", "email": email, "note": "Already authenticated"}

            # --- STEP 1: Enter Email ---
            email_input = page.locator('input[type="email"], input#identifierId').first
            try:
                await email_input.wait_for(state="visible", timeout=9000)
                await email_input.clear()
                await human_type(email_input, email)
                await page.wait_for_timeout(400)
                await page.click('#identifierNext, button:has-text("Next")')
                _log(f"Email {email} submitted.")
                await page.wait_for_timeout(2500)
            except Exception as e:
                _log(f"Email step failed: {e}")
                close_profile(profile_id)
                return {"status": "FAILED", "reason": f"Email entry error: {e}"}

            content = await page.content()
            if "couldn't find your google account" in content.lower():
                _log("Google account does not exist.")
                database.update_account(email, status="NOT_FOUND")
                close_profile(profile_id)
                return {"status": "NOT_FOUND", "email": email}

            if "account has been disabled" in content.lower() or "disabled" in page.url:
                _log("Account is disabled. Attempting automated appeal...")
                res = await handle_suspended_appeal(page, appeal_email, appeal_text, _log)
                database.update_account(email, status="SUSPENDED")
                close_profile(profile_id)
                return {"status": "SUSPENDED", "email": email, "appeal": res}

            # --- STEP 2: Password Waterfall ---
            pwd_success = False
            for idx, candidate in enumerate(passwords[:3], start=1):
                _log(f"Testing password candidate {idx}/{min(3, len(passwords))}...")
                pwd_input = page.locator('input[type="password"]').first
                try:
                    await pwd_input.wait_for(state="visible", timeout=7000)
                except Exception:
                    cur_c = await page.content()
                    if "captcha" in cur_c.lower():
                        _log("CAPTCHA challenge detected.")
                        database.update_account(email, status="NEEDS_CAPTCHA")
                        close_profile(profile_id)
                        return {"status": "NEEDS_CAPTCHA", "email": email}
                    break

                await pwd_input.clear()
                await human_type(pwd_input, candidate)
                await page.wait_for_timeout(400)
                await page.click('#passwordNext, button:has-text("Next")')
                await page.wait_for_timeout(3000)

                cur_url = page.url
                if "signin/v2/challenge/pwd" not in cur_url and "CheckCookie" not in cur_url:
                    _log("Password accepted!")
                    pwd_success = True
                    break
                else:
                    _log(f"Password {idx} rejected.")

            if not pwd_success:
                _log("All waterfall passwords rejected.")
                database.update_account(email, status="WRONG_PASSWORD")
                close_profile(profile_id)
                return {"status": "WRONG_PASSWORD", "email": email}

            # --- STEP 3: Handle 2-Step Verification & Challenges ---
            await page.wait_for_timeout(2000)
            cur_url = page.url

            # FIDO2/caBLE Challenge -> "Try another way"
            try_another = page.locator('button:has-text("Try another way"), div[role="button"]:has-text("Try another way"), #tryAnotherWay, a:has-text("Try another way")').first
            if await try_another.count() > 0 and await try_another.is_visible():
                _log("FIDO2/caBLE Challenge detected. Clicking 'Try another way'...")
                await try_another.click()
                await page.wait_for_timeout(1800)

                auth_option = page.locator('li:has-text("Authenticator"), div[role="link"]:has-text("Authenticator"), div:has-text("Google Authenticator")').first
                if await auth_option.count() > 0:
                    _log("Selecting 'Google Authenticator' option...")
                    await auth_option.click()
                    await page.wait_for_timeout(2000)

            # Check for TOTP Input
            totp_input = page.locator('input[type="tel"], input#totpPin, input[name="totpPin"], input[autocomplete="one-time-code"]').first
            if await totp_input.count() > 0 and await totp_input.is_visible():
                if not totp_secret:
                    acc = database.get_account_by_email(email)
                    if acc:
                        totp_secret = acc.get("totp_secret")

                if totp_secret:
                    code, remaining = totp.generate_totp(totp_secret)
                    if remaining < 5:
                        _log(f"TOTP expiring in {remaining}s. Waiting {remaining + 1}s for fresh code...")
                        await page.wait_for_timeout((remaining + 1) * 1000)
                        code, remaining = totp.generate_totp(totp_secret)

                    _log(f"Injecting Live TOTP: {code} ({remaining}s valid)...")
                    await totp_input.clear()
                    await human_type(totp_input, code)
                    await page.wait_for_timeout(400)
                    await page.click('#totpNext, button:has-text("Next")')
                    await page.wait_for_timeout(3500)
                else:
                    _log("ERROR: 2FA required but no TOTP secret found in vault!")
                    close_profile(profile_id)
                    return {"status": "NEEDS_TOTP_SECRET", "email": email}

            # Check for SMS OTP
            cur_c = await page.content()
            if "text message" in cur_c.lower() or "sent a code" in cur_c.lower():
                _log("Account requires SMS OTP from physical SIM.")
                database.update_account(email, status="NEEDS_SMS")
                close_profile(profile_id)
                return {"status": "NEEDS_SMS", "email": email}

            # --- STEP 4: Handle Post-Login Modals ---
            await handle_post_login_modals(page, _log)

            # --- STEP 5: Verify Final Success ---
            await page.wait_for_timeout(2000)
            final_url = page.url

            if _is_google_success_url(final_url):
                _log(f"SUCCESS! Account {email} fully recovered and authenticated!")
                database.update_account(email, status="RECOVERED", ixbrowser_profile_id=str(profile_id))

                # Save session backup
                try:
                    s_path = os.path.join(SESSIONS_DIR, f"{re.sub(r'[^a-zA-Z0-9]', '_', email)}.json")
                    await ctx.storage_state(path=s_path)
                    _log(f"Session saved offline: {os.path.basename(s_path)}")
                except Exception:
                    pass

                close_profile(profile_id)
                return {"status": "RECOVERED", "email": email, "profile_id": profile_id}

            _log(f"Login outcome uncertain. Final URL: {final_url}")
            close_profile(profile_id)
            return {"status": "UNCERTAIN", "email": email, "url": final_url}

    except Exception as e:
        _log(f"Unexpected automation error: {e}")
        try:
            close_profile(profile_id)
        except Exception:
            pass
        return {"status": "FAILED", "reason": str(e)}

def run_sync_login(profile_id: Any, email: str, **kwargs) -> Dict[str, Any]:
    """Safe synchronous entry point for threads with dedicated event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(login_google_in_profile(profile_id, email, **kwargs))
    finally:
        try:
            loop.close()
        except Exception:
            pass
