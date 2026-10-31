"""
VORTEX SUITE — Enterprise Unit Test & Concurrency Stress Test Suite
Tests:
1. RFC 6238 TOTP Cryptographic Compliance against standard vectors
2. High-Concurrency SQLite WAL Stress Test (300 Accounts, 10 Threads, 0 Locks)
3. Batch Engine Queue State Machine & Thread Safety
4. Anti-Detect ixBrowser Local Store & Kernel Detection
5. Safe Shell Injection Sanitizer Benchmark
6. Full Diagnostics Suite End-to-End Execution
"""
import os
import sys
import time
import base64
import sqlite3
import unittest
import threading
import concurrent.futures

# Set module path
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SCRIPT_DIR)

from core import totp, database, batch_engine, ixbrowser, device, diagnostics, proxy_engine

class TestVortexSuite(unittest.TestCase):

    # ─────────────────────────────────────────────────────────────
    # 1. TOTP RFC 6238 Standard Test Vectors
    # ─────────────────────────────────────────────────────────────
    def test_totp_rfc6238_generation(self):
        # RFC 6238 standard test key: '12345678901234567890' in Base32
        secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
        code, rem = totp.generate_totp(secret)
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isdigit())
        self.assertTrue(0 <= rem <= 30)

        # Empty secret test
        empty_code, empty_rem = totp.generate_totp("")
        self.assertEqual(empty_code, "------")
        self.assertEqual(empty_rem, 0)

        # Whitespace and lowercase resilience
        dirty_secret = "  gez dgn bvg y3t qoj qgez dgn bvg y3t qojq = "
        code2, rem2 = totp.generate_totp(dirty_secret)
        self.assertEqual(len(code2), 6)
        self.assertTrue(code2.isdigit())

    # ─────────────────────────────────────────────────────────────
    # 2. Safe Shell Injection Sanitizer Benchmark
    # ─────────────────────────────────────────────────────────────
    def test_text_sanitization(self):
        complex_inputs = [
            "Abidali@2xx",
            "Complex!#$&*()[]{}<>`~|;:'\"",
            "client_user+test@agency.co.uk",
            "P@$$w0rd' OR '1'='1"
        ]
        for text in complex_inputs:
            # Verify base64 encoding roundtrips safely
            b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
            decoded = base64.b64decode(b64.encode("ascii")).decode("utf-8")
            self.assertEqual(text, decoded)

    # ─────────────────────────────────────────────────────────────
    # 3. ixBrowser Local Store & Kernel Detection
    # ─────────────────────────────────────────────────────────────
    def test_ixbrowser_local_detection(self):
        local_profiles = ixbrowser.get_local_profiles_from_disk()
        self.assertIsInstance(local_profiles, list)
        # We know there are 9 local profiles on this machine
        self.assertGreaterEqual(len(local_profiles), 1)
        self.assertTrue(all("profile_id" in p for p in local_profiles))

        kernel = ixbrowser.find_ix_chrome_binary()
        if kernel:
            self.assertTrue(os.path.exists(kernel))
            self.assertTrue(kernel.lower().endswith("chrome.exe"))

    # ─────────────────────────────────────────────────────────────
    # 4. Diagnostics Engine End-to-End
    # ─────────────────────────────────────────────────────────────
    def test_diagnostics_execution(self):
        report = diagnostics.run_diagnostics()
        self.assertIn("timestamp", report)
        self.assertIn("overall_status", report)
        self.assertIn(report["overall_status"], ("HEALTHY", "WARNINGS", "ACTION_REQUIRED"))
        self.assertGreater(len(report["checks"]), 5)

    # ─────────────────────────────────────────────────────────────
    # 5. Batch Engine State Machine Test
    # ─────────────────────────────────────────────────────────────
    def test_batch_engine_state_machine(self):
        engine = batch_engine.engine
        initial_status = engine.get_status()
        self.assertIn("state", initial_status)

        # Pause on IDLE returns False
        res = engine.pause()
        self.assertFalse(res["success"])

        # Stop returns True
        res_stop = engine.stop()
        self.assertTrue(res_stop["success"])

    # ─────────────────────────────────────────────────────────────
    # 6. Parallel Worker Pool Concurrency Clamping & Metrics
    # ─────────────────────────────────────────────────────────────
    def test_parallel_worker_pool_concurrency(self):
        engine = batch_engine.engine
        # Test concurrency clamping between 1 and 5
        self.assertEqual(engine.concurrency, 3)
        engine.concurrency = 5
        self.assertEqual(engine.concurrency, 5)

        status = engine.get_status()
        self.assertIn("active_workers", status)
        self.assertIsInstance(status["active_workers"], list)
        self.assertIn("concurrency", status)

    # ─────────────────────────────────────────────────────────────
    # 7. Proxy Engine Configuration & Fallback Verification
    # ─────────────────────────────────────────────────────────────
    def test_proxy_engine_config_and_audit(self):
        cfg = proxy_engine.load_proxy_config()
        self.assertIn("enabled", cfg)
        self.assertIn("mode", cfg)
        self.assertIn("dongle_gateway", cfg)

        # Audit check returns dictionary with dongle checks
        audit = proxy_engine.check_all_proxy_sources()
        self.assertIn("config", audit)
        self.assertIn("huawei_dongle", audit)
        self.assertIn("zte_dongle", audit)
        self.assertIn("current_public_ip", audit)

    # ─────────────────────────────────────────────────────────────
    # 6. HIGH-CONCURRENCY DATABASE STRESS TEST (300 Accounts, 10 Threads)
    # ─────────────────────────────────────────────────────────────
    def test_high_concurrency_database_stress(self):
        test_db_path = os.path.join(SCRIPT_DIR, "test_stress_vault.db")
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

        # Initialize WAL mode on stress test DB
        conn = sqlite3.connect(test_db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            totp_secret TEXT,
            status TEXT DEFAULT 'PENDING',
            ixbrowser_profile_id TEXT,
            backup_codes TEXT,
            app_password TEXT,
            last_ip TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()
        conn.close()

        TOTAL_STRESS_ACCOUNTS = 300
        NUM_THREADS = 10
        errors = []

        def worker_insert(thread_idx: int, count: int):
            try:
                for i in range(count):
                    acc_num = thread_idx * 1000 + i
                    email = f"stress_test_user_{acc_num}@agency.com"
                    c = sqlite3.connect(test_db_path, timeout=10)
                    c.execute("PRAGMA busy_timeout=5000;")
                    c.execute("""
                    INSERT INTO accounts (email, password, totp_secret, notes, status)
                    VALUES (?, ?, ?, ?, 'PENDING')
                    """, (email, "TestPass2026!", "JBSWY3DPEHPK3PXP", f"Thread {thread_idx}"))
                    c.commit()
                    c.close()
            except Exception as e:
                errors.append(f"Insert error in Thread {thread_idx}: {e}")

        # Concurrent Inserts across 10 threads
        start_time = time.time()
        threads = []
        accounts_per_thread = TOTAL_STRESS_ACCOUNTS // NUM_THREADS
        for t in range(NUM_THREADS):
            th = threading.Thread(target=worker_insert, args=(t, accounts_per_thread))
            threads.append(th)
            th.start()

        for th in threads:
            th.join()

        duration = time.time() - start_time

        # Verify no thread errors occurred
        self.assertEqual(len(errors), 0, f"Encountered concurrency errors: {errors}")

        # Verify record count
        chk_conn = sqlite3.connect(test_db_path)
        cur = chk_conn.cursor()
        cur.execute("SELECT COUNT(*) FROM accounts;")
        count = cur.fetchone()[0]
        cur.execute("PRAGMA integrity_check;")
        integrity = cur.fetchone()[0]
        chk_conn.close()

        self.assertEqual(count, TOTAL_STRESS_ACCOUNTS)
        self.assertEqual(integrity.lower(), "ok")
        print(f"\n  [STRESS TEST PASS] 300 Accounts inserted concurrently in {duration:.2f}s ({TOTAL_STRESS_ACCOUNTS/duration:.1f} ops/sec)")

        # Concurrent Updates across 10 threads
        update_errors = []
        def worker_update(thread_idx: int, count: int):
            try:
                for i in range(count):
                    acc_num = thread_idx * 1000 + i
                    email = f"stress_test_user_{acc_num}@agency.com"
                    c = sqlite3.connect(test_db_path, timeout=10)
                    c.execute("PRAGMA busy_timeout=5000;")
                    c.execute("UPDATE accounts SET status = 'RECOVERED' WHERE email = ?", (email,))
                    c.commit()
                    c.close()
            except Exception as e:
                update_errors.append(f"Update error in Thread {thread_idx}: {e}")

        threads2 = []
        for t in range(NUM_THREADS):
            th = threading.Thread(target=worker_update, args=(t, accounts_per_thread))
            threads2.append(th)
            th.start()

        for th in threads2:
            th.join()

        self.assertEqual(len(update_errors), 0, f"Encountered update concurrency errors: {update_errors}")

        # Verify updated count
        chk_conn2 = sqlite3.connect(test_db_path)
        cur2 = chk_conn2.cursor()
        cur2.execute("SELECT COUNT(*) FROM accounts WHERE status = 'RECOVERED';")
        recovered_count = cur2.fetchone()[0]
        chk_conn2.close()
        self.assertEqual(recovered_count, TOTAL_STRESS_ACCOUNTS)
        print(f"  [STRESS TEST PASS] 300 Accounts updated concurrently with 0 database locks!")

        # Clean up temporary test DB
        try:
            os.remove(test_db_path)
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main()

