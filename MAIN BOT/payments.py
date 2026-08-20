"""
OXYGENT — Telegram Stars Payment System
=======================================

Handles in-app purchases using Telegram's Stars (XTR) currency.

Payment Flow:
    1. User taps "Buy Credits" → shows package options
    2. User selects package → bot sends invoice
    3. User confirms payment → Telegram processes Stars
    4. Bot receives PreCheckoutQuery → approves
    5. Bot receives SuccessfulPayment → credits user account

Credit Packages:
    - 3 Stars   = 10 Credits   (3.33 Stars/credit)
    - 10 Stars  = 35 Credits   (2.86 Stars/credit)
    - 30 Stars  = 120 Credits  (2.50 Stars/credit)
    - 100 Stars = 400 Credits  (2.50 Stars/credit)
    - 300 Stars = 1500 Credits (2.00 Stars/credit)

Idempotency:
    - payment_exists() checks charge_id uniqueness
    - ON CONFLICT DO NOTHING prevents double-credit

Author: OXYCODE TEAM
"""
from telegram import (
    LabeledPrice,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ParseMode

import database as db

STAR_PACKAGES = [
    {"stars": 3, "credits": 10, "label": "10 Credits - 3 Stars"},
    {"stars": 10, "credits": 35, "label": "35 Credits - 10 Stars"},
    {"stars": 30, "credits": 120, "label": "120 Credits - 30 Stars"},
    {"stars": 100, "credits": 400, "label": "400 Credits - 100 Stars"},
    {"stars": 300, "credits": 1500, "label": "1500 Credits - 300 Stars"},
]


def get_buy_keyboard():
    buttons = [
        [InlineKeyboardButton("10 Credits - 3 Stars", callback_data="buy_3", style="success"),
         InlineKeyboardButton("35 Credits - 10 Stars", callback_data="buy_10", style="success")],
        [InlineKeyboardButton("120 Credits - 30 Stars", callback_data="buy_30", style="success"),
         InlineKeyboardButton("400 Credits - 100 Stars", callback_data="buy_100", style="success")],
        [InlineKeyboardButton("1500 Credits - 300 Stars", callback_data="buy_300", style="success")],
        [InlineKeyboardButton("Cancel", callback_data="buy_cancel", style="danger")]
    ]
    return InlineKeyboardMarkup(buttons)


async def send_buy_menu(update, context):
    text = (
        "**Buy Credits with Telegram Stars**\n\n"
        "Select a package below. You'll pay with **Telegram Stars**.\n"
        "Credits are used for AI requests.\n\n"
        "**1 Credit = 1 message** to the bot."
    )
    if hasattr(update, "callback_query") and update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=get_buy_keyboard(), parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            text, reply_markup=get_buy_keyboard(), parse_mode=ParseMode.MARKDOWN
        )


async def send_invoice_for_package(update, context, stars):
    pkg = next((p for p in STAR_PACKAGES if p["stars"] == stars), None)
    if not pkg:
        return
    user_id = update.effective_user.id
    prices = [LabeledPrice(label=f"{pkg['credits']} Credits", amount=stars)]
    payload = f"credit_{pkg['credits']}:{user_id}"

    await context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=f"{pkg['credits']} Credits",
        description=f"Get {pkg['credits']} OXYGENT credits. Pay {stars} Telegram Stars.",
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token="",
    )


async def handle_pre_checkout(update, context):
    query = update.pre_checkout_query
    await query.answer(ok=True)


async def handle_successful_payment(update, context):
    payment = update.message.successful_payment
    stars = payment.total_amount
    charge_id = payment.telegram_payment_charge_id
    payload = payment.invoice_payload
    user_id = update.effective_user.id

    if db.payment_exists(charge_id):
        await update.message.reply_text("Payment already processed.")
        return

    try:
        credits = int(payload.split(":")[0].replace("credit_", ""))
    except Exception:
        credits = 0

    db.save_payment(user_id, charge_id, payload, stars, credits)
    db.add_bonus_messages(user_id, credits)

    await update.message.reply_text(
        f"**Payment Successful!**\n\n"
        f"Paid: `{stars}` Stars\n"
        f"Credits Added: `{credits}`\n\n"
        f"Use them for AI requests!",
        parse_mode=ParseMode.MARKDOWN,
    )
