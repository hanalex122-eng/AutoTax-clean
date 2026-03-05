import psycopg2
import json
import uuid
from datetime import datetime, timedelta
from threading import Lock
from app.config import settings

_LOCK = Lock()


def _conn():
    return psycopg2.connect(
        settings.DATABASE_URL,
        sslmode="require"
    )


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


def init_db():
    try:
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(DDL)
            c.commit()
        print("[AutoTax] Database schema ready", flush=True)
    except Exception as e:
        print(f"[AutoTax] Database init failed: {e}", flush=True)
        raise


def add_invoice(record: dict, filename: str, user_id: str) -> str:
    inv_id = str(uuid.uuid4())

    with _LOCK:
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO invoices VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
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
                        user_id,
                    ),
                )
            c.commit()

    return inv_id


def get_invoice(inv_id: str, user_id: str):
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                "SELECT * FROM invoices WHERE id=%s AND user_id=%s",
                (inv_id, user_id),
            )
            row = cur.fetchone()

            if not row:
                return None

            cols = [desc[0] for desc in cur.description]
            return dict(zip(cols, row))


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

    set_clause = ", ".join(f"{k}=%s" for k in updates)
    values = list(updates.values())

    with _LOCK:
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    f"UPDATE invoices SET {set_clause} WHERE id=%s AND user_id=%s",
                    values + [inv_id, user_id],
                )
                updated = cur.rowcount
            c.commit()

    return updated > 0


def delete_invoice(inv_id: str, user_id: str) -> bool:
    with _LOCK:
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "DELETE FROM invoices WHERE id=%s AND user_id=%s",
                    (inv_id, user_id),
                )
                deleted = cur.rowcount
            c.commit()

    return deleted > 0


def query_invoices(user_id: str, page: int = 1, per_page: int = 50):

    offset = (page - 1) * per_page

    with _conn() as c:
        with c.cursor() as cur:

            cur.execute(
                "SELECT COUNT(*) FROM invoices WHERE user_id=%s",
                (user_id,),
            )
            total = cur.fetchone()[0]

            cur.execute(
                "SELECT * FROM invoices WHERE user_id=%s ORDER BY timestamp DESC LIMIT %s OFFSET %s",
                (user_id, per_page, offset),
            )

            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]

    invoices = [dict(zip(cols, r)) for r in rows]

    return {
        "count": total,
        "page": page,
        "per_page": per_page,
        "invoices": invoices,
    }


def purge_old_invoice_files(days: int = 90) -> int:

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

    with _LOCK:
        with _conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "DELETE FROM invoices WHERE timestamp < %s",
                    (cutoff,),
                )
                deleted = cur.rowcount
            c.commit()

    return deleted


def find_duplicate(user_id: str, total: float, date: str, vendor: str):

    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM invoices
                WHERE user_id=%s
                AND total=%s
                AND date=%s
                AND vendor=%s
                LIMIT 1
                """,
                (user_id, total, date, vendor),
            )

            row = cur.fetchone()

    if row:
        return row[0]

    return None


def find_recurring(user_id: str, vendor: str):

    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) 
                FROM invoices
                WHERE user_id=%s
                AND vendor=%s
                """,
                (user_id, vendor),
            )

            count = cur.fetchone()[0]

    return count >= 3


def iter_rows(rows, cols):
    for r in rows:
        yield dict(zip(cols, r))


def get_data(row, key, default=None):
    if not row:
        return default
    return row.get(key, default)


def safe_float(value):
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def get_invoices_page(user_id: str, page: int = 1, per_page: int = 50):

    offset = (page - 1) * per_page

    with _conn() as c:
        with c.cursor() as cur:

            cur.execute(
                "SELECT * FROM invoices WHERE user_id=%s ORDER BY timestamp DESC LIMIT %s OFFSET %s",
                (user_id, per_page, offset),
            )

            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]

    return [dict(zip(cols, r)) for r in rows]


def get_ledger(user_id: str):

    with _conn() as c:
        with c.cursor() as cur:

            cur.execute(
                """
                SELECT date, vendor, total, category
                FROM invoices
                WHERE user_id=%s
                ORDER BY date DESC
                """,
                (user_id,),
            )

            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]

    return [dict(zip(cols, r)) for r in rows]

def get_review_queue(user_id: str, page: int = 1, per_page: int = 50):

    offset = (page - 1) * per_page

    with _conn() as c:
        with c.cursor() as cur:

            cur.execute(
                "SELECT COUNT(*) FROM invoices WHERE user_id=%s AND needs_review=1",
                (user_id,),
            )
            total = cur.fetchone()[0]

            cur.execute(
                """
                SELECT * FROM invoices
                WHERE user_id=%s AND needs_review=1
                ORDER BY timestamp DESC
                LIMIT %s OFFSET %s
                """,
                (user_id, per_page, offset),
            )

            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]

    invoices = [dict(zip(cols, r)) for r in rows]

    return {
        "count": total,
        "page": page,
        "per_page": per_page,
        "invoices": invoices,
    }