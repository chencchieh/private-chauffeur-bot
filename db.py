"""
In-memory storage for the Chauffeur Bot.
Data is held in module-level dicts and resets on restart.
All functions are synchronous (same API as the previous DB version).
"""

from datetime import datetime

# ─── STATE ────────────────────────────────────────────────────────────────────

_bookings: dict[str, dict] = {}      # booking_id → booking dict
_blocked_dates: dict[str, str] = {}  # date_iso   → reason
_booking_counter: int = 0


def init_db() -> None:
    """No-op — kept so bot.py startup code doesn't need to change."""
    pass


# ─── BOOKING ID COUNTER ───────────────────────────────────────────────────────

def next_booking_id() -> str:
    """Return the next sequential CC-XXXX booking ID."""
    global _booking_counter
    _booking_counter += 1
    return f"CC-{_booking_counter:04d}"


# ─── BOOKINGS ─────────────────────────────────────────────────────────────────

def save_booking(booking_id: str, user_id: str, user_name: str,
                 username: str, data: dict) -> None:
    """Store a confirmed booking in memory."""
    _bookings[booking_id] = {
        "booking_id": booking_id,
        "user_id":    user_id,
        "user_name":  user_name,
        "username":   username,
        "service":    data.get("service", ""),
        "date":       data.get("date", "—"),
        "time":       data.get("time", "—"),
        "pickup":     data.get("pickup", "—"),
        "dropoff":    data.get("dropoff", "—"),
        "flight":     data.get("flight") or "",
        "duration":   data.get("duration"),
        "pax":        data.get("pax", "—"),
        "requests":   data.get("requests") or "",
        "booked_at":  datetime.now().strftime("%d %b %Y %H:%M"),
    }


def get_user_bookings(user_id: str) -> list[dict]:
    """Return all bookings for a user, newest first."""
    return [b for b in reversed(list(_bookings.values())) if b["user_id"] == user_id]


def get_all_bookings() -> dict[str, list[dict]]:
    """Return {user_id: [bookings]} for all customers."""
    result: dict[str, list[dict]] = {}
    for b in _bookings.values():
        result.setdefault(b["user_id"], []).append(b)
    return result


def get_booking_by_id(booking_id: str) -> dict | None:
    """Return a booking dict by CC-XXXX id, or None."""
    return _bookings.get(booking_id.upper())


def get_all_user_ids() -> list[str]:
    """Return distinct user_ids that have at least one booking."""
    return list({b["user_id"] for b in _bookings.values()})


def delete_all_bookings() -> None:
    """Wipe all bookings and reset the counter."""
    global _booking_counter
    _bookings.clear()
    _booking_counter = 0


def get_stats() -> dict:
    """Return aggregate stats for /stats command."""
    total = len(_bookings)
    by_service: dict[str, int] = {}
    for b in _bookings.values():
        svc = b.get("service", "")
        by_service[svc] = by_service.get(svc, 0) + 1
    customers = len({b["user_id"] for b in _bookings.values()})
    return {
        "total": total,
        "by_service": sorted(by_service.items(), key=lambda x: x[1], reverse=True),
        "customers": customers,
    }


# ─── BLOCKED DATES ────────────────────────────────────────────────────────────

def get_blocked_dates() -> dict[str, str]:
    """Return {date_iso: reason} for all blocked dates."""
    return dict(_blocked_dates)


def block_date(date_iso: str, reason: str) -> None:
    _blocked_dates[date_iso] = reason


def unblock_date(date_iso: str) -> bool:
    """Remove a blocked date. Returns True if it existed."""
    if date_iso in _blocked_dates:
        del _blocked_dates[date_iso]
        return True
    return False


def is_date_blocked(date_iso: str) -> tuple[bool, str]:
    """Returns (True, reason) if blocked, else (False, '')."""
    if date_iso in _blocked_dates:
        return True, _blocked_dates[date_iso]
    return False, ""
