import os
import sys
import json
import urllib.parse
import webbrowser
from typing import Any
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from core import database, device, autopilot, totp, ixbrowser, batch_engine, diagnostics

PORT = 8765
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(SCRIPT_DIR, "static")

class RecoveryHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def log_message(self, format, *args):
        # Suppress verbose access logs
        pass

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path
        query = urllib.parse.parse_qs(url.query)

        # ─── API Routes ───────────────────────────────────────────────
        if path == "/api/ixbrowser/status":
            online, msg = ixbrowser.check_api_status()
            self.send_json({"online": online, "message": msg})
            return

        elif path == "/api/ixbrowser/profiles":
            profiles = ixbrowser.get_all_profiles()
            self.send_json({"profiles": profiles})
            return

        elif path == "/api/ixbrowser/local_profiles":
            profiles = ixbrowser.get_local_profiles_from_disk()
            self.send_json({"profiles": profiles})
            return

        elif path == "/api/device":
            self.send_json(device.get_connected_device() or {"status": "DISCONNECTED"})
            return

        elif path == "/api/devices":
            devs = device.get_all_connected_devices()
            self.send_json({"devices": devs, "count": len(devs)})
            return

        elif path == "/api/diagnostics":
            report = diagnostics.run_diagnostics()
            self.send_json(report)
            return

        elif path == "/api/batch/status":
            self.send_json(batch_engine.engine.get_status())
            return

        elif path == "/api/screen":
            device_id = query.get("device_id", [None])[0]
            png_bytes = device.capture_screenshot(device_id)
            if png_bytes:
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Content-Length", str(len(png_bytes)))
                self.end_headers()
                self.wfile.write(png_bytes)
            else:
                self.send_response(404)
                self.end_headers()
            return

        elif path == "/api/accounts":
            accounts = database.get_all_accounts()
            stats = database.get_stats()
            self.send_json({"accounts": accounts, "stats": stats})
            return

        elif path == "/api/state":
            self.send_json(autopilot.get_state())
            return

        elif path == "/api/totp":
            secret = query.get("secret", [""])[0]
            code, remaining = totp.generate_totp(secret)
            self.send_json({"code": code, "remaining": remaining})
            return

        elif path == "/api/totp/batch":
            secrets_param = query.get("secrets", [""])[0]
            results = {}
            if secrets_param:
                for secret in secrets_param.split(","):
                    s = secret.strip()
                    if s:
                        code, remaining = totp.generate_totp(s)
                        results[s] = {"code": code, "remaining": remaining}
            self.send_json(results)
            return

        elif path == "/api/export":
            accounts = database.get_all_accounts()
            csv_lines = ["email,password,app_password,backup_codes,status"]
            for a in accounts:
                csv_lines.append(f'"{a["email"]}","{a["password"]}","{a.get("app_password") or ""}","{a.get("backup_codes") or ""}","{a["status"]}"')
            csv_content = "\n".join(csv_lines).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", 'attachment; filename="warmup_recovered_accounts.csv"')
            self.send_header("Content-Length", str(len(csv_content)))
            self.end_headers()
            self.wfile.write(csv_content)
            return

        # Fallback to static files
        if path == "/":
            self.path = "/index.html"
        elif path == "/docs.html":
            self.path = "/docs.html"
        return super().do_GET()

    def do_POST(self):
        url = urllib.parse.urlparse(self.path)
        path = url.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            data = json.loads(body.decode("utf-8"))
        except Exception:
            data = {}

        # ─── Batch Engine Controls ────────────────────────────────────
        if path == "/api/batch/start":
            max_accs = int(data.get("max_accounts", 300))
            res = batch_engine.engine.start(max_accounts=max_accs)
            self.send_json(res)
            return

        elif path == "/api/batch/pause":
            res = batch_engine.engine.pause()
            self.send_json(res)
            return

        elif path == "/api/batch/resume":
            res = batch_engine.engine.resume()
            self.send_json(res)
            return

        elif path == "/api/batch/stop":
            res = batch_engine.engine.stop()
            self.send_json(res)
            return

        elif path == "/api/action":
            action = data.get("action", "")
            email = data.get("email", "")
            extra = data.get("extra", "")
            res = autopilot.run_single_step(action, email, extra)
            self.send_json(res)
            return

        elif path == "/api/ixbrowser/recover":
            profile_id = data.get("profile_id")
            email = data.get("email")
            if not profile_id or not email:
                self.send_json({"success": False, "error": "profile_id and email required"}, 400)
                return

            def _bg_run():
                autopilot.log(f"Starting ixBrowser Playwright recovery for {email} (Profile {profile_id})...", "INFO")
                res = ixbrowser.run_sync_login(
                    profile_id=profile_id,
                    email=email,
                    log_cb=lambda m: autopilot.log(m, "INFO")
                )
                st = res.get("status", "FAILED")
                autopilot.log(f"ixBrowser recovery finished for {email}: Status = {st}", "SUCCESS" if st == "RECOVERED" else "WARN")

            import threading
            threading.Thread(target=_bg_run, daemon=True).start()
            self.send_json({"success": True, "message": f"ixBrowser recovery queued for {email}"})
            return

        elif path == "/api/accounts/add":
            email = data.get("email", "")
            pwd = data.get("password", "")
            secret = data.get("totp_secret", "")
            notes = data.get("notes", "")
            if email and pwd:
                success = database.add_account(email, pwd, secret, notes)
                self.send_json({"success": success})
            else:
                self.send_json({"success": False, "error": "Email and Password required"}, 400)
            return

        elif path == "/api/accounts/update":
            email = data.get("email", "")
            status = data.get("status")
            codes = data.get("backup_codes")
            app_pwd = data.get("app_password")
            profile_id = data.get("ixbrowser_profile_id")
            if email:
                success = database.update_account(
                    email, 
                    status=status, 
                    backup_codes=codes, 
                    app_password=app_pwd,
                    ixbrowser_profile_id=profile_id
                )
                self.send_json({"success": success})
            else:
                self.send_json({"success": False}, 400)
            return

        elif path == "/api/accounts/delete":
            acc_id = data.get("id")
            if acc_id:
                success = database.delete_account(acc_id)
                self.send_json({"success": success})
            else:
                self.send_json({"success": False}, 400)
            return

        self.send_json({"error": "Not Found"}, 404)

    def send_json(self, data: Any, code: int = 200):
        content = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

def main():
    database.init_db()

    server = ThreadingHTTPServer(("127.0.0.1", PORT), RecoveryHandler)
    url = f"http://127.0.0.1:{PORT}"
    print("=" * 68)
    print(f"   ⚡ VORTEX GOOGLE ACCOUNT ORCHESTRATOR & RECOVERY SUITE ⚡   ")
    print(f"   Dashboard Live At: {url}   ")
    print(f"   Multi-Phone & 300 Batch Engine Ready   ")
    print("=" * 68)

    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")

if __name__ == "__main__":
    main()
