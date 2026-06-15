"""
Persistent storage for the Chauffeur Bot using PostgreSQL.
All functions are synchronous (called via asyncio.to_thread from bot.py).
"""

import os
import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool
from datetime import datetime

_pool: ThreadedConnectionPool | None = None


def init_db() -> None:
    """Initialise the connection pool. Call once at startup."""
    global _pool
    _pool = ThreadedConnectionPool(
        minconn=1,
        maxconn=5,
        dsn=os.environ["DATABASE_URL"],
    )


def _conn():
    """Borrow a connection from the pool."""
    if _pool is None:
        raise RuntimeError("Database pool not initialised — call init_db() first.")
    return _pool.getconn()


def _put(conn):
    _pool.putconn(conn)


# ─── BOOKING ID COUNTER ───────────────────────────────────────────────────────

def next_booking_id() -> str:
    """Atomically increment the counter and return the next CC-XXXX id."""
    conn = _conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE counters SET value = value + 1 WHERE key = 'booking_counter' RETURNING value"
                )
                n = cur.fetchone()[0]
        return f"CC-{n:04d}"
    finally:
        _put(conn)


# ─── BOOKINGS ─────────────────────────────────────────────────────────────────

def save_booking(booking_id: str, user_id: str, user_name: str,
                 username: str, data: dict) -> None:
    """Persist a confirmed booking."""
    conn = _conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO bookings
                        (booking_id, user_id, user_name, username,
                         service, date, time, pickup, dropoff,
                         flight, duration, pax, requests)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        booking_id,
                        user_id,
                        user_name,
                        username,
                        data.get("service", ""),
                        data.get("date", ""),
                        data.get("time", ""),
                        data.get("pickup", ""),
                        data.get("dropoff", ""),
                        data.get("flight", "") or None,
                        data.get("duration") or None,
                        data.get("pax", ""),
                        data.get("requests", "") or None,
                    ),
                )
    finally:
        _put(conn)


def _row_to_dict(row) -> dict:
    return {
        "booking_id": row["booking_id"],
        "user_id":    row["user_id"],
        "user_name":  row["user_name"] or "",
        "username":   row["username"] or "",
        "service":    row["service"] or "",
        "date":       row["date"] or "—",
        "time":       row["time"] or "—",
        "pickup":     row["pickup"] or "—",
        "dropoff":    row["dropoff"] or "—",
        "flight":     row["flight"] or "",
        "duration":   row["duration"],
        "pax":        row["pax"] or "—",
        "requests":   row["requests"] or "",
        "booked_at":  row["booked_at"].strftime("%d %b %Y %H:%M") if row["booked_at"] else "—",
    }


def get_user_bookings(user_id: str) -> list[dict]:
    """Return all bookings for a user, newest first."""
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM bookings WHERE user_id = %s ORDER BY booked_at DESC",
                (user_id,),
            )
            return [_row_to_dict(r) for r in cur.fetchall()]
    finally:
        _put(conn)


def get_all_bookings() -> dict[str, list[dict]]:
    """Return {user_id: [bookings]} for all customers, newest first per user."""
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM bookings ORDER BY user_id, booked_at DESC")
            rows = cur.fetchall()
        result: dict[str, list[dict]] = {}
        for row in rows:
            uid = row["user_id"]
            result.setdefault(uid, []).append(_row_to_dict(row))
        return result
    finally:
        _put(conn)


def get_booking_by_id(booking_id: str) -> dict | None:
    """Return a booking dict for the given CC-XXXX id, or None if not found."""
    conn = _conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM bookings WHERE booking_id = %s",
                (booking_id.upper(),),
            )
            row = cur.fetchone()
            return _row_to_dict(row) if row else None
    finally:
        _put(conn)


def get_all_user_ids() -> list[str]:
    """Return distinct user_ids that have at least one booking."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT user_id FROM bookings")
            return [r[0] for r in cur.fetchall()]
    finally:
        _put(conn)


def delete_all_bookings() -> None:
    """Wipe all bookings and reset the counter."""
    conn = _conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM bookings")
                cur.execute("UPDATE counters SET value = 0 WHERE key = 'booking_counter'")
    finally:
        _put(conn)


def get_stats() -> dict:
    """Return aggregate stats for /stats command."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bookings")
            total = cur.fetchone()[0]

            cur.execute(
                "SELECT service, COUNT(*) FROM bookings GROUP BY service ORDER BY COUNT(*) DESC"
            )
            by_service = cur.fetchall()

            cur.execute("SELECT COUNT(DISTINCT user_id) FROM bookings")
            customers = cur.fetchone()[0]
        return {"total": total, "by_service": by_service, "customers": customers}
    finally:
        _put(conn)


# ─── BLOCKED DATES ────────────────────────────────────────────────────────────

def get_blocked_dates() -> dict[str, str]:
    """Return {date_iso: reason} for all blocked dates."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT date_iso, reason FROM blocked_dates ORDER BY date_iso")
            return {r[0]: r[1] for r in cur.fetchall()}
    finally:
        _put(conn)


def block_date(date_iso: str, reason: str) -> None:
    conn = _conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO blocked_dates (date_iso, reason)
                    VALUES (%s, %s)
                    ON CONFLICT (date_iso) DO UPDATE SET reason = EXCLUDED.reason
                    """,
                    (date_iso, reason),
                )
    finally:
        _put(conn)


def unblock_date(date_iso: str) -> bool:
    """Returns True if a row was deleted."""
    conn = _conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM blocked_dates WHERE date_iso = %s", (date_iso,))
                return cur.rowcount > 0
    finally:
        _put(conn)


def is_date_blocked(date_iso: str) -> tuple[bool, str]:
    """Returns (True, reason) if blocked, else (False, '')."""
    conn = _conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT reason FROM blocked_dates WHERE date_iso = %s", (date_iso,))
            row = cur.fetchone()
            return (True, row[0]) if row else (False, "")
    finally:
        _put(conn)
