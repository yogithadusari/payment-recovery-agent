"""
Tiny SQLite data layer. No ORM — this is a hackathon project, not a bank.
Everything is one table (`orders`) plus a couple of helper queries for the
dashboard's recovered-revenue stats.
"""

import sqlite3
import time
from contextlib import contextmanager

from config import Config

SCHEMA = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seller_phone TEXT NOT NULL,
    buyer_phone TEXT NOT NULL,
    description TEXT NOT NULL,
    amount_paise INTEGER NOT NULL,
    discount_paise INTEGER NOT NULL DEFAULT 0,
    razorpay_link_id TEXT,
    razorpay_short_url TEXT,
    status TEXT NOT NULL DEFAULT 'created',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    had_failure INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    paid_at REAL
);
"""

# Valid values for `status`:
#   created          -> link just generated, no payment attempt yet
#   failed_once       -> at least one failed/abandoned attempt, agent has acted
#   nudged_upi        -> agent suggested switching to UPI
#   nudged_reminder   -> agent sent a plain reminder
#   discount_offered  -> agent issued a fresh discounted link
#   paid              -> money is in
#   lost              -> agent gave up after max attempts


@contextmanager
def get_db():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute(SCHEMA)


def create_order(seller_phone, buyer_phone, description, amount_paise):
    now = time.time()
    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO orders
               (seller_phone, buyer_phone, description, amount_paise,
                status, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'created', ?, ?)""",
            (seller_phone, buyer_phone, description, amount_paise, now, now),
        )
        return cur.lastrowid


def attach_payment_link(order_id, link_id, short_url):
    with get_db() as conn:
        conn.execute(
            """UPDATE orders SET razorpay_link_id = ?, razorpay_short_url = ?,
               updated_at = ? WHERE id = ?""",
            (link_id, short_url, time.time(), order_id),
        )


def get_order(order_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        return dict(row) if row else None


def get_order_by_link_id(link_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM orders WHERE razorpay_link_id = ?", (link_id,)
        ).fetchone()
        return dict(row) if row else None


def update_status(order_id, status, *, bump_attempt=False, mark_failure=False,
                   discount_paise=None, paid=False):
    fields = ["status = ?", "updated_at = ?"]
    values = [status, time.time()]

    if bump_attempt:
        fields.append("attempt_count = attempt_count + 1")
    if mark_failure:
        fields.append("had_failure = 1")
    if discount_paise is not None:
        fields.append("discount_paise = ?")
        values.append(discount_paise)
    if paid:
        fields.append("paid_at = ?")
        values.append(time.time())

    values.append(order_id)
    with get_db() as conn:
        conn.execute(f"UPDATE orders SET {', '.join(fields)} WHERE id = ?", values)


def list_orders(limit=100):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats():
    with get_db() as conn:
        total_orders = conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]
        paid = conn.execute(
            "SELECT COUNT(*) c FROM orders WHERE status = 'paid'"
        ).fetchone()["c"]
        lost = conn.execute(
            "SELECT COUNT(*) c FROM orders WHERE status = 'lost'"
        ).fetchone()["c"]
        recovered_row = conn.execute(
            """SELECT COUNT(*) c, COALESCE(SUM(amount_paise - discount_paise), 0) amt
               FROM orders WHERE status = 'paid' AND had_failure = 1"""
        ).fetchone()
        direct_row = conn.execute(
            """SELECT COUNT(*) c, COALESCE(SUM(amount_paise), 0) amt
               FROM orders WHERE status = 'paid' AND had_failure = 0"""
        ).fetchone()

    return {
        "total_orders": total_orders,
        "paid": paid,
        "lost": lost,
        "recovered_count": recovered_row["c"],
        "recovered_amount_paise": recovered_row["amt"],
        "direct_count": direct_row["c"],
        "direct_amount_paise": direct_row["amt"],
    }
