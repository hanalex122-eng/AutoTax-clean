import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from app.config import settings

DB_PATH = Path(settings.SQLITE_PATH)
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
_LOCK = Lock()

DDL = """
CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    filename TEXT,
    timestamp TEXT,
    vendor TEXT,
    date TEXT,
    time TEXT,
    total REAL,
    vat_rate INTEGER,
    vat_amount REAL,
    invoice_number TEXT,
    category TEXT,
    payment_method TEXT,
    qr_raw TEXT,
    qr_parsed TEXT,
    raw_text TEXT,
    needs_review INTEGER DEFAULT 0,
    review_reason TEXT,
    invoice_type TEXT DEFAULT 'expense',
    user_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_uid ON invoices(user_id);
CREATE INDEX IF NOT EXISTS idx_ts ON invoices(timestamp DESC);
"""

def _conn():
    c = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def _init():
    with _conn() as c:
        c.executescript(DDL)

_init()

# --------------------------
# ADD
# --------------------------

def add_invoice(record: dict, filename: str, user_id: str) -> str:
    inv_id = str(uuid.uuid4())
    with _LOCK:
        with _conn() as c:
            c.execute("""
                INSERT INTO invoices VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                inv_id,
                filename,
                datetime.utcnow().isoformat(),
                record.get("vendor"),
                record.get("date"),
                record.get("time"),
                record.get("total"),
                record.get("vat_rate"),
                record.get("vat_amount"),
                record.get("invoice_number"),
                record.get("category"),
                record.get("payment_method"),
                (record.get("qr_raw") or "")[:500],
                json.dumps(record.get("qr_parsed")) if record.get("qr_parsed") else None,
                (record.get("raw_text") or "")[:5000],
                1 if record.get("needs_review") else 0,
                record.get("review_reason"),
                record.get("invoice_type", "expense"),
                user_id
            ))
    return inv_id

# --------------------------
# GET (IDOR SAFE)
# --------------------------

def get_invoice(inv_id: str, user_id: str):
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM invoices WHERE id=? AND user_id=?",
            (inv_id, user_id)
        ).fetchone()
    return dict(row) if row else None

# --------------------------
# UPDATE (IDOR SAFE)
# --------------------------

def update_invoice(inv_id: str, user_id: str, fields: dict) -> bool:
    allowed = {
        "vendor","date","time","total",
        "vat_rate","vat_amount",
        "invoice_number","category",
        "payment_method","needs_review","review_reason"
    }

    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k}=?" for k in updates)
    values = list(updates.values())

    with _LOCK:
        with _conn() as c:
            cur = c.execute(
                f"UPDATE invoices SET {set_clause} WHERE id=? AND user_id=?",
                values + [inv_id, user_id]
            )
    return cur.rowcount > 0

# --------------------------
# DELETE (SAFE)
# --------------------------

def delete_invoice(inv_id: str, user_id: str) -> bool:
    with _LOCK:
        with _conn() as c:
            cur = c.execute(
                "DELETE FROM invoices WHERE id=? AND user_id=?",
                (inv_id, user_id)
            )
    return cur.rowcount > 0

# --------------------------
# QUERY (MULTI TENANT SAFE)
# --------------------------

def query_invoices(user_id: str, page: int = 1, per_page: int = 50):
    with _conn() as c:
        total = c.execute(
            "SELECT COUNT(*) FROM invoices WHERE user_id=?",
            (user_id,)
        ).fetchone()[0]

        offset = (page - 1) * per_page

        rows = c.execute(
            "SELECT * FROM invoices WHERE user_id=? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (user_id, per_page, offset)
        ).fetchall()

    return {
        "count": total,
        "page": page,
        "per_page": per_page,
        "invoices": [dict(r) for r in rows]
    }

# --------------------------
# REVIEW QUEUE (USER SAFE)
# --------------------------

def get_review_queue(user_id: str, page: int = 1, per_page: int = 50):
    with _conn() as c:
        total = c.execute(
            "SELECT COUNT(*) FROM invoices WHERE user_id=? AND needs_review=1",
            (user_id,)
        ).fetchone()[0]

        offset = (page - 1) * per_page

        rows = c.execute(
            "SELECT * FROM invoices WHERE user_id=? AND needs_review=1 ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (user_id, per_page, offset)
        ).fetchall()

    return {
        "count": total,
        "page": page,
        "per_page": per_page,
        "invoices": [dict(r) for r in rows]
    }

# --------------------------
# GDPR PURGE FIXED
# --------------------------

def purge_old_invoice_files(days: int = 90) -> int:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with _LOCK:
        with _conn() as c:
            cur = c.execute(
                "DELETE FROM invoices WHERE timestamp < ?",
                (cutoff,)
            )
    return cur.rowcount