"""
OXYCODE AI - Telegram Bot (Mini App Gateway + Admin Panel)
==========================================================

Bot that:
1. Works for all users - saves to database on /start
2. Shows "Open Mini App" button after channel verification
3. /admin panel with maintenance toggle (admin only)
4. Maintenance mode blocks all users when enabled
"""

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
    MessageEntity,
)
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
import database as db
import asyncio
import logging
import datetime
from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    AGENT_NAME,
    WELCOME_MESSAGE,
)

logger = logging.getLogger(__name__)

# Mini App URL - deployed on Vercel
MINI_APP_URL = "https://oxycode-miniapp.vercel.app"

# Maintenance message shown to all users when maintenance is ON
MAINTENANCE_MSG = (
    "\U0001f527 <b>Bot Under Maintenance</b>\n\n"
    "The bot is currently being updated. Please try again later.\n\n"
    "<i>If you are an admin, use /admin to manage maintenance mode.</i>"
)


# ==================== HELPERS ====================

def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in ADMIN_IDS


def is_maintenance_mode() -> bool:
    """Check if bot is in maintenance mode."""
    return db.get_maintenance_mode()


async def notify_admins(bot, text: str):
    """Send a message to all admins."""
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode=ParseMode.HTML)
        except Exception:
            pass


# ==================== CHANNEL VERIFICATION ====================

async def check_channel_membership(user_id, context):
    """Check if user is a member of all required channels."""
    channels = db.get_channels()
    if not channels:
        return True, []

    not_joined = []
    for ch in channels:
        try:
            member = await context.bot.get_chat_member(ch["channel_id"], user_id)
            if member.status in ("left", "kicked"):
                not_joined.append(ch)
        except Exception as e:
            logger.warning(f"Channel check failed for {ch['channel_id']}: {e}")
            not_joined.append(ch)
    return len(not_joined) == 0, not_joined


def get_force_join_keyboard(not_joined):
    """Build inline keyboard with channel join buttons + 'I Joined' check."""
    btns = []
    for ch in not_joined:
        name = ch.get("name", "Channel")
        link = ch.get("link", f"https://t.me/{ch['channel_id'].replace('@', '')}")
        btns.append([InlineKeyboardButton(f"Join {name}", url=link)])
    btns.append([InlineKeyboardButton("I Joined ?", callback_data="check_joined")])
    return InlineKeyboardMarkup(btns)


# ==================== CALLBACK HANDLERS ====================

async def check_joined_callback(update, context):
    """Handle 'I Joined ?' callback - re-verify membership."""
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    # Maintenance check
    if is_maintenance_mode() and not is_admin(uid):
        await query.edit_message_text(MAINTENANCE_MSG, parse_mode=ParseMode.HTML)
        return

    joined, not_joined = await check_channel_membership(uid, context)
    if not joined:
        await query.edit_message_text(
            f"**{AGENT_NAME}**\n\nJoin all required channels to continue:",
            reply_markup=get_force_join_keyboard(not_joined),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # All channels joined - show Mini App button
    await query.edit_message_text(
        WELCOME_MESSAGE,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "\U0001f44c Open Mini App",
                web_app=WebAppInfo(url=MINI_APP_URL),
            )],
        ]),
    )


async def apply_referral(uid, context):
    """Apply pending referral if user just joined channels."""
    user_state = db.get_user_state(uid)
    if not user_state:
        return
    pending = user_state.get("state", "")
    data = user_state.get("data", "")
    if pending == "pending_ref" and data:
        referrer_id = db.resolve_referral_code(data)
        if referrer_id and referrer_id != uid:
            db.credit_referral(referrer_id, uid)
            db.clear_user_state(uid)
            try:
                await context.bot.send_message(
                    referrer_id,
                    f"\U0001f389 **New Referral!**\n\nSomeone joined using your code!",
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass


# ==================== START COMMAND ====================

async def start_command(update: Update, context):
    """/start - Register user, verify channels, show Mini App button."""
    user = update.effective_user
    uid = user.id

    # ALWAYS save user to DB first (even during maintenance)
    is_new_user = db.add_user(uid, user.username, user.first_name, user.last_name)
    u = db.get_user(uid)

    # Notify admins of new user
    if is_new_user:
        try:
            asyncio.create_task(notify_admin_new_user(context.bot, user))
        except Exception as e:
            logger.error(f"notify_admin_new_user sched failed: {e}")

    # No maintenance block here — /start always shows welcome.
    # The Mini App frontend handles maintenance display.

    if u and u.get("is_banned"):
        await update.message.reply_text("You are banned.")
        return

    # Handle referral deep-link: /start ref_ABC123
    if context.args:
        arg = context.args[0].strip()
        if arg.lower().startswith("ref_"):
            code = arg[4:].strip().upper()
            if code and not (u and u.get("referred_by")):
                db.set_user_state(uid, "pending_ref", data=code)

    # Channel verification
    joined, not_joined = await check_channel_membership(uid, context)
    if not joined:
        await update.message.reply_text(
            f"**{AGENT_NAME}**\n\nJoin all required channels to continue:",
            reply_markup=get_force_join_keyboard(not_joined),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # All channels joined - show Mini App button
    await apply_referral(uid, context)
    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "\U0001f44c Open Mini App",
                web_app=WebAppInfo(url=MINI_APP_URL),
            )],
        ]),
    )


async def notify_admin_new_user(bot, user):
    """Notify admins when a new user starts the bot."""
    total = db.get_user_count()
    name = user.first_name or (user.username or "unknown")
    uname = f"@{user.username}" if user.username else ""
    text = (
        f"<b>\U0001f464 New User #{total}</b>\n\n"
        f"<b>Name:</b> {name} {uname}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Total Users:</b> {total}"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode=ParseMode.HTML)
        except Exception:
            pass


# ==================== ADMIN PANEL ====================

async def admin_command(update: Update, context):
    """/admin - Admin panel with stats and controls."""
    uid = update.effective_user.id

    if not is_admin(uid):
        await update.message.reply_text(
            "\U0001f6ab <b>Admin Only</b>\n\nYou don't have access to this command.",
            parse_mode=ParseMode.HTML,
        )
        return

    total_users = db.get_user_count()
    maintenance = is_maintenance_mode()
    daily_limit = db.get_daily_limit()

    maint_status = "\u2705 ON" if maintenance else "\u274c OFF"
    maint_btn_text = "\u274c Turn Maintenance OFF" if maintenance else "\u2705 Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"

    text = (
        f"\U0001f680 <b>{AGENT_NAME} Admin Panel</b>\n\n"
        f"<b>\U0001f4ca Stats:</b>\n"
        f"  Total Users: <code>{total_users}</code>\n"
        f"  Daily Limit: <code>{daily_limit}</code> msgs/user\n"
        f"  Maintenance: {maint_status}\n\n"
        f"<b>\U0001f527 Controls:</b>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"\U0001f4b3 Change Rate Limit (now: {daily_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("\U0001f504 Refresh Stats", callback_data="admin_refresh")],
    ])

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def toggle_maintenance_callback(update: Update, context):
    """Handle maintenance toggle button."""
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if not is_admin(uid):
        await query.answer("\U0001f6ab Admin only!", show_alert=True)
        return

    new_state = db.toggle_maintenance()
    maintenance = is_maintenance_mode()

    total_users = db.get_user_count()
    daily_limit = db.get_daily_limit()

    maint_status = "\u2705 ON" if maintenance else "\u274c OFF"
    maint_btn_text = "\u274c Turn Maintenance OFF" if maintenance else "\u2705 Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"

    text = (
        f"\U0001f680 <b>{AGENT_NAME} Admin Panel</b>\n\n"
        f"<b>\U0001f4ca Stats:</b>\n"
        f"  Total Users: <code>{total_users}</code>\n"
        f"  Daily Limit: <code>{daily_limit}</code> msgs/user\n"
        f"  Maintenance: {maint_status}\n\n"
        f"<b>\U0001f527 Controls:</b>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"\U0001f4b3 Change Rate Limit (now: {daily_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("\U0001f504 Refresh Stats", callback_data="admin_refresh")],
    ])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    status_text = "ENABLED" if maintenance else "DISABLED"
    await query.answer(f"Maintenance mode {status_text}!", show_alert=True)


async def admin_refresh_callback(update: Update, context):
    """Handle refresh stats button."""
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if not is_admin(uid):
        await query.answer("\U0001f6ab Admin only!", show_alert=True)
        return

    total_users = db.get_user_count()
    daily_limit = db.get_daily_limit()
    maintenance = is_maintenance_mode()

    maint_status = "\u2705 ON" if maintenance else "\u274c OFF"
    maint_btn_text = "\u274c Turn Maintenance OFF" if maintenance else "\u2705 Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"

    text = (
        f"\U0001f680 <b>{AGENT_NAME} Admin Panel</b>\n\n"
        f"<b>\U0001f4ca Stats:</b>\n"
        f"  Total Users: <code>{total_users}</code>\n"
        f"  Daily Limit: <code>{daily_limit}</code> msgs/user\n"
        f"  Maintenance: {maint_status}\n\n"
        f"<b>\U0001f527 Controls:</b>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"\U0001f4b3 Change Rate Limit (now: {daily_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("\U0001f504 Refresh Stats", callback_data="admin_refresh")],
    ])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    await query.answer("Stats refreshed!")


async def admin_rate_limit_callback(update: Update, context):
    """Handle rate limit change button - ask admin to send new value."""
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if not is_admin(uid):
        await query.answer("\U0001f6ab Admin only!", show_alert=True)
        return

    current_limit = db.get_daily_limit()

    await query.edit_message_text(
        f"\U0001f4b3 <b>Change Rate Limit</b>\n\n"
        f"Current limit: <code>{current_limit}</code> msgs/24h\n\n"
        f"Send the new limit value (1-10000):",
        parse_mode=ParseMode.HTML,
    )

    db.set_user_state(uid, "waiting_for_rate_limit")


async def handle_admin_rate_limit_input(update: Update, context):
    """Handle admin sending new rate limit value."""
    uid = update.effective_user.id

    if not is_admin(uid):
        return False

    user_state = db.get_user_state(uid)
    if not user_state or user_state.get("state") != "waiting_for_rate_limit":
        return False

    text = update.message.text.strip()

    try:
        new_limit = int(text)
    except ValueError:
        await update.message.reply_text(
            "\u274c Invalid input. Please send a number (1-10000):",
            parse_mode=ParseMode.HTML,
        )
        return True

    if new_limit < 1 or new_limit > 10000:
        await update.message.reply_text(
            "\u274c Value must be between 1 and 10000. Send a valid number:",
            parse_mode=ParseMode.HTML,
        )
        return True

    db.set_setting("daily_limit", str(new_limit))
    db.clear_user_state(uid)

    total_users = db.get_user_count()
    maintenance = is_maintenance_mode()

    maint_status = "\u2705 ON" if maintenance else "\u274c OFF"
    maint_btn_text = "\u274c Turn Maintenance OFF" if maintenance else "\u2705 Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"

    text_msg = (
        f"\u2705 <b>Daily limit updated to {new_limit} msgs/24h</b>\n\n"
        f"\U0001f680 <b>{AGENT_NAME} Admin Panel</b>\n\n"
        f"<b>\U0001f4ca Stats:</b>\n"
        f"  Total Users: <code>{total_users}</code>\n"
        f"  Daily Limit: <code>{new_limit}</code> msgs/user\n"
        f"  Maintenance: {maint_status}\n\n"
        f"<b>\U0001f527 Controls:</b>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"\U0001f4b3 Change Rate Limit (now: {new_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("\U0001f504 Refresh Stats", callback_data="admin_refresh")],
    ])

    await update.message.reply_text(text_msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    return True


# ==================== FALLBACK HANDLERS ====================

async def handle_text(update: Update, context):
    """Handle plain text - show Mini App button or maintenance message."""
    uid = update.effective_user.id

    user_state = db.get_user_state(uid)
    if user_state and user_state.get("state") == "waiting_for_rate_limit":
        return

    # Save user to DB if not exists
    u = db.get_user(uid)
    if not u:
        db.add_user(uid, update.effective_user.username, update.effective_user.first_name, update.effective_user.last_name)
        u = db.get_user(uid)

    # No maintenance block here — always show Mini App button.
    # The Mini App frontend handles maintenance display.

    await update.message.reply_text(
        "Use /start to open the Mini App \U0001f44c",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "\U0001f44c Open Mini App",
                web_app=WebAppInfo(url=MINI_APP_URL),
            )],
        ]),
    )


# ==================== MAIN ====================

def main():
    """Start the bot."""
    db.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(check_joined_callback, pattern="^check_joined$"))
    app.add_handler(CallbackQueryHandler(toggle_maintenance_callback, pattern="^toggle_maintenance_(on|off)$"))
    app.add_handler(CallbackQueryHandler(admin_rate_limit_callback, pattern="^admin_rate_limit$"))
    app.add_handler(CallbackQueryHandler(admin_refresh_callback, pattern="^admin_refresh$"))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_admin_rate_limit_input,
        block=False,
    ))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info(f"\U0001f680 {AGENT_NAME} bot started (Mini App gateway + admin panel mode)")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()