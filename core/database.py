import sqlite3
import os
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vault.db")

# FIX PERF-04: Track if WAL mode has been initialized already
_db_initialized = False

def get_connection():
    """Open a SQLite connection. PRAGMAs only set once at init."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    # FIX PERF-04: busy_timeout is per-connection (must stay here), but WAL/sync only set at init
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn

def init_db():
    """Initialize database schema and set persistent PRAGMAs once."""
    global _db_initialized
    conn = get_connection()
    cursor = conn.cursor()

    # FIX PERF-04: Set WAL and synchronous only at startup, not every connection
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
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

    # Migration: Add ixbrowser_profile_id if table already existed without it
    cursor.execute("PRAGMA table_info(accounts)")
    cols = [c[1] for c in cursor.fetchall()]
    if "ixbrowser_profile_id" not in cols:
        cursor.execute("ALTER TABLE accounts ADD COLUMN ixbrowser_profile_id TEXT;")

    conn.commit()
    conn.close()
    _db_initialized = True

def get_all_accounts() -> List[Dict[str, Any]]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts ORDER BY id DESC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"DB Error get_all_accounts: {e}")
        return []
    finally:
        conn.close()

def get_account_by_email(email: str) -> Optional[Dict[str, Any]]:
    """FIX ARCH-02: Direct single-account lookup instead of scanning all accounts."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM accounts WHERE LOWER(email) = LOWER(?)", (email.strip(),))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"DB Error get_account_by_email: {e}")
        return None
    finally:
        conn.close()

def get_stats() -> Dict[str, int]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'RECOVERED' THEN 1 ELSE 0 END) as recovered,
            SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status = 'SUSPENDED' THEN 1 ELSE 0 END) as suspended,
            SUM(CASE WHEN status = 'WRONG_PASSWORD' THEN 1 ELSE 0 END) as wrong_password,
            SUM(CASE WHEN status = 'NEEDS_SMS' THEN 1 ELSE 0 END) as needs_sms
        FROM accounts
        """)
        row = cursor.fetchone()
        return {
            "total": row["total"] or 0,
            "recovered": row["recovered"] or 0,
            "pending": row["pending"] or 0,
            "suspended": row["suspended"] or 0,
            "wrong_password": row["wrong_password"] or 0,
            "needs_sms": row["needs_sms"] or 0,
        }
    except Exception as e:
        print(f"DB Error get_stats: {e}")
        return {"total": 0, "recovered": 0, "pending": 0, "suspended": 0, "wrong_password": 0, "needs_sms": 0}
    finally:
        conn.close()

def add_account(email: str, password: str, totp_secret: str = "", notes: str = "") -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO accounts (email, password, totp_secret, notes, status)
        VALUES (?, ?, ?, ?, 'PENDING')
        ON CONFLICT(email) DO UPDATE SET
            password=excluded.password,
            totp_secret=excluded.totp_secret,
            notes=excluded.notes,
            updated_at=CURRENT_TIMESTAMP
        """, (email.strip(), password.strip(), totp_secret.strip(), notes.strip()))
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error add_account: {e}")
        return False
    finally:
        # FIX BUG-05: Always close connection even on exception
        conn.close()

def update_account(email: str, status: Optional[str] = None, backup_codes: Optional[str] = None,
                   app_password: Optional[str] = None, last_ip: Optional[str] = None, notes: Optional[str] = None,
                   ixbrowser_profile_id: Optional[str] = None) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        fields = []
        values = []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if backup_codes is not None:
            fields.append("backup_codes = ?")
            values.append(backup_codes)
        if app_password is not None:
            fields.append("app_password = ?")
            values.append(app_password)
        if last_ip is not None:
            fields.append("last_ip = ?")
            values.append(last_ip)
        if notes is not None:
            fields.append("notes = ?")
            values.append(notes)
        if ixbrowser_profile_id is not None:
            fields.append("ixbrowser_profile_id = ?")
            values.append(ixbrowser_profile_id)

        if not fields:
            return False

        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(email)

        query = f"UPDATE accounts SET {', '.join(fields)} WHERE email = ?"
        cursor.execute(query, values)
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Error update_account: {e}")
        return False
    finally:
        # FIX BUG-05: Always close, even if exception
        conn.close()

def delete_account(acc_id: int) -> bool:
    # FIX ARCH-04: Added proper error handling
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"DB Error delete_account: {e}")
        return False
    finally:
        conn.close()
