"""
VORTEX SUITE — Batch Auto Recovery Engine (300 Queue Orchestrator)
Features:
- Automated queue processing for 300+ accounts
- Dual-Lane intelligent dispatch: Lane A (ixBrowser CDP) or Lane B (UIAutomator2 Real Hardware)
- Multi-Phone Round-Robin: balances between OnePlus 9 Pro and Tecno Spark 5 Pro
- Rate Limit Protection: Dynamic jitter delays (8-15s), daily per-device quota safety
- Auto 4G Carrier IP Rotation every N accounts
- Graceful Start / Pause / Resume / Stop controls
"""
import time
import random
import threading
from typing import Dict, Any, List, Optional
from core import database, autopilot, device

class BatchEngine:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = "IDLE"  # IDLE, RUNNING, PAUSED, STOPPED
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_requested = False
        self.pause_requested = False
        
        # Runtime metrics
        self.total = 0
        self.processed = 0
        self.recovered = 0
        self.failed = 0
        self.current_email = ""
        self.current_lane = ""
        self.current_device = ""
        self.current_step = ""
        self.started_at = ""
        self.device_usage: Dict[str, int] = {}
        self.device_round_robin_idx = 0

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            pct = round((self.processed / self.total * 100), 1) if self.total > 0 else 0
            return {
                "state": self.state,
                "total": self.total,
                "processed": self.processed,
                "recovered": self.recovered,
                "failed": self.failed,
                "progress_pct": pct,
                "current_email": self.current_email,
                "current_lane": self.current_lane,
                "current_device": self.current_device,
                "current_step": self.current_step,
                "started_at": self.started_at,
                "device_usage": dict(self.device_usage)
            }

    def start(self, account_ids: Optional[List[int]] = None, max_accounts: int = 300) -> Dict[str, Any]:
        with self.lock:
            if self.state == "RUNNING":
                return {"success": False, "message": "Batch already running"}
            if self.state == "PAUSED":
                self.pause_requested = False
                self.state = "RUNNING"
                autopilot.log("Resuming batch recovery queue...", "INFO")
                return {"success": True, "message": "Batch resumed"}

            self.state = "RUNNING"
            self.stop_requested = False
            self.pause_requested = False
            self.processed = 0
            self.recovered = 0
            self.failed = 0
            self.started_at = time.strftime("%Y-%m-%d %H:%M:%S")

        self.worker_thread = threading.Thread(
            target=self._run_queue, 
            args=(account_ids, max_accounts), 
            daemon=True
        )
        self.worker_thread.start()
        autopilot.log(f"Batch Auto Recovery started (Queue limit: {max_accounts})...", "SUCCESS")
        return {"success": True, "message": "Batch engine started"}

    def pause(self) -> Dict[str, Any]:
        with self.lock:
            if self.state != "RUNNING":
                return {"success": False, "message": "Batch is not running"}
            self.pause_requested = True
            self.state = "PAUSED"
        autopilot.log("Batch recovery paused by user.", "WARN")
        return {"success": True, "message": "Batch paused"}

    def resume(self) -> Dict[str, Any]:
        return self.start()

    def stop(self) -> Dict[str, Any]:
        with self.lock:
            self.stop_requested = True
            self.state = "STOPPED"
        autopilot.log("Batch recovery stopped by user.", "WARN")
        return {"success": True, "message": "Batch stopping..."}

    def _select_device(self, online_devices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Multi-phone round robin selector with daily limit guard (15 per phone)."""
        if not online_devices:
            return None
        
        # Filter devices that haven't hit max daily quota of 15
        available = []
        for d in online_devices:
            did = d["id"]
            if self.device_usage.get(did, 0) < 15:
                available.append(d)
        
        if not available:
            # All available devices reached daily quota
            autopilot.log("All connected devices reached daily quota (15/day). Cool down required.", "WARN")
            return None

        # Round robin among available devices
        chosen = available[self.device_round_robin_idx % len(available)]
        self.device_round_robin_idx += 1
        return chosen

    def _run_queue(self, account_ids: Optional[List[int]], max_accounts: int):
        from core import ixbrowser, device_u2

        all_accounts = database.get_all_accounts()
        if account_ids:
            queue = [a for a in all_accounts if a["id"] in account_ids]
        else:
            # Process non-recovered accounts first
            queue = [a for a in all_accounts if a.get("status") not in ("RECOVERED", "SUSPENDED")]

        queue = queue[:max_accounts]
        with self.lock:
            self.total = len(queue)

        autopilot.log(f"Loaded {self.total} pending accounts into automated recovery queue.", "INFO")

        for idx, acc in enumerate(queue, start=1):
            if self.stop_requested:
                break
            
            while self.pause_requested:
                time.sleep(1)
                if self.stop_requested:
                    break
            if self.stop_requested:
                break

            email = acc["email"]
            pwd = acc.get("password") or "Abidali@2xx"
            secret = acc.get("totp_secret", "")
            profile_id = acc.get("ixbrowser_profile_id")

            with self.lock:
                self.current_email = email
                self.current_step = f"Processing ({idx}/{self.total})"

            autopilot.log(f"[{idx}/{self.total}] Starting recovery for: {email}", "INFO")

            # Route account to best lane
            result = None
            lane_used = "UNKNOWN"

            # Check if Lane A (ixBrowser) is preferred and profile exists
            ix_online, _ = ixbrowser.check_api_status()
            if profile_id and ix_online:
                lane_used = "Lane A (ixBrowser)"
                with self.lock:
                    self.current_lane = lane_used
                    self.current_device = f"ixBrowser Profile {profile_id}"

                try:
                    res = ixbrowser.run_sync_login(
                        profile_id=int(profile_id),
                        email=email,
                        passwords=[pwd],
                        totp_secret=secret,
                        log_cb=lambda m: autopilot.log(f"[ixBrowser] {m}", "INFO")
                    )
                    result = res
                except Exception as e:
                    result = {"status": "FAILED", "reason": str(e)}
            else:
                # Lane B: Physical Android Hardware (UIAutomator2 + ADB fallback)
                lane_used = "Lane B (Android Hardware)"
                online_devs = device.get_all_connected_devices()
                target_dev = self._select_device(online_devs)

                if not target_dev:
                    autopilot.log(f"No available Android hardware online for {email}. Skipping Lane B.", "WARN")
                    result = {"status": "SKIPPED_NO_DEVICE"}
                else:
                    dev_id = target_dev["id"]
                    dev_name = target_dev["name"]
                    with self.lock:
                        self.current_lane = lane_used
                        self.current_device = f"{dev_name} ({dev_id[:8]})"
                        self.device_usage[dev_id] = self.device_usage.get(dev_id, 0) + 1

                    autopilot.log(f"Assigned {email} to {dev_name} (Round-Robin Usage: {self.device_usage[dev_id]}/15)", "INFO")

                    # Run Lane B UIAutomator2 element recovery
                    try:
                        res = device_u2.recover_account_native(
                            device_id=dev_id,
                            email=email,
                            password=pwd,
                            totp_secret=secret,
                            log_cb=lambda m: autopilot.log(f"[{dev_name}] {m}", "INFO")
                        )
                        result = res
                    except Exception as e:
                        result = {"status": "FAILED", "reason": str(e)}

            # Evaluate Result
            st = result.get("status", "FAILED") if result else "FAILED"
            with self.lock:
                self.processed += 1
                if st == "RECOVERED":
                    self.recovered += 1
                else:
                    self.failed += 1

            database.update_account(email, status=st)
            autopilot.log(f"Finished {email} -> Status: {st}", "SUCCESS" if st == "RECOVERED" else "WARN")

            # Rate Limit Protection between accounts
            if idx < self.total and not self.stop_requested:
                jitter = random.randint(8, 15)
                autopilot.log(f"Anti-detection cooldown: waiting {jitter}s before next account...", "INFO")
                for _ in range(jitter):
                    if self.stop_requested:
                        break
                    time.sleep(1)

                # Periodic IP rotation every 3 accounts on connected phone
                if idx % 3 == 0:
                    autopilot.log(f"Periodic 3-account milestone: triggering clean 4G IP rotation...", "WARN")
                    device.rotate_carrier_ip()

        with self.lock:
            self.state = "IDLE"
            self.current_email = ""
            self.current_step = "Completed"
        autopilot.log(f"Batch Recovery Finished! Total: {self.total}, Recovered: {self.recovered}, Failed: {self.failed}", "SUCCESS")

# Singleton instance
engine = BatchEngine()

