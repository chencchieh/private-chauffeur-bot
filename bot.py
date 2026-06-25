"""
╔══════════════════════════════════════════════════════════════╗
║        Private Chauffeur Booking Bot — Chih Chieh Chen       ║
║        Telegram Bot · Singapore                               ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import os
import re
from functools import wraps
from datetime import datetime
import db
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)

# ─── CONFIG ──────────────────────────────────────────────────────────────────

BOT_TOKEN     = os.getenv("BOT_TOKEN", "")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "")

OWNER_NAME    = "Chih Chieh"
BUSINESS_URL  = "https://private-chauffeur.netlify.app"

RATES = {
    "airport_arrival":   60,
    "airport_departure": 50,
    "hourly":            60,
}
EXTENSION_RATE = 1.20  # S$ per minute beyond booked hours


# ─── INPUT VALIDATORS ────────────────────────────────────────────────────────

_MONTHS = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"

_DATE_FORMATS = [
    "%d %b %Y", "%d %B %Y",    # 15 Jun 2026 / 15 June 2026
    "%d/%m/%Y", "%d-%m-%Y",    # 15/06/2026 / 15-06-2026
    "%d/%m/%y", "%d-%m-%y",    # 15/06/26 / 15-06-26
    "%b %d %Y", "%B %d %Y",    # Jun 15 2026
    "%d %b",    "%d %B",       # 15 Jun (no year — assume current/next year)
    "%b %d",    "%B %d",       # Jun 15
]

def parse_date_obj(text: str):
    """Try to parse text into a date object. Returns date or None."""
    from datetime import date as date_type
    t = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(t, fmt)
            # If no year in format, assign current year (or next if already past)
            if "%Y" not in fmt and "%y" not in fmt:
                today = datetime.today()
                dt = dt.replace(year=today.year)
                if dt.date() < today.date():
                    dt = dt.replace(year=today.year + 1)
            return dt.date()
        except ValueError:
            continue
    return None

def valid_date(text: str) -> bool:
    t = text.lower().strip()
    # DD/MM/YYYY or DD-MM-YYYY
    if re.search(r"\d{1,2}[/\-]\d{1,2}([/\-]\d{2,4})?", t):
        return True
    # 15 Jun 2026 / Jun 15 / 15 June
    if re.search(rf"\d{{1,2}}\s+{_MONTHS}", t):
        return True
    if re.search(rf"{_MONTHS}\s+\d{{1,2}}", t):
        return True
    return False

def valid_time(text: str) -> bool:
    t = text.lower().strip()
    # 14:30 or 8:00 AM or 8am / 8 am
    if re.search(r"\d{1,2}[:.]\d{2}", t):
        return True
    if re.search(r"\d{1,2}\s*(am|pm)", t):
        return True
    return False

_SG_AREAS = {
    # Planning areas / towns
    "ang mo kio", "bedok", "bishan", "boon lay", "bukit batok", "bukit merah",
    "bukit panjang", "bukit timah", "central area", "choa chu kang", "clementi",
    "geylang", "hougang", "jurong east", "jurong west", "kallang", "lim chu kang",
    "mandai", "marine parade", "novena", "pasir ris", "punggol", "queenstown",
    "sembawang", "sengkang", "serangoon", "simpang", "tampines", "tanglin",
    "tengah", "toa payoh", "tuas", "western islands", "woodlands", "yishun",
    # Common landmarks & areas
    "orchard", "changi", "marina bay", "raffles", "sentosa", "harbourfront",
    "dhoby ghaut", "city hall", "bugis", "lavender", "farrer park", "little india",
    "chinatown", "tanjong pagar", "telok blangah", "pasir panjang", "one north",
    "buona vista", "dover", "kent ridge", "holland", "commonwealth", "queensway",
    "redhill", "tiong bahru", "outram", "havelock", "robertson quay", "clarke quay",
    "boat quay", "esplanade", "promenade", "bayfront", "gardens by the bay",
    "east coast", "kembangan", "eunos", "paya lebar", "aljunied", "kallang",
    "mountbatten", "dakota", "macpherson", "tai seng", "bartley", "lorong chuan",
    "bishan", "marymount", "caldecott", "stevens", "newton", "bras basah",
    "upper thomson", "bright hill", "springleaf", "lentor", "yio chu kang",
    "khatib", "canberra", "admiralty", "kranji", "marsiling", "woodlands",
    "bukit panjang", "cashew", "hillview", "beauty world", "king albert park",
    "sixth avenue", "tan kah kee", "botanic gardens", "farrer road",
    "mrt", "lrt", "hdb", "blk", "block", "avenue", "street", "road", "drive",
    "crescent", "close", "lane", "way", "place", "terrace", "walk", "link",
    "view", "rise", "grove", "vale", "hill", "garden", "park", "square",
    "central", "mall", "plaza", "tower", "building", "centre", "center",
    "terminal", "airport", "hotel", "singapore",
}

_FOREIGN_CITIES = {
    "kuala lumpur", "kl ", " kl", "johor", "jb ", " jb", "penang", "ipoh",
    "malacca", "malaysia", "indonesia", "jakarta", "bali", "bangkok", "thailand",
    "vietnam", "hanoi", "ho chi minh", "philippines", "manila", "hong kong",
    "taiwan", "taipei", "japan", "tokyo", "osaka", "korea", "seoul",
    "china", "beijing", "shanghai", "guangzhou", "india", "mumbai", "delhi",
    "australia", "sydney", "melbourne", "london", "new york", "dubai",
}

def valid_singapore_location(text: str) -> tuple[bool, str]:
    """
    Returns (is_valid, reason).
    reason is non-empty only when invalid.
    """
    t = text.lower().strip()

    if len(t) < 4:
        return False, "too short"

    # Reject if a foreign city/country is mentioned
    for foreign in _FOREIGN_CITIES:
        if foreign in t:
            return False, "foreign"

    # Accept Singapore 6-digit postal code (S(xxxxxx) or just 6 digits starting 01–82)
    if re.search(r"\b(s\s*)?\d{6}\b", t):
        return True, ""

    # Accept if any SG keyword found
    for kw in _SG_AREAS:
        if kw in t:
            return True, ""

    # Accept if text contains a number (block/unit) AND at least one letter word ≥ 3 chars
    has_number = bool(re.search(r"\d", t))
    has_word   = bool(re.search(r"[a-z]{3,}", t))
    if has_number and has_word:
        return True, ""

    return False, "unrecognised"

def valid_flight(text: str) -> bool:
    t = text.strip().lower()
    if t == "skip":
        return True
    # e.g. SQ321, MH370, TR123, BA9
    return bool(re.match(r"^[a-z]{1,3}\d{1,4}[a-z]?$", t))

def valid_pax(text: str) -> bool:
    try:
        n = int(text.strip())
        return 1 <= n <= 5
    except ValueError:
        return False


# ─── CONVERSATION STATES ─────────────────────────────────────────────────────

(
    SERVICE_TYPE,
    TRIP_DATE,
    TRIP_TIME,
    PICKUP_LOCATION,
    DROPOFF_LOCATION,
    FLIGHT_NUMBER,
    PAX_COUNT,
    HOURLY_DURATION,
    SPECIAL_REQUESTS,
    CONFIRM_BOOKING,
    EXTRA_PICKUP,
    EXTRA_DROPOFF,
) = range(12)

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def service_label(key):
    return {
        "airport_arrival":   "✈️ Airport Arrival (Pick-up)",
        "airport_departure": "🛫 Airport Departure (Drop-off)",
        "hourly":            "⏱️ Hourly Charter",
    }.get(key, key)

def build_summary(data: dict) -> str:
    svc_key = data.get("service", "")
    svc = service_label(svc_key)
    extra_pickups  = data.get("extra_pickups", [])
    extra_dropoffs = data.get("extra_dropoffs", [])
    extra_stop_count = len(extra_pickups) + len(extra_dropoffs)
    extra_charge = extra_stop_count * 10

    lines = [
        "📋 *Booking Summary*",
        "─────────────────────",
        f"🚗 *Service:* {svc}",
        f"📅 *Date:* {data.get('date', '—')}",
        f"🕐 *Time:* {data.get('time', '—')}",
        f"📍 *Pick-up:* {data.get('pickup', '—')}",
    ]
    for i, ep in enumerate(extra_pickups, 2):
        lines.append(f"📍 *Pick-up #{i}:* {ep}  _(+S$10)_")
    lines.append(f"🏁 *Drop-off:* {data.get('dropoff', '—')}")
    for i, ed in enumerate(extra_dropoffs, 2):
        lines.append(f"🏁 *Drop-off #{i}:* {ed}  _(+S$10)_")

    if svc_key in ("airport_arrival", "airport_departure"):
        lines.append(f"✈️ *Flight No:* {data.get('flight', 'Not provided')}")
    if svc_key == "hourly":
        dur = data.get("duration", "—")
        total = RATES["hourly"] * int(dur) if str(dur).isdigit() else "—"
        lines.append(f"⏳ *Duration:* {dur} hrs")
        lines.append(f"💵 *Est. Total:* S${total}")
        lines.append(f"⏱️ _Extension beyond booked time: S${EXTENSION_RATE:.2f}/min_")
    else:
        base = RATES.get(svc_key, 0)
        if extra_charge:
            lines.append(f"💵 *Base Rate:* S${base}")
            lines.append(f"➕ *Extra Stops:* +S${extra_charge} ({extra_stop_count} × S$10)")
            lines.append(f"💵 *Total:* S${base + extra_charge}")
        else:
            lines.append(f"💵 *Rate:* S${base}")
    lines.append(f"👥 *Passengers:* {data.get('pax', '—')}")
    if data.get("requests"):
        lines.append(f"📝 *Requests:* {data.get('requests')}")
    lines.append("─────────────────────")
    lines.append("🚙 *Vehicle:* Toyota Voxy / Noah (→ Noah from Jun 2026)")
    lines.append("📍 *Area:* Singapore")
    return "\n".join(lines)


# ─── /START ──────────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    user = update.effective_user
    name = user.first_name or "there"

    welcome = (
        f"👋 Hello {name}! Welcome to *Chih Chieh's Private Chauffeur* service.\n\n"
        f"🚙 *Toyota Voxy / Noah* · Singapore\n"
        f"📱 Available 24/7 · Fixed rates · No surge pricing\n\n"
        f"How can I help you today?"
    )
    keyboard = [
        [InlineKeyboardButton("📅 Book a Ride", callback_data="book")],
        [InlineKeyboardButton("💰 View Rates",  callback_data="rates")],
        [InlineKeyboardButton("📋 My Bookings", callback_data="mybookings")],
        [InlineKeyboardButton("📞 Contact Chih Chieh", callback_data="contact")],
        [InlineKeyboardButton("🌐 View Business Card", url=BUSINESS_URL)],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    await update.message.reply_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show available commands — owner sees extra management commands."""
    user_id = str(update.effective_user.id)
    is_owner = user_id == str(OWNER_CHAT_ID)

    text = (
        "📖 *Available Commands*\n"
        "─────────────────────\n\n"
        "👤 *Customer Commands*\n"
        "/start — Main menu\n"
        "/mybookings — View your bookings\n"
        "/help — Show this help\n"
    )

    if is_owner:
        text += (
            "\n🔑 *Owner Commands*\n"
            "/listbookings — View all bookings\n"
            "/confirm `CC-XXXX` — Confirm a booking\n"
            "/reply `CC-XXXX` message — Message a customer\n"
            "/cancelride `CC-XXXX` reason — Cancel a booking\n"
            "/stats — Booking statistics\n"
            "/broadcast message — Message all customers\n\n"
            "📅 *Availability*\n"
            "/block `24 Dec` to `2 Jan` reason — Block date range\n"
            "/unblock `24 Dec` to `2 Jan` — Unblock date range\n"
            "/setavailability `date` reason — Block a single date\n"
            "/clearavailability `date` — Unblock a single date\n"
            "/viewavailability — View all blocked dates\n\n"
            "🗑️ *Danger Zone*\n"
            "/clearbookings confirm — Wipe all bookings\n"
        )

    keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]]
    await update.message.reply_text(
        text, parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def main_menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "rates":
        text = (
            "💰 *My Rates (SGD)*\n"
            "─────────────────────\n"
            "✈️ *Airport Arrival* — S$60\n"
            "   _(Pick-up from Changi)_\n\n"
            "🛫 *Airport Departure* — S$50\n"
            "   _(Drop-off to Changi)_\n\n"
            "⏱️ *Hourly Charter* — S$60/hr\n"
            "   _(Minimum 2 hours · min. charge S$120)_\n"
            "   _(Extension: S$1.20/min beyond booked hours)_\n\n"
            "─────────────────────\n"
            "🚙 Toyota Voxy / Noah · 4–5 pax\n"
            "📌 ERP & parking charges extra"
        )
        keyboard = [[InlineKeyboardButton("📅 Book Now", callback_data="book"),
                     InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]]
        await q.edit_message_text(text, parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup(keyboard))

    elif q.data == "contact":
        text = (
            "📞 *Contact Chih Chieh*\n"
            "─────────────────────\n"
            "✈️ Telegram: +65 8127 2450\n\n"
            "Or simply book directly through this bot! 👇"
        )
        keyboard = [[InlineKeyboardButton("📅 Book Now", callback_data="book"),
                     InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]]
        await q.edit_message_text(text, parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup(keyboard))

    elif q.data == "mybookings":
        user = q.from_user
        all_bookings = ctx.bot_data.get("bookings", {})
        history = all_bookings.get(str(user.id), [])

        if not history:
            await q.edit_message_text(
                "📋 You have no bookings yet.\n\nTap below to make your first booking!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📅 Book a Ride", callback_data="book"),
                     InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
                ])
            )
            return

        lines = [f"📋 *Your Bookings* ({len(history)} total)\n"]
        for i, b in enumerate(reversed(history), 1):
            svc = service_label(b.get("service", ""))
            lines.append(f"*#{i} — {svc}*")
            lines.append(f"📅 {b.get('date', '—')}  🕐 {b.get('time', '—')}")
            lines.append(f"📍 {b.get('pickup', '—')} → {b.get('dropoff', '—')}")
            if b.get("flight"):
                lines.append(f"✈️ Flight: {b['flight']}")
            if b.get("duration"):
                lines.append(f"⏳ Duration: {b['duration']} hrs")
            lines.append(f"👥 Pax: {b.get('pax', '—')}")
            if b.get("requests"):
                lines.append(f"📝 {b['requests']}")
            lines.append(f"🕓 _Booked: {b.get('booked_at', '—')}_")
            lines.append("─────────────────────")

        keyboard = [[InlineKeyboardButton("📅 Book Another Ride", callback_data="book"),
                     InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]]
        await q.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif q.data == "menu":
        await q.edit_message_text(
            "🏠 *Main Menu* — what would you like to do?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 Book a Ride", callback_data="book")],
                [InlineKeyboardButton("💰 View Rates",  callback_data="rates")],
                [InlineKeyboardButton("📋 My Bookings", callback_data="mybookings")],
                [InlineKeyboardButton("📞 Contact Chih Chieh", callback_data="contact")],
                [InlineKeyboardButton("🌐 Business Card", url=BUSINESS_URL)],
                [InlineKeyboardButton("❓ Help", callback_data="help")],
            ])
        )

    elif q.data == "help":
        user_id = str(q.from_user.id)
        is_owner = user_id == str(OWNER_CHAT_ID)
        text = (
            "📖 *Available Commands*\n"
            "─────────────────────\n\n"
            "👤 *Customer Commands*\n"
            "/start — Main menu\n"
            "/mybookings — View your bookings\n"
            "/help — Show this help\n"
        )
        if is_owner:
            text += (
                "\n🔑 *Owner Commands*\n"
                "/listbookings — View all bookings\n"
                "/confirm `CC-XXXX` — Confirm a booking\n"
                "/reply `CC-XXXX` message — Message a customer\n"
                "/cancelride `CC-XXXX` reason — Cancel a booking\n"
                "/stats — Booking statistics\n"
                "/broadcast message — Message all customers\n\n"
                "📅 *Availability*\n"
                "/block `24 Dec` to `2 Jan` reason — Block date range\n"
                "/unblock `24 Dec` to `2 Jan` — Unblock date range\n"
                "/setavailability `date` reason — Block a single date\n"
                "/clearavailability `date` — Unblock a single date\n"
                "/viewavailability — View all blocked dates\n\n"
                "🗑️ *Danger Zone*\n"
                "/clearbookings confirm — Wipe all bookings\n"
            )
        await q.edit_message_text(
            text, parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]
            ])
        )


# ─── BOOKING FLOW ────────────────────────────────────────────────────────────

async def book_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()

    keyboard = [
        [InlineKeyboardButton("✈️ Airport Arrival (Pick-up)  S$60",  callback_data="airport_arrival")],
        [InlineKeyboardButton("🛫 Airport Departure (Drop-off)  S$50", callback_data="airport_departure")],
        [InlineKeyboardButton("⏱️ Hourly Charter  S$60/hr (min. 2 hrs)", callback_data="hourly")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ]
    await q.edit_message_text(
        "📅 *New Booking*\n\nPlease select your service type:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SERVICE_TYPE


async def service_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cancel":
        await q.edit_message_text("❌ Booking cancelled. Type /start to begin again.")
        return ConversationHandler.END

    ctx.user_data["service"] = q.data
    await q.edit_message_text(
        f"✅ *{service_label(q.data)}* selected.\n\n"
        "📅 Please enter your *trip date*:\n"
        "_(e.g. 15 Jun 2026 or 15/06/2026)_",
        parse_mode="Markdown"
    )
    return TRIP_DATE


async def get_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    date_text = update.message.text.strip()
    if not valid_date(date_text):
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid date. Please try again.\n"
            "_(e.g. 15 Jun 2026 or 15/06/2026)_",
            parse_mode="Markdown"
        )
        return TRIP_DATE
    # Check owner-blocked dates
    parsed = parse_date_obj(date_text)
    if parsed:
        is_blocked, reason = await asyncio.to_thread(db.is_date_blocked, str(parsed))
        if is_blocked:
            msg = "⛔ Sorry, *Chih Chieh is unavailable* on that date."
            if reason:
                msg += f"\n📝 Reason: _{reason}_"
            msg += "\n\nPlease choose a different date:"
            await update.message.reply_text(msg, parse_mode="Markdown")
            return TRIP_DATE
    ctx.user_data["date"] = date_text
    await update.message.reply_text(
        f"📅 Date: *{date_text}*\n\n"
        "🕐 What time do you need the car?\n"
        "_(e.g. 8:00 AM or 14:30)_",
        parse_mode="Markdown"
    )
    return TRIP_TIME


def terminal_keyboard(action: str) -> InlineKeyboardMarkup:
    """Inline keyboard with Changi Terminal 1–4 buttons (2 per row)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Terminal 1", callback_data=f"terminal_{action}_T1"),
            InlineKeyboardButton("Terminal 2", callback_data=f"terminal_{action}_T2"),
        ],
        [
            InlineKeyboardButton("Terminal 3", callback_data=f"terminal_{action}_T3"),
            InlineKeyboardButton("Terminal 4", callback_data=f"terminal_{action}_T4"),
        ],
    ])


async def get_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    time_text = update.message.text.strip()
    if not valid_time(time_text):
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid time. Please try again.\n"
            "_(e.g. 8:00 AM or 14:30)_",
            parse_mode="Markdown"
        )
        return TRIP_TIME
    ctx.user_data["time"] = time_text
    svc = ctx.user_data.get("service")

    if svc == "airport_arrival":
        await update.message.reply_text(
            "✈️ *Which terminal are you arriving at?*",
            parse_mode="Markdown",
            reply_markup=terminal_keyboard("pickup")
        )
    elif svc == "airport_departure":
        await update.message.reply_text(
            "📍 *Pick-up location:*\n_(e.g. 123 Orchard Road, Singapore)_",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "📍 *Pick-up location:*\n_(e.g. 10 Marina Bay, Singapore)_",
            parse_mode="Markdown"
        )
    return PICKUP_LOCATION


async def terminal_pickup_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handles terminal button press for airport arrival pick-up."""
    query = update.callback_query
    await query.answer()
    terminal = query.data.split("_")[-1]  # T1, T2, T3, T4
    pickup = f"Changi Airport {terminal} — Arrival Hall"
    ctx.user_data["pickup"] = pickup
    await query.edit_message_text(f"📍 Pick-up: *{pickup}*", parse_mode="Markdown")
    await ctx.bot.send_message(
        chat_id=query.message.chat_id,
        text="🏁 *Drop-off location:*\n_(e.g. 12 Marina Blvd, Blk 45 Tampines Ave 1)_",
        parse_mode="Markdown"
    )
    return DROPOFF_LOCATION


async def terminal_dropoff_chosen(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Handles terminal button press for airport departure drop-off."""
    query = update.callback_query
    await query.answer()
    terminal = query.data.split("_")[-1]  # T1, T2, T3, T4
    dropoff = f"Changi Airport {terminal} — Departure Hall"
    ctx.user_data["dropoff"] = dropoff
    await query.edit_message_text(f"🏁 Drop-off: *{dropoff}*", parse_mode="Markdown")
    await ctx.bot.send_message(
        chat_id=query.message.chat_id,
        text="✈️ *Flight number?*\n_(e.g. SQ321 — helps me track delays)_\n"
             "Or type *skip* if you don't have it yet.",
        parse_mode="Markdown"
    )
    return FLIGHT_NUMBER


async def get_pickup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pickup_text = update.message.text.strip()
    ok, reason = valid_singapore_location(pickup_text)
    if not ok:
        if reason == "foreign":
            await update.message.reply_text(
                "⚠️ Sorry, I only operate within *Singapore*.\n"
                "Please enter a Singapore pick-up address.\n"
                "_(e.g. Changi Airport T3, 123 Orchard Road, Blk 45 Tampines Ave 1)_",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "⚠️ I couldn't recognise that as a Singapore address.\n"
                "Please be more specific — include the street name, block, or area.\n"
                "_(e.g. Changi Airport T3, 123 Orchard Road, Blk 45 Tampines Ave 1)_",
                parse_mode="Markdown"
            )
        return PICKUP_LOCATION
    ctx.user_data["pickup"] = pickup_text
    ctx.user_data.setdefault("extra_pickups", [])
    svc = ctx.user_data.get("service")

    if svc == "airport_arrival":
        await update.message.reply_text(
            "🏁 *Drop-off location:*\n_(e.g. 12 Marina Blvd, Blk 45 Tampines Ave 1)_",
            parse_mode="Markdown"
        )
        return DROPOFF_LOCATION
    elif svc == "airport_departure":
        await update.message.reply_text(
            "➕ *Any additional pick-up stops?* (+S$10 each)\n"
            "Type the address, or *done* to continue.",
            parse_mode="Markdown"
        )
        return EXTRA_PICKUP
    else:
        await update.message.reply_text(
            "🏁 *Drop-off / final destination:*\n_(or type 'Multiple stops' if needed)_",
            parse_mode="Markdown"
        )
        return DROPOFF_LOCATION


async def get_dropoff(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    dropoff_text = update.message.text.strip()
    ok, reason = valid_singapore_location(dropoff_text)
    if not ok:
        if reason == "foreign":
            await update.message.reply_text(
                "⚠️ Sorry, I only operate within *Singapore*.\n"
                "Please enter a Singapore drop-off address.\n"
                "_(e.g. 12 Marina Blvd, Blk 10 Woodlands Ave 2, or 'Multiple stops')_",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                "⚠️ I couldn't recognise that as a Singapore address.\n"
                "Please be more specific — include the street name, block, or area.\n"
                "_(e.g. 12 Marina Blvd, Blk 10 Woodlands Ave 2, or 'Multiple stops')_",
                parse_mode="Markdown"
            )
        return DROPOFF_LOCATION
    ctx.user_data["dropoff"] = dropoff_text
    ctx.user_data.setdefault("extra_dropoffs", [])
    svc = ctx.user_data.get("service")

    if svc == "airport_arrival":
        await update.message.reply_text(
            "➕ *Any additional drop-off stops?* (+S$10 each)\n"
            "Type the address, or *done* to continue.",
            parse_mode="Markdown"
        )
        return EXTRA_DROPOFF
    if svc == "airport_departure":
        await update.message.reply_text(
            "✈️ *Flight number?*\n_(e.g. SQ321 — helps me track delays)_\n"
            "Or type *skip* if you don't have it yet.",
            parse_mode="Markdown"
        )
        return FLIGHT_NUMBER
    elif svc == "hourly":
        await update.message.reply_text(
            "⏳ *How many hours do you need?*\n_(Minimum 2 hours — e.g. type 3)_\n_Extension beyond booked time: S$1.20/min_",
            parse_mode="Markdown"
        )
        return HOURLY_DURATION
    else:
        await update.message.reply_text(
            "👥 *How many passengers?* (max 4–5)\n_(e.g. 2)_",
            parse_mode="Markdown"
        )
        return PAX_COUNT


async def get_extra_pickup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Collect additional pick-up stops for airport departure (+S$10 each)."""
    text = update.message.text.strip()
    if text.lower() == "done":
        await update.message.reply_text(
            "✈️ *Which terminal are you departing from?*",
            parse_mode="Markdown",
            reply_markup=terminal_keyboard("dropoff")
        )
        return DROPOFF_LOCATION
    ok, reason = valid_singapore_location(text)
    if not ok:
        msg = (
            "⚠️ Sorry, I only operate within *Singapore*.\nPlease enter a Singapore address."
            if reason == "foreign" else
            "⚠️ I couldn't recognise that as a Singapore address.\n"
            "Please be more specific — include the street name, block, or area."
        )
        await update.message.reply_text(
            msg + "\n\nOr type *done* to continue without adding more stops.",
            parse_mode="Markdown"
        )
        return EXTRA_PICKUP
    ctx.user_data.setdefault("extra_pickups", []).append(text)
    count = len(ctx.user_data["extra_pickups"])
    await update.message.reply_text(
        f"✅ *Pick-up #{count + 1}* added.\n\n"
        "➕ Any more pick-up stops? (+S$10 each)\n"
        "Type the address, or *done* to continue.",
        parse_mode="Markdown"
    )
    return EXTRA_PICKUP


async def get_extra_dropoff(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Collect additional drop-off stops for airport arrival (+S$10 each)."""
    text = update.message.text.strip()
    if text.lower() == "done":
        await update.message.reply_text(
            "✈️ *Flight number?*\n_(e.g. SQ321 — helps me track delays)_\n"
            "Or type *skip* if you don't have it yet.",
            parse_mode="Markdown"
        )
        return FLIGHT_NUMBER
    ok, reason = valid_singapore_location(text)
    if not ok:
        msg = (
            "⚠️ Sorry, I only operate within *Singapore*.\nPlease enter a Singapore address."
            if reason == "foreign" else
            "⚠️ I couldn't recognise that as a Singapore address.\n"
            "Please be more specific — include the street name, block, or area."
        )
        await update.message.reply_text(
            msg + "\n\nOr type *done* to continue without adding more stops.",
            parse_mode="Markdown"
        )
        return EXTRA_DROPOFF
    ctx.user_data.setdefault("extra_dropoffs", []).append(text)
    count = len(ctx.user_data["extra_dropoffs"])
    await update.message.reply_text(
        f"✅ *Drop-off #{count + 1}* added.\n\n"
        "➕ Any more drop-off stops? (+S$10 each)\n"
        "Type the address, or *done* to continue.",
        parse_mode="Markdown"
    )
    return EXTRA_DROPOFF


async def get_flight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not valid_flight(text):
        await update.message.reply_text(
            "⚠️ That doesn't look like a valid flight number.\n"
            "_(e.g. SQ321, MH370 — or type *skip* if unknown)_",
            parse_mode="Markdown"
        )
        return FLIGHT_NUMBER
    ctx.user_data["flight"] = "—" if text.lower() == "skip" else text.upper()
    await update.message.reply_text(
        "👥 *How many passengers?* (max 4–5)\n_(e.g. 2)_",
        parse_mode="Markdown"
    )
    return PAX_COUNT


async def get_duration(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    dur = update.message.text.strip()
    try:
        hrs = int(dur)
        if hrs < 2:
            await update.message.reply_text("⚠️ Minimum is *2 hours*. Please enter 2 or more:", parse_mode="Markdown")
            return HOURLY_DURATION
        ctx.user_data["duration"] = hrs
    except ValueError:
        await update.message.reply_text("Please enter a number (e.g. 3):")
        return HOURLY_DURATION

    await update.message.reply_text(
        "👥 *How many passengers?* (max 4–5)\n_(e.g. 2)_",
        parse_mode="Markdown"
    )
    return PAX_COUNT


async def get_pax(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pax_text = update.message.text.strip()
    if not valid_pax(pax_text):
        await update.message.reply_text(
            "⚠️ Please enter a number between 1 and 5.\n_(e.g. 2)_",
            parse_mode="Markdown"
        )
        return PAX_COUNT
    ctx.user_data["pax"] = pax_text
    await update.message.reply_text(
        "📝 Any *special requests*?\n"
        "_(e.g. baby seat, extra luggage, meet & greet sign)_\n"
        "Or type *none*.",
        parse_mode="Markdown"
    )
    return SPECIAL_REQUESTS


async def get_requests(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    ctx.user_data["requests"] = "" if text.lower() == "none" else text

    summary = build_summary(ctx.user_data)
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Booking", callback_data="confirm")],
        [InlineKeyboardButton("✏️ Start Over",       callback_data="restart")],
        [InlineKeyboardButton("❌ Cancel",            callback_data="cancel_final")],
    ]
    await update.message.reply_text(
        f"{summary}\n\nPlease review your booking above. All good?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CONFIRM_BOOKING


async def confirm_booking(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "cancel_final":
        await q.edit_message_text("❌ Booking cancelled. Type /start to begin again.")
        return ConversationHandler.END

    if q.data == "restart":
        ctx.user_data.clear()
        keyboard = [[InlineKeyboardButton("📅 Book a Ride", callback_data="book")]]
        await q.edit_message_text(
            "🔄 Let's start over. Tap below:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END

    user = q.from_user
    data = ctx.user_data
    summary = build_summary(data)

    # ── Generate unique booking ID and persist ──
    booking_id = await asyncio.to_thread(db.next_booking_id)
    await asyncio.to_thread(
        db.save_booking,
        booking_id, str(user.id), user.full_name or "", user.username or "", data
    )

    await q.edit_message_text(
        f"🎉 *Booking Confirmed!*\n\n"
        f"🔖 *Booking ID: `{booking_id}`*\n\n"
        f"{summary}\n\n"
        f"✅ Your request has been sent to *{OWNER_NAME}*.\n"
        f"He will confirm via Telegram shortly.\n\n"
        f"_Please quote *{booking_id}* if you need to follow up._",
        parse_mode="Markdown"
    )

    owner_msg = (
        f"🔔 *New Booking Request!*\n\n"
        f"🔖 *Booking ID: `{booking_id}`*\n\n"
        f"{summary}\n\n"
        f"─────────────────────\n"
        f"👤 *Customer:* {user.full_name}\n"
        f"🆔 Username: @{user.username or 'N/A'}\n\n"
        f"*Quick reply commands:*\n"
        f"`/confirm {booking_id}`\n"
        f"`/reply {booking_id} your message here`\n"
        f"`/cancelride {booking_id} reason`"
    )
    try:
        await ctx.bot.send_message(
            chat_id=OWNER_CHAT_ID,
            text=owner_msg,
            parse_mode="Markdown"
        )
        await ctx.bot.send_message(
            chat_id=OWNER_CHAT_ID,
            text=f"💬 [Open chat with customer](tg://user?id={user.id})",
            parse_mode="Markdown"
        )
    except Exception as e:
        log.error(f"Failed to notify owner: {e}")

    return ConversationHandler.END


# ─── MY BOOKINGS COMMAND ─────────────────────────────────────────────────────

async def my_bookings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    history = await asyncio.to_thread(db.get_user_bookings, str(user.id))

    if not history:
        await update.message.reply_text(
            "📋 You have no bookings yet.\n\nType /start to make your first booking!",
        )
        return

    lines = [f"📋 *Your Bookings* ({len(history)} total)\n"]
    for i, b in enumerate(reversed(history), 1):
        svc = service_label(b.get("service", ""))
        bid = b.get("booking_id", "—")
        lines.append(f"*#{i} — {svc}*  `{bid}`")
        lines.append(f"📅 {b.get('date', '—')}  🕐 {b.get('time', '—')}")
        lines.append(f"📍 {b.get('pickup', '—')} → {b.get('dropoff', '—')}")
        if b.get("flight"):
            lines.append(f"✈️ Flight: {b['flight']}")
        if b.get("duration"):
            lines.append(f"⏳ Duration: {b['duration']} hrs")
        lines.append(f"👥 Pax: {b.get('pax', '—')}")
        if b.get("requests"):
            lines.append(f"📝 {b['requests']}")
        lines.append(f"🕓 _Booked: {b.get('booked_at', '—')}_")
        lines.append("─────────────────────")

    keyboard = [[InlineKeyboardButton("📅 Book Another Ride", callback_data="book")]]
    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ─── OWNER REPLY COMMANDS ────────────────────────────────────────────────────

def owner_only(func):
    """Decorator — silently ignores commands not sent by the owner."""
    @wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_user.id) != str(OWNER_CHAT_ID):
            return
        return await func(update, ctx)
    return wrapper


@owner_only
async def owner_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Usage: /confirm <booking_id>  e.g. /confirm CC-0001"""
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/confirm CC-0001`", parse_mode="Markdown")
        return
    booking_id = args[0].upper()
    booking = await asyncio.to_thread(db.get_booking_by_id, booking_id)
    if not booking:
        await update.message.reply_text(f"❌ No booking found with ID `{booking_id}`.", parse_mode="Markdown")
        return
    customer_id = booking["user_id"]
    try:
        await ctx.bot.send_message(
            chat_id=customer_id,
            text=(
                f"✅ *Booking Confirmed!*\n\n"
                f"🔖 Booking ID: `{booking_id}`\n\n"
                f"Hi! *{OWNER_NAME}* has confirmed your booking.\n"
                f"He will be there on time. See you soon! 🚗"
            ),
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Confirmation sent for `{booking_id}`.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")


@owner_only
async def owner_reply(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Usage: /reply <booking_id> <message>  e.g. /reply CC-0001 your message"""
    args = ctx.args
    if not args or len(args) < 2:
        await update.message.reply_text(
            "Usage: `/reply CC-0001 your message here`", parse_mode="Markdown"
        )
        return
    booking_id = args[0].upper()
    booking = await asyncio.to_thread(db.get_booking_by_id, booking_id)
    if not booking:
        await update.message.reply_text(f"❌ No booking found with ID `{booking_id}`.", parse_mode="Markdown")
        return
    customer_id = booking["user_id"]
    message = " ".join(args[1:])
    try:
        await ctx.bot.send_message(
            chat_id=customer_id,
            text=(
                f"📨 *Message from {OWNER_NAME}:*\n\n"
                f"_Re: booking `{booking_id}`_\n\n"
                f"{message}\n\n"
                f"_Reply via Telegram if you have questions._"
            ),
            parse_mode="Markdown"
        )
        await update.message.reply_text(f"✅ Message sent for `{booking_id}`.", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")


@owner_only
async def owner_list_bookings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show all bookings across all customers."""
    all_bookings = await asyncio.to_thread(db.get_all_bookings)

    if not all_bookings:
        await update.message.reply_text("📋 No bookings recorded yet.")
        return

    total = sum(len(v) for v in all_bookings.values())
    lines = [f"📋 *All Bookings* ({total} total across {len(all_bookings)} customer(s))\n"]

    for user_id, bookings in all_bookings.items():
        lines.append(f"👤 *Customer ID:* `{user_id}` — {len(bookings)} booking(s)")
        for i, b in enumerate(reversed(bookings), 1):
            svc = service_label(b.get("service", ""))
            bid = b.get("booking_id", "—")
            lines.append(f"  *#{i}* {svc}  `{bid}`")
            lines.append(f"  📅 {b.get('date', '—')}  🕐 {b.get('time', '—')}")
            lines.append(f"  📍 {b.get('pickup', '—')} → {b.get('dropoff', '—')}")
            if b.get("flight"):
                lines.append(f"  ✈️ Flight: {b['flight']}")
            if b.get("duration"):
                lines.append(f"  ⏳ {b['duration']} hrs")
            lines.append(f"  👥 Pax: {b.get('pax', '—')}")
            if b.get("requests"):
                lines.append(f"  📝 {b['requests']}")
            lines.append(f"  🕓 _{b.get('booked_at', '—')}_")
        for b in bookings:
            bid = b.get("booking_id", "—")
            lines.append(
                f"  ↩️ `/confirm {bid}` · `/reply {bid} msg` · `/cancelride {bid} reason`"
            )
        lines.append("─────────────────────")

    # Telegram has a 4096 char limit — split if needed
    text = "\n".join(lines)
    if len(text) <= 4096:
        await update.message.reply_text(text, parse_mode="Markdown")
    else:
        chunks, current = [], []
        for line in lines:
            current.append(line)
            if len("\n".join(current)) > 3800:
                await update.message.reply_text("\n".join(current[:-1]), parse_mode="Markdown")
                current = [line]
        if current:
            await update.message.reply_text("\n".join(current), parse_mode="Markdown")


@owner_only
async def owner_clear_bookings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Wipe all booking history. Asks for confirmation first."""
    args = ctx.args
    if not args or args[0].lower() != "confirm":
        await update.message.reply_text(
            "⚠️ This will delete *all* booking history for every customer.\n\n"
            "To confirm, send:\n`/clearbookings confirm`",
            parse_mode="Markdown"
        )
        return
    await asyncio.to_thread(db.delete_all_bookings)
    await update.message.reply_text("🗑️ All booking history has been cleared.")


@owner_only
async def owner_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Show a summary of all bookings."""
    stats = await asyncio.to_thread(db.get_stats)

    if stats["total"] == 0:
        await update.message.reply_text("📊 No bookings recorded yet.")
        return

    counts = {"airport_arrival": 0, "airport_departure": 0, "hourly": 0}
    revenue = 0
    for svc, cnt in stats["by_service"]:
        if svc in counts:
            counts[svc] = cnt
        rate = RATES.get(svc, 0)
        if svc == "hourly":
            pass  # duration-based; revenue tracked separately below
        else:
            revenue += rate * cnt

    # Rough hourly revenue needs full booking data — skip for now, show fixed services
    popular_svc = stats["by_service"][0][0] if stats["by_service"] else "—"
    popular_label = service_label(popular_svc) if popular_svc != "—" else "—"

    lines = [
        "📊 *Booking Stats*",
        "─────────────────────",
        f"👥 *Customers:* {stats['customers']}",
        f"📋 *Total Bookings:* {stats['total']}",
        "",
        "📈 *By Service:*",
        f"  ✈️ Airport Arrival:   {counts['airport_arrival']}",
        f"  🛫 Airport Departure: {counts['airport_departure']}",
        f"  ⏱️ Hourly Charter:    {counts['hourly']}",
        "",
        f"🏆 *Most Popular:* {popular_label}",
        "─────────────────────",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@owner_only
async def owner_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Usage: /cancelride <booking_id> [reason]  e.g. /cancelride CC-0001 Flight changed"""
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Usage: `/cancelride CC-0001 optional reason`", parse_mode="Markdown"
        )
        return
    booking_id = args[0].upper()
    booking = await asyncio.to_thread(db.get_booking_by_id, booking_id)
    if not booking:
        await update.message.reply_text(f"❌ No booking found with ID `{booking_id}`.", parse_mode="Markdown")
        return
    customer_id = booking["user_id"]
    reason = " ".join(args[1:]) if len(args) > 1 else ""
    reason_line = f"\n\n📝 *Reason:* {reason}" if reason else ""
    try:
        await ctx.bot.send_message(
            chat_id=customer_id,
            text=(
                f"❌ *Booking Cancelled*\n\n"
                f"🔖 Booking ID: `{booking_id}`\n\n"
                f"We're sorry, *{OWNER_NAME}* has had to cancel your booking."
                f"{reason_line}\n\n"
                f"Please type /start to make a new booking."
            ),
            parse_mode="Markdown"
        )
        await update.message.reply_text(
            f"✅ Cancellation sent for `{booking_id}`.", parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")


@owner_only
async def owner_broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Usage: /broadcast <message> — sends to all customers who have ever booked."""
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Usage: `/broadcast your message here`\n\n"
            "_Sends to all customers who have made at least one booking._",
            parse_mode="Markdown"
        )
        return

    message = " ".join(args)
    user_ids = await asyncio.to_thread(db.get_all_user_ids)

    if not user_ids:
        await update.message.reply_text("📋 No customers to broadcast to yet.")
        return

    sent, failed = 0, 0
    for user_id in user_ids:
        try:
            await ctx.bot.send_message(
                chat_id=user_id,
                text=(
                    f"📢 *Message from {OWNER_NAME}:*\n\n"
                    f"{message}"
                ),
                parse_mode="Markdown"
            )
            sent += 1
        except Exception as e:
            log.warning(f"Broadcast failed for {user_id}: {e}")
            failed += 1

    summary = f"✅ Broadcast sent to *{sent}* customer(s)."
    if failed:
        summary += f"\n⚠️ Failed to reach *{failed}* customer(s) (they may have blocked the bot)."
    await update.message.reply_text(summary, parse_mode="Markdown")


# ─── AVAILABILITY COMMANDS ───────────────────────────────────────────────────

@owner_only
async def set_availability(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Usage: /setavailability <date> [reason]  — block a date."""
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Usage: `/setavailability <date> [reason]`\n"
            "_(e.g. `/setavailability 25 Dec 2026 Public holiday`)_",
            parse_mode="Markdown"
        )
        return
    # First token might be part of the date — try consuming 1, 2, or 3 tokens as date
    date_obj = None
    reason_start = 0
    for n in (3, 2, 1):
        candidate = " ".join(args[:n])
        date_obj = parse_date_obj(candidate)
        if date_obj:
            reason_start = n
            break
    if not date_obj:
        await update.message.reply_text(
            "⚠️ Couldn't parse that date. Try: `25 Dec 2026` or `25/12/2026`",
            parse_mode="Markdown"
        )
        return
    reason = " ".join(args[reason_start:]) if len(args) > reason_start else ""
    await asyncio.to_thread(db.block_date, str(date_obj), reason)
    label = date_obj.strftime("%d %b %Y")
    reply = f"⛔ *{label}* marked as unavailable."
    if reason:
        reply += f"\n📝 Reason: _{reason}_"
    await update.message.reply_text(reply, parse_mode="Markdown")


@owner_only
async def block_range(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Usage: /block <start date> to <end date> [reason]
    e.g. /block 24 Dec 2026 to 2 Jan 2027 Year-end break"""
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Usage: `/block <start> to <end> [reason]`\n"
            "_(e.g. `/block 24 Dec 2026 to 2 Jan 2027 Year-end break`)_",
            parse_mode="Markdown"
        )
        return

    # Find the separator "to" in args (case-insensitive)
    try:
        sep_idx = next(i for i, a in enumerate(args) if a.lower() == "to")
    except StopIteration:
        await update.message.reply_text(
            "⚠️ Missing *to* keyword. Usage: `/block 24 Dec 2026 to 2 Jan 2027`",
            parse_mode="Markdown"
        )
        return

    start_tokens = args[:sep_idx]
    rest_tokens = args[sep_idx + 1:]

    # Parse start date — try consuming up to 3 tokens
    start_date = None
    for n in (3, 2, 1):
        if len(start_tokens) >= n:
            start_date = parse_date_obj(" ".join(start_tokens[:n]))
            if start_date:
                break
    if not start_date:
        await update.message.reply_text(
            "⚠️ Couldn't parse the *start* date. Try: `24 Dec 2026` or `24/12/2026`",
            parse_mode="Markdown"
        )
        return

    # Parse end date — try consuming up to 3 tokens from rest
    end_date = None
    reason_start = 0
    for n in (3, 2, 1):
        if len(rest_tokens) >= n:
            end_date = parse_date_obj(" ".join(rest_tokens[:n]))
            if end_date:
                reason_start = n
                break
    if not end_date:
        await update.message.reply_text(
            "⚠️ Couldn't parse the *end* date. Try: `2 Jan 2027` or `2/1/2027`",
            parse_mode="Markdown"
        )
        return

    if end_date < start_date:
        await update.message.reply_text("⚠️ End date must be on or after the start date.")
        return

    reason = " ".join(rest_tokens[reason_start:]) if len(rest_tokens) > reason_start else ""

    # Block every date in [start_date, end_date]
    from datetime import timedelta
    current = start_date
    count = 0
    while current <= end_date:
        await asyncio.to_thread(db.block_date, str(current), reason)
        current += timedelta(days=1)
        count += 1

    start_label = start_date.strftime("%d %b %Y")
    end_label   = end_date.strftime("%d %b %Y")
    reply = f"⛔ *{count} date(s)* blocked from *{start_label}* to *{end_label}*."
    if reason:
        reply += f"\n📝 Reason: _{reason}_"
    await update.message.reply_text(reply, parse_mode="Markdown")


@owner_only
async def clear_availability(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Usage: /clearavailability <date>  — unblock a date."""
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Usage: `/clearavailability <date>`\n_(e.g. `/clearavailability 25 Dec 2026`)_",
            parse_mode="Markdown"
        )
        return
    date_obj = None
    for n in (3, 2, 1):
        candidate = " ".join(args[:n])
        date_obj = parse_date_obj(candidate)
        if date_obj:
            break
    if not date_obj:
        await update.message.reply_text("⚠️ Couldn't parse that date.", parse_mode="Markdown")
        return
    deleted = await asyncio.to_thread(db.unblock_date, str(date_obj))
    label = date_obj.strftime("%d %b %Y")
    if deleted:
        await update.message.reply_text(f"✅ *{label}* is now available again.", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"ℹ️ *{label}* was not blocked.", parse_mode="Markdown")


@owner_only
async def view_availability(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """List all blocked dates."""
    blocked = await asyncio.to_thread(db.get_blocked_dates)
    if not blocked:
        await update.message.reply_text("✅ No dates are currently blocked.")
        return
    from datetime import date as date_type
    sorted_dates = sorted(blocked.items())
    lines = ["⛔ *Unavailable Dates*\n"]
    for iso, reason in sorted_dates:
        try:
            label = datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b %Y")
        except ValueError:
            label = iso
        line = f"• *{label}*"
        if reason:
            line += f" — _{reason}_"
        lines.append(line)
    lines.append("\n_Use /clearavailability <date> or /unblock <start> to <end> to unblock._")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


@owner_only
async def unblock_range(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Usage: /unblock <start date> to <end date>
    e.g. /unblock 24 Dec 2026 to 2 Jan 2027"""
    args = ctx.args
    if not args:
        await update.message.reply_text(
            "Usage: `/unblock <start> to <end>`\n"
            "_(e.g. `/unblock 24 Dec 2026 to 2 Jan 2027`)_",
            parse_mode="Markdown"
        )
        return

    try:
        sep_idx = next(i for i, a in enumerate(args) if a.lower() == "to")
    except StopIteration:
        await update.message.reply_text(
            "⚠️ Missing *to* keyword. Usage: `/unblock 24 Dec 2026 to 2 Jan 2027`",
            parse_mode="Markdown"
        )
        return

    start_tokens = args[:sep_idx]
    end_tokens = args[sep_idx + 1:]

    start_date = None
    for n in (3, 2, 1):
        if len(start_tokens) >= n:
            start_date = parse_date_obj(" ".join(start_tokens[:n]))
            if start_date:
                break
    if not start_date:
        await update.message.reply_text(
            "⚠️ Couldn't parse the *start* date. Try: `24 Dec 2026` or `24/12/2026`",
            parse_mode="Markdown"
        )
        return

    end_date = None
    for n in (3, 2, 1):
        if len(end_tokens) >= n:
            end_date = parse_date_obj(" ".join(end_tokens[:n]))
            if end_date:
                break
    if not end_date:
        await update.message.reply_text(
            "⚠️ Couldn't parse the *end* date. Try: `2 Jan 2027` or `2/1/2027`",
            parse_mode="Markdown"
        )
        return

    if end_date < start_date:
        await update.message.reply_text("⚠️ End date must be on or after the start date.")
        return

    from datetime import timedelta
    current = start_date
    removed = 0
    skipped = 0
    while current <= end_date:
        deleted = await asyncio.to_thread(db.unblock_date, str(current))
        if deleted:
            removed += 1
        else:
            skipped += 1
        current += timedelta(days=1)

    start_label = start_date.strftime("%d %b %Y")
    end_label   = end_date.strftime("%d %b %Y")
    reply = f"✅ *{removed} date(s)* unblocked from *{start_label}* to *{end_label}*."
    if skipped:
        reply += f"\n_(ℹ️ {skipped} date(s) were already available)_"
    await update.message.reply_text(reply, parse_mode="Markdown")


# ─── CANCEL COMMAND ──────────────────────────────────────────────────────────

async def cancel_mid_booking(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Catches unexpected text mid-booking and prompts the user."""
    await update.message.reply_text(
        "⚠️ You have a booking in progress.\n\n"
        "Please continue answering the questions above, or type /cancel to stop.",
    )
    return None  # stay in the current state


async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text(
        "❌ Booking cancelled. Type /start to begin again.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


# ─── FALLBACK ────────────────────────────────────────────────────────────────

async def unknown(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Type /start to book a ride or see the menu.",
    )


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set.")
    if not OWNER_CHAT_ID:
        raise RuntimeError("OWNER_CHAT_ID environment variable is not set.")

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(book_start, pattern="^book$")],
        states={
            SERVICE_TYPE:     [CallbackQueryHandler(service_chosen)],
            TRIP_DATE:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            TRIP_TIME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            PICKUP_LOCATION:  [
                CallbackQueryHandler(terminal_pickup_chosen, pattern="^terminal_pickup_T[1-4]$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_pickup),
            ],
            DROPOFF_LOCATION: [
                CallbackQueryHandler(terminal_dropoff_chosen, pattern="^terminal_dropoff_T[1-4]$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_dropoff),
            ],
            EXTRA_PICKUP:     [MessageHandler(filters.TEXT & ~filters.COMMAND, get_extra_pickup)],
            EXTRA_DROPOFF:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_extra_dropoff)],
            FLIGHT_NUMBER:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_flight)],
            HOURLY_DURATION:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_duration)],
            PAX_COUNT:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pax)],
            SPECIAL_REQUESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_requests)],
            CONFIRM_BOOKING:  [CallbackQueryHandler(confirm_booking)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
            CommandHandler("help", help_command),
            CommandHandler("confirm", owner_confirm),
            CommandHandler("reply", owner_reply),
            CommandHandler("cancelride", owner_cancel),
            CommandHandler("listbookings", owner_list_bookings),
            CommandHandler("clearbookings", owner_clear_bookings),
            CommandHandler("stats", owner_stats),
            CommandHandler("broadcast", owner_broadcast),
            CommandHandler("setavailability", set_availability),
            CommandHandler("block", block_range),
            CommandHandler("unblock", unblock_range),
            CommandHandler("clearavailability", clear_availability),
            CommandHandler("viewavailability", view_availability),
            CommandHandler("mybookings", my_bookings),
            MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_mid_booking),
        ],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^(rates|contact|menu|mybookings|help)$"))
    app.add_handler(CommandHandler("mybookings", my_bookings))
    app.add_handler(CommandHandler("confirm", owner_confirm))
    app.add_handler(CommandHandler("reply", owner_reply))
    app.add_handler(CommandHandler("cancelride", owner_cancel))
    app.add_handler(CommandHandler("listbookings", owner_list_bookings))
    app.add_handler(CommandHandler("clearbookings", owner_clear_bookings))
    app.add_handler(CommandHandler("stats", owner_stats))
    app.add_handler(CommandHandler("broadcast", owner_broadcast))
    app.add_handler(CommandHandler("setavailability", set_availability))
    app.add_handler(CommandHandler("block", block_range))
    app.add_handler(CommandHandler("unblock", unblock_range))
    app.add_handler(CommandHandler("clearavailability", clear_availability))
    app.add_handler(CommandHandler("viewavailability", view_availability))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    db.init_db()
    log.info("🚗 Chauffeur bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
