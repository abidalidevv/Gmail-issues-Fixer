"""
VORTEX SUITE — Enterprise Batch Auto Recovery Engine (Parallel Multi-Worker 5x Speed)
Features:
- Multi-Threaded Parallel Worker Pool (1x to 5x speedup)
- Simultaneous ixBrowser Profile Execution with dynamic port isolation
- Multi-Phone Round-Robin Hardware Fleet balancing (OnePlus + Tecno)
- 4G Mobile Dongle & Proxy Rotation integration (Huawei, ZTE, Webhooks, Phone ADB)
- Synchronized IP rotation barrier preventing worker TCP collisions
- Dynamic Jitter & Socrates BotGuard evasion
- Thread-safe runtime metrics & active worker telemetry
"""
import time
import random
import threading
import queue
from typing import Dict, Any, List, Optional
from core import database, autopilot, device, ixbrowser, device_u2, proxy_engine

class BatchEngine:
    def __init__(self):
        self.lock = threading.Lock()
        self.state = "IDLE"  # IDLE, RUNNING, PAUSED, STOPPED
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_requested = False
        self.pause_requested = False
        
        # Configuration
        self.concurrency = 3  # Default 3 concurrent workers (up to 5x speed)
        
        # Runtime metrics
        self.total = 0
        self.processed = 0
        self.recovered = 0
        self.failed = 0
        self.started_at = ""
        self.device_usage: Dict[str, int] = {}
        self.device_round_robin_idx = 0
        self.rotation_lock = threading.Lock()
        self.accounts_since_rotation = 0

        # Live telemetry per active worker
        self.active_workers: Dict[int, Dict[str, Any]] = {}

    def get_status(self) -> Dict[str, Any]:
        with self.lock:
            pct = round((self.processed / self.total * 100), 1) if self.total > 0 else 0
            workers_list = [v for k, v in self.active_workers.items()]
            current_email = workers_list[0]["email"] if workers_list else "Standby"
            current_lane = f"{len(workers_list)} Active Workers ({self.concurrency}x Parallel)" if workers_list else "Standby"

            return {
                "state": self.state,
                "total": self.total,
                "processed": self.processed,
                "recovered": self.recovered,
                "failed": self.failed,
                "progress_pct": pct,
                "concurrency": self.concurrency,
                "current_email": current_email,
                "current_lane": current_lane,
                "active_workers": workers_list,
                "started_at": self.started_at,
                "device_usage": dict(self.device_usage)
            }

    def start(self, account_ids: Optional[List[int]] = None, max_accounts: int = 300, concurrency: int = 3) -> Dict[str, Any]:
        with self.lock:
            if self.state == "RUNNING":
                return {"success": False, "message": "Batch already running"}
            if self.state == "PAUSED":
                self.pause_requested = False
                self.state = "RUNNING"
                autopilot.log("Resuming parallel batch recovery queue...", "INFO")
                return {"success": True, "message": "Batch resumed"}

            self.concurrency = max(1, min(concurrency, 5))  # Clamp between 1 and 5
            self.state = "RUNNING"
            self.stop_requested = False
            self.pause_requested = False
            self.processed = 0
            self.recovered = 0
            self.failed = 0
            self.accounts_since_rotation = 0
            self.active_workers.clear()
            self.started_at = time.strftime("%Y-%m-%d %H:%M:%S")

        self.worker_thread = threading.Thread(
            target=self._run_parallel_queue, 
            args=(account_ids, max_accounts), 
            daemon=True
        )
        self.worker_thread.start()
        autopilot.log(f"Multi-Threaded Parallel Batch Started ({self.concurrency}x Concurrent Workers, Max: {max_accounts})...", "SUCCESS")
        return {"success": True, "message": f"Parallel batch started with {self.concurrency} workers"}

    def pause(self) -> Dict[str, Any]:
        with self.lock:
            if self.state != "RUNNING":
                return {"success": False, "message": "Batch is not running"}
            self.pause_requested = True
            self.state = "PAUSED"
        autopilot.log("Parallel batch paused by user.", "WARN")
        return {"success": True, "message": "Batch paused"}

    def resume(self) -> Dict[str, Any]:
        return self.start(concurrency=self.concurrency)

    def stop(self) -> Dict[str, Any]:
        with self.lock:
            self.stop_requested = True
            self.state = "STOPPED"
            self.active_workers.clear()
        autopilot.log("Parallel batch stopped by user.", "WARN")
        return {"success": True, "message": "Batch stopping..."}

    def _select_device(self, online_devices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Multi-phone round robin selector with daily limit guard."""
        if not online_devices:
            return None
        available = [d for d in online_devices if self.device_usage.get(d["id"], 0) < 15]
        if not available:
            return None
        chosen = available[self.device_round_robin_idx % len(available)]
        self.device_round_robin_idx += 1
        return chosen

    def _maybe_rotate_ip(self):
        """Coordinate periodic IP rotation across all workers safely."""
        with self.rotation_lock:
            self.accounts_since_rotation += 1
            if self.accounts_since_rotation >= 3:
                self.accounts_since_rotation = 0
                autopilot.log("Periodic 3-account milestone: triggering clean IP rotation...", "WARN")
                res = proxy_engine.rotate_ip_universal()
                autopilot.log(f"IP Rotation Complete: {res.get('new_ip', 'Unknown')} (via {res.get('source', 'Carrier')})", "SUCCESS")

    def _worker_task(self, worker_id: int, task_queue: queue.Queue):
        """Single worker processing loop for parallel execution."""
        while not self.stop_requested:
            # Check pause
            while self.pause_requested and not self.stop_requested:
                time.sleep(1)
            if self.stop_requested:
                break

            try:
                acc = task_queue.get(timeout=1)
            except queue.Empty:
                break

            email = acc["email"]
            pwd = acc.get("password") or "Abidali@2xx"
            secret = acc.get("totp_secret", "")
            profile_id = acc.get("ixbrowser_profile_id")

            with self.lock:
                self.active_workers[worker_id] = {
                    "worker_id": worker_id,
                    "email": email,
                    "lane": "Selecting Lane...",
                    "step": "Starting",
                    "status": "ACTIVE"
                }

            autopilot.log(f"[Worker #{worker_id + 1}] Processing: {email}", "INFO")

            # Route to Lane A or Lane B
            result = None
            ix_online, _ = ixbrowser.check_api_status()
            disk_profiles = ixbrowser.get_local_profiles_from_disk()

            # If account has profile or disk profiles exist, prefer Lane A (Parallel ixBrowser)
            if profile_id or (ix_online and disk_profiles):
                target_pid = profile_id or (disk_profiles[worker_id % len(disk_profiles)]["profile_id"] if disk_profiles else None)
                lane_name = f"Lane A (ixBrowser Worker #{worker_id + 1})"

                with self.lock:
                    self.active_workers[worker_id]["lane"] = lane_name
                    self.active_workers[worker_id]["step"] = f"Profile {target_pid}"

                try:
                    res = ixbrowser.run_sync_login(
                        profile_id=target_pid,
                        email=email,
                        passwords=[pwd],
                        totp_secret=secret,
                        worker_idx=worker_id,
                        log_cb=lambda m: autopilot.log(f"[Worker #{worker_id + 1}] {m}", "INFO")
                    )
                    result = res
                except Exception as e:
                    result = {"status": "FAILED", "reason": str(e)}

            else:
                # Lane B: Android Hardware
                lane_name = f"Lane B (Phone Worker #{worker_id + 1})"
                with self.lock:
                    self.active_workers[worker_id]["lane"] = lane_name

                online_devs = device.get_all_connected_devices()
                target_dev = self._select_device(online_devs)

                if not target_dev:
                    autopilot.log(f"[Worker #{worker_id + 1}] No Android hardware available for {email}.", "WARN")
                    result = {"status": "SKIPPED_NO_DEVICE"}
                else:
                    dev_id = target_dev["id"]
                    dev_name = target_dev["name"]
                    with self.lock:
                        self.active_workers[worker_id]["step"] = f"{dev_name}"
                        self.device_usage[dev_id] = self.device_usage.get(dev_id, 0) + 1

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

            # Process outcome
            st = result.get("status", "FAILED") if result else "FAILED"
            database.update_account(email, status=st)

            with self.lock:
                self.processed += 1
                if st == "RECOVERED":
                    self.recovered += 1
                else:
                    self.failed += 1
                if worker_id in self.active_workers:
                    del self.active_workers[worker_id]

            autopilot.log(f"[Worker #{worker_id + 1}] Finished {email} -> {st}", "SUCCESS" if st == "RECOVERED" else "WARN")
            task_queue.task_done()

            # Anti-detection jitter cooldown
            if not self.stop_requested and not task_queue.empty():
                jitter = random.randint(4, 8)
                time.sleep(jitter)

            # Check if milestone rotation needed
            self._maybe_rotate_ip()

    def _run_parallel_queue(self, account_ids: Optional[List[int]], max_accounts: int):
        all_accounts = database.get_all_accounts()
        if account_ids:
            queue_items = [a for a in all_accounts if a["id"] in account_ids]
        else:
            queue_items = [a for a in all_accounts if a.get("status") not in ("RECOVERED", "SUSPENDED")]

        queue_items = queue_items[:max_accounts]
        with self.lock:
            self.total = len(queue_items)

        autopilot.log(f"Dispatching {self.total} accounts across {self.concurrency} parallel worker threads...", "INFO")

        task_queue = queue.Queue()
        for item in queue_items:
            task_queue.put(item)

        threads = []
        for wid in range(self.concurrency):
            th = threading.Thread(target=self._worker_task, args=(wid, task_queue), daemon=True)
            threads.append(th)
            th.start()

        for th in threads:
            th.join()

        with self.lock:
            self.state = "IDLE"
            self.active_workers.clear()

        autopilot.log(f"All Parallel Workers Finished! Total: {self.total}, Recovered: {self.recovered}, Failed: {self.failed}", "SUCCESS")

# Singleton instance
engine = BatchEngine()
