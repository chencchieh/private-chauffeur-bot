"""
╔══════════════════════════════════════════════════════════════╗
║        Private Chauffeur Booking Bot — Chih Chieh Chen       ║
║        Telegram Bot · Singapore                               ║
╚══════════════════════════════════════════════════════════════╝

Setup:
  1. pip install python-telegram-bot==20.7
  2. Set BOT_TOKEN and OWNER_CHAT_ID in config below
  3. python bot.py

Deploy free on Railway.app or Render.com
"""

import logging
import os
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes, filters
)

# ─── CONFIG ──────────────────────────────────────────────────────────────────

BOT_TOKEN     = os.getenv("BOT_TOKEN", "8775062704:AAECicVjCh5rhBVerM2ogSZswsTXvZ1goq4")
OWNER_CHAT_ID = os.getenv("OWNER_CHAT_ID", "715863208")
# To get your Chat ID: message @userinfobot on Telegram

OWNER_NAME    = "Chih Chieh"
BUSINESS_URL  = "https://private-chauffeur.netlify.app"
WHATSAPP_NUM  = "6581272450"

RATES = {
    "airport_arrival":   90,
    "airport_departure": 80,
    "hourly":            80,
}

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
) = range(10)

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
    svc = service_label(data.get("service", ""))
    lines = [
        "📋 *Booking Summary*",
        "─────────────────────",
        f"🚗 *Service:* {svc}",
        f"📅 *Date:* {data.get('date', '—')}",
        f"🕐 *Time:* {data.get('time', '—')}",
        f"📍 *Pick-up:* {data.get('pickup', '—')}",
        f"🏁 *Drop-off:* {data.get('dropoff', '—')}",
    ]
    if data.get("service") in ("airport_arrival", "airport_departure"):
        lines.append(f"✈️ *Flight No:* {data.get('flight', 'Not provided')}")
    if data.get("service") == "hourly":
        dur = data.get("duration", "—")
        total = RATES["hourly"] * int(dur) if str(dur).isdigit() else "—"
        lines.append(f"⏳ *Duration:* {dur} hrs")
        lines.append(f"💵 *Est. Total:* S${total}")
    else:
        rate = RATES.get(data.get("service", ""), "—")
        lines.append(f"💵 *Rate:* S${rate}")
    lines.append(f"👥 *Passengers:* {data.get('pax', '—')}")
    if data.get("requests"):
        lines.append(f"📝 *Requests:* {data.get('requests')}")
    lines.append("─────────────────────")
    lines.append("🚙 *Vehicle:* Toyota Voxy / Noah (→ Noah from Jun 2026)")
    lines.append("📍 *Area:* Singapore & cross-border JB")
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
        [InlineKeyboardButton("📞 Contact Chih Chieh", callback_data="contact")],
        [InlineKeyboardButton("🌐 View Business Card", url=BUSINESS_URL)],
    ]
    await update.message.reply_text(
        welcome,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def main_menu_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "rates":
        text = (
            "💰 *My Rates (SGD)*\n"
            "─────────────────────\n"
            "✈️ *Airport Arrival* — S$90\n"
            "   _(Pick-up from Changi)_\n\n"
            "🛫 *Airport Departure* — S$80\n"
            "   _(Drop-off to Changi)_\n\n"
            "⏱️ *Hourly Charter* — S$80/hr\n"
            "   _(Minimum 2 hours)_\n\n"
            "─────────────────────\n"
            "🚙 Toyota Voxy / Noah · 4–5 pax\n"
            "📌 ERP & parking charges extra\n"
            "🛣️ Cross-border JB available"
        )
        keyboard = [[InlineKeyboardButton("📅 Book Now", callback_data="book"),
                     InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]]
        await q.edit_message_text(text, parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup(keyboard))

    elif q.data == "contact":
        text = (
            "📞 *Contact Chih Chieh*\n"
            "─────────────────────\n"
            f"💬 WhatsApp: wa.me/{WHATSAPP_NUM}\n"
            f"✈️ Telegram: +65 8127 2450\n\n"
            "Or simply book directly through this bot! 👇"
        )
        keyboard = [[InlineKeyboardButton("📅 Book Now", callback_data="book"),
                     InlineKeyboardButton("🏠 Main Menu", callback_data="menu")]]
        await q.edit_message_text(text, parse_mode="Markdown",
                                   reply_markup=InlineKeyboardMarkup(keyboard))

    elif q.data == "menu":
        await q.edit_message_text(
            "🏠 *Main Menu* — what would you like to do?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 Book a Ride", callback_data="book")],
                [InlineKeyboardButton("💰 View Rates",  callback_data="rates")],
                [InlineKeyboardButton("📞 Contact Chih Chieh", callback_data="contact")],
                [InlineKeyboardButton("🌐 Business Card", url=BUSINESS_URL)],
            ])
        )


# ─── BOOKING FLOW ────────────────────────────────────────────────────────────

async def book_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Entry point — choose service type."""
    q = update.callback_query
    await q.answer()
    ctx.user_data.clear()

    keyboard = [
        [InlineKeyboardButton("✈️ Airport Arrival (Pick-up)  S$90",  callback_data="airport_arrival")],
        [InlineKeyboardButton("🛫 Airport Departure (Drop-off)  S$80", callback_data="airport_departure")],
        [InlineKeyboardButton("⏱️ Hourly Charter  S$80/hr",           callback_data="hourly")],
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
    ctx.user_data["date"] = date_text
    await update.message.reply_text(
        f"📅 Date: *{date_text}*\n\n"
        "🕐 What time do you need the car?\n"
        "_(e.g. 8:00 AM or 14:30)_",
        parse_mode="Markdown"
    )
    return TRIP_TIME


async def get_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["time"] = update.message.text.strip()
    svc = ctx.user_data.get("service")

    if svc == "airport_arrival":
        await update.message.reply_text(
            "📍 *Pick-up location:*\n_(e.g. Changi Airport Terminal 3 — Arrival Hall)_",
            parse_mode="Markdown"
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


async def get_pickup(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["pickup"] = update.message.text.strip()
    svc = ctx.user_data.get("service")

    if svc == "airport_arrival":
        await update.message.reply_text(
            "🏁 *Drop-off location:*\n_(e.g. 12 Marina Boulevard, CBD)_",
            parse_mode="Markdown"
        )
    elif svc == "airport_departure":
        await update.message.reply_text(
            "🏁 *Drop-off location:*\n_(e.g. Changi Airport Terminal 1 — Departure)_",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "🏁 *Drop-off / final destination:*\n_(or type 'Multiple stops' if needed)_",
            parse_mode="Markdown"
        )
    return DROPOFF_LOCATION


async def get_dropoff(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["dropoff"] = update.message.text.strip()
    svc = ctx.user_data.get("service")

    if svc in ("airport_arrival", "airport_departure"):
        await update.message.reply_text(
            "✈️ *Flight number?*\n_(e.g. SQ321 — helps me track delays)_\n"
            "Or type *skip* if you don't have it yet.",
            parse_mode="Markdown"
        )
        return FLIGHT_NUMBER
    elif svc == "hourly":
        await update.message.reply_text(
            "⏳ *How many hours do you need?*\n_(Minimum 2 hours — e.g. type 3)_",
            parse_mode="Markdown"
        )
        return HOURLY_DURATION
    else:
        await update.message.reply_text(
            "👥 *How many passengers?* (max 4–5)\n_(e.g. 2)_",
            parse_mode="Markdown"
        )
        return PAX_COUNT


async def get_flight(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    ctx.user_data["flight"] = "—" if text.lower() == "skip" else text
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
    ctx.user_data["pax"] = update.message.text.strip()
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

    # Show summary for confirmation
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

    # ── CONFIRMED ──
    user = q.from_user
    data = ctx.user_data
    summary = build_summary(data)

    # 1. Thank the customer
    await q.edit_message_text(
        f"🎉 *Booking Confirmed!*\n\n"
        f"{summary}\n\n"
        f"✅ Your request has been sent to *{OWNER_NAME}*.\n"
        f"He will confirm via Telegram shortly.\n\n"
        f"📱 You can also reach him on WhatsApp:\n"
        f"wa.me/{WHATSAPP_NUM}",
        parse_mode="Markdown"
    )

    # 2. Notify the owner
    owner_msg = (
        f"🔔 *New Booking Request!*\n\n"
        f"{summary}\n\n"
        f"─────────────────────\n"
        f"👤 *Customer:* {user.full_name}\n"
        f"🆔 Username: @{user.username or 'N/A'}\n"
        f"🔑 Chat ID: `{user.id}`\n\n"
        f"Reply to this chat to contact the customer directly."
    )
    try:
        await ctx.bot.send_message(
            chat_id=OWNER_CHAT_ID,
            text=owner_msg,
            parse_mode="Markdown"
        )
        # Send a deep link so owner can reply to customer instantly
        await ctx.bot.send_message(
            chat_id=OWNER_CHAT_ID,
            text=f"💬 [Reply to customer](tg://user?id={user.id})",
            parse_mode="Markdown"
        )
    except Exception as e:
        log.error(f"Failed to notify owner: {e}")

    return ConversationHandler.END


# ─── CANCEL COMMAND ──────────────────────────────────────────────────────────

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
    app = Application.builder().token(BOT_TOKEN).build()

    # Booking conversation
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(book_start, pattern="^book$")],
        states={
            SERVICE_TYPE:     [CallbackQueryHandler(service_chosen)],
            TRIP_DATE:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_date)],
            TRIP_TIME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            PICKUP_LOCATION:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pickup)],
            DROPOFF_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_dropoff)],
            FLIGHT_NUMBER:    [MessageHandler(filters.TEXT & ~filters.COMMAND, get_flight)],
            HOURLY_DURATION:  [MessageHandler(filters.TEXT & ~filters.COMMAND, get_duration)],
            PAX_COUNT:        [MessageHandler(filters.TEXT & ~filters.COMMAND, get_pax)],
            SPECIAL_REQUESTS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_requests)],
            CONFIRM_BOOKING:  [CallbackQueryHandler(confirm_booking)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(main_menu_callback, pattern="^(rates|contact|menu)$"))
    app.add_handler(conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    log.info("🚗 Chauffeur bot is running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
