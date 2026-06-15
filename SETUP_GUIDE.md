# 🚗 Chih Chieh Chauffeur Bot — Setup Guide

## What this bot does
- Customers can book Airport Arrival, Departure, or Hourly rides
- Bot collects date, time, pickup, dropoff, flight number, passengers
- Shows a full booking summary for customer to confirm
- Sends you (the owner) an instant Telegram notification with all details
- Includes a one-tap link for you to reply directly to the customer

---

## Step 1 — Get your Bot Token

1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Choose a name: `Chih Chieh Chauffeur`
4. Choose a username: `ChihChiehChauffeurBot` (must end in "bot")
5. BotFather sends you a token like: `7123456789:AAFxxxxxxx`
6. Copy it — this is your `BOT_TOKEN`

---

## Step 2 — Get your Chat ID

1. Open Telegram → search **@userinfobot**
2. Send `/start`
3. It replies with your ID like: `Id: 987654321`
4. Copy it — this is your `OWNER_CHAT_ID`

---

## Step 3 — Deploy FREE on Railway.app (easiest)

1. Go to **railway.app** → sign up free with GitHub
2. Click **New Project → Deploy from GitHub repo**
   - Upload the 3 files (bot.py, requirements.txt, .env.example)
   - Or use GitHub Desktop to push them to a repo first
3. In Railway dashboard → click your project → **Variables** tab
4. Add two variables:
   ```
   BOT_TOKEN     = 7123456789:AAFxxxxxxx
   OWNER_CHAT_ID = 987654321
   ```
5. Click **Deploy** — your bot goes live in ~60 seconds!

---

## Step 4 — Set up bot commands (optional but nice)

Send this to @BotFather to give your bot a clean menu:

```
/setcommands
```
Then select your bot and paste:
```
start - 🏠 Main menu & booking
cancel - ❌ Cancel current booking
```

---

## Step 5 — Test it

1. Search your bot username on Telegram
2. Send `/start`
3. Tap **Book a Ride**
4. Complete the flow
5. You should receive a notification on your Telegram instantly ✅

---

## Booking flow (what customers see)

```
/start
  └── 📅 Book a Ride
        └── Choose service:
              ✈️ Airport Arrival  S$90
              🛫 Airport Departure S$80
              ⏱️ Hourly Charter   S$80/hr
                  └── Date → Time → Pickup → Dropoff
                        └── Flight No (if airport)
                              └── Duration (if hourly)
                                    └── Passengers
                                          └── Special requests
                                                └── Confirm ✅
                                                      └── You get notified! 🔔
```

---

## Files included

| File | Purpose |
|------|---------|
| `bot.py` | Main bot code |
| `requirements.txt` | Python packages needed |
| `.env.example` | Template for your secret keys |

---

## Need help?

Ask Chih Chieh or open the bot code in any text editor.
The only two things you ever need to change are `BOT_TOKEN` and `OWNER_CHAT_ID`.
