"""
OXYCODE AI — Telegram Bot (Mini App Gateway + Admin Panel)
==========================================================

Bot that:
1. Only works for admin IDs (8972944701, 7371674958) — others get maintenance message
2. Shows "Open Mini App" button for admins
3. /admin panel with maintenance toggle
4. Maintenance mode blocks all non-admin users
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

# Mini App URL — deployed on Vercel
MINI_APP_URL = "https://oxycode-miniapp.vercel.app"

# Maintenance message shown to non-admin users
MAINTENANCE_MSG = (
    "🔧 <b>Bot Under Maintenance</b>\n\n"
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


def _entities_to_list(entities):
    """Serialize MessageEntity objects to JSON-serializable dicts."""
    if not entities:
        return None
    out = []
    for e in entities:
        try:
            out.append(e.to_dict())
        except Exception:
            d = {"type": e.type, "offset": e.offset, "length": e.length}
            if getattr(e, "url", None):
                d["url"] = e.url
            if getattr(e, "language", None):
                d["language"] = e.language
            if getattr(e, "custom_emoji_id", None):
                d["custom_emoji_id"] = e.custom_emoji_id
            out.append(d)
    return out


def _list_to_entities(lst):
    """Rebuild MessageEntity objects from stored dicts."""
    if not lst:
        return None
    return [MessageEntity.de_json(d) for d in lst]


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
    btns.append([InlineKeyboardButton("I Joined ✅", callback_data="check_joined")])
    return InlineKeyboardMarkup(btns)


# ==================== CALLBACK HANDLERS ====================

async def check_joined_callback(update, context):
    """Handle 'I Joined ✅' callback — re-verify membership."""
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    # Maintenance check
    if is_maintenance_mode() and not is_admin(uid):
        await query.edit_message_text(MAINTENANCE_MSG, parse_mode=ParseMode.HTML)
        return

    # Non-admin blocked
    if not is_admin(uid):
        await query.edit_message_text(
            "⛔ <b>Access Denied</b>\n\nThis bot is currently in private beta.",
            parse_mode=ParseMode.HTML,
        )
        return

    joined, not_joined = await check_channel_membership(uid, context)
    if not joined:
        await query.edit_message_text(
            f"**{AGENT_NAME}**\n\nJoin all required channels to continue:",
            reply_markup=get_force_join_keyboard(not_joined),
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    # All channels joined — show Mini App button
    await query.edit_message_text(
        WELCOME_MESSAGE,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🚀 Open Mini App",
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
                    f"🎉 **New Referral!**\n\nSomeone joined using your code!",
                    parse_mode=ParseMode.MARKDOWN,
                )
            except Exception:
                pass


# ==================== START COMMAND ====================

async def start_command(update: Update, context):
    """/start — Register user, verify channels, show Mini App button."""
    user = update.effective_user
    uid = user.id

    # Admin-only restriction
    if not is_admin(uid):
        if is_maintenance_mode():
            await update.message.reply_text(MAINTENANCE_MSG, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(
                "⛔ <b>Access Denied</b>\n\nThis bot is currently in private beta.",
                parse_mode=ParseMode.HTML,
            )
        return

    is_new_user = db.add_user(uid, user.username, user.first_name, user.last_name)
    u = db.get_user(uid)

    if u and u.get("is_banned"):
        await update.message.reply_text("You are banned.")
        return

    # Admin notification for new users
    if is_new_user:
        try:
            asyncio.create_task(notify_admin_new_user(context.bot, user))
        except Exception as e:
            logger.error(f"notify_admin_new_user sched failed: {e}")

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

    # All channels joined — show Mini App button
    await apply_referral(uid, context)
    await update.message.reply_text(
        WELCOME_MESSAGE,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🚀 Open Mini App",
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
        f"<b>🆕 New User #{total}</b>\n\n"
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
    """/admin — Admin panel with stats and controls."""
    uid = update.effective_user.id

    if not is_admin(uid):
        await update.message.reply_text(
            "⛔ <b>Admin Only</b>\n\nYou don't have access to this command.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Get stats
    total_users = db.get_user_count()
    maintenance = is_maintenance_mode()
    daily_limit = db.get_daily_limit()

    # Build admin panel
    maint_status = "🟢 ON" if maintenance else "🔴 OFF"
    maint_btn_text = "🔴 Turn Maintenance OFF" if maintenance else "🟢 Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"

    text = (
        f"🛡 <b>{AGENT_NAME} Admin Panel</b>\n\n"
        f"<b>📊 Stats:</b>\n"
        f"• Total Users: <code>{total_users}</code>\n"
        f"• Daily Limit: <code>{daily_limit}</code> msgs/user\n"
        f"• Maintenance: {maint_status}\n\n"
        f"<b>🔧 Controls:</b>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"⚙️ Change Rate Limit (now: {daily_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("📊 Refresh Stats", callback_data="admin_refresh")],
    ])

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def toggle_maintenance_callback(update: Update, context):
    """Handle maintenance toggle button."""
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if not is_admin(uid):
        await query.answer("⛔ Admin only!", show_alert=True)
        return

    # Toggle maintenance mode
    new_state = db.toggle_maintenance()
    maintenance = is_maintenance_mode()

    # Build new admin panel
    total_users = db.get_user_count()
    daily_limit = db.get_daily_limit()

    maint_status = "🟢 ON" if maintenance else "🔴 OFF"
    maint_btn_text = "🔴 Turn Maintenance OFF" if maintenance else "🟢 Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"

    text = (
        f"🛡 <b>{AGENT_NAME} Admin Panel</b>\n\n"
        f"<b>📊 Stats:</b>\n"
        f"• Total Users: <code>{total_users}</code>\n"
        f"• Daily Limit: <code>{daily_limit}</code> msgs/user\n"
        f"• Maintenance: {maint_status}\n\n"
        f"<b>🔧 Controls:</b>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"⚙️ Change Rate Limit (now: {daily_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("📊 Refresh Stats", callback_data="admin_refresh")],
    ])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # Notify admin
    status_text = "ENABLED" if maintenance else "DISABLED"
    await query.answer(f"Maintenance mode {status_text}!", show_alert=True)


async def admin_refresh_callback(update: Update, context):
    """Handle refresh stats button."""
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if not is_admin(uid):
        await query.answer("⛔ Admin only!", show_alert=True)
        return

    # Rebuild admin panel with fresh stats
    total_users = db.get_user_count()
    daily_limit = db.get_daily_limit()
    maintenance = is_maintenance_mode()

    maint_status = "🟢 ON" if maintenance else "🔴 OFF"
    maint_btn_text = "🔴 Turn Maintenance OFF" if maintenance else "🟢 Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"

    text = (
        f"🛡 <b>{AGENT_NAME} Admin Panel</b>\n\n"
        f"<b>📊 Stats:</b>\n"
        f"• Total Users: <code>{total_users}</code>\n"
        f"• Daily Limit: <code>{daily_limit}</code> msgs/user\n"
        f"• Maintenance: {maint_status}\n\n"
        f"<b>🔧 Controls:</b>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"⚙️ Change Rate Limit (now: {daily_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("📊 Refresh Stats", callback_data="admin_refresh")],
    ])

    await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    await query.answer("Stats refreshed!")


async def admin_rate_limit_callback(update: Update, context):
    """Handle rate limit change button — ask admin to send new value."""
    query = update.callback_query
    uid = query.from_user.id
    await query.answer()

    if not is_admin(uid):
        await query.answer("⛔ Admin only!", show_alert=True)
        return

    current_limit = db.get_daily_limit()

    await query.edit_message_text(
        f"⚙️ <b>Change Rate Limit</b>\n\n"
        f"Current limit: <code>{current_limit}</code> msgs/24h\n\n"
        f"Send the new limit value (1-10000):",
        parse_mode=ParseMode.HTML,
    )

    # Set user state to waiting for limit value
    db.set_user_state(uid, "waiting_for_rate_limit")


async def handle_admin_rate_limit_input(update: Update, context):
    """Handle admin sending new rate limit value."""
    uid = update.effective_user.id

    if not is_admin(uid):
        return False  # not handled

    # Check if admin is waiting for rate limit input
    user_state = db.get_user_state(uid)
    if not user_state or user_state.get("state") != "waiting_for_rate_limit":
        return False  # not in rate limit flow

    text = update.message.text.strip()

    # Validate input
    try:
        new_limit = int(text)
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid input. Please send a number (1-10000):",
            parse_mode=ParseMode.HTML,
        )
        return True

    if new_limit < 1 or new_limit > 10000:
        await update.message.reply_text(
            "❌ Value must be between 1 and 10000. Send a valid number:",
            parse_mode=ParseMode.HTML,
        )
        return True

    # Update the limit in DB
    db.set_setting("daily_limit", str(new_limit))
    db.clear_user_state(uid)

    # Show confirmation with updated admin panel
    total_users = db.get_user_count()
    maintenance = is_maintenance_mode()

    maint_status = "🟢 ON" if maintenance else "🔴 OFF"
    maint_btn_text = "🔴 Turn Maintenance OFF" if maintenance else "🟢 Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"

    text_msg = (
        f"✅ <b>Daily limit updated to {new_limit} msgs/24h</b>\n\n"
        f"🛡 <b>{AGENT_NAME} Admin Panel</b>\n\n"
        f"<b>📊 Stats:</b>\n"
        f"• Total Users: <code>{total_users}</code>\n"
        f"• Daily Limit: <code>{new_limit}</code> msgs/user\n"
        f"• Maintenance: {maint_status}\n\n"
        f"<b>🔧 Controls:</b>"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"⚙️ Change Rate Limit (now: {new_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("📊 Refresh Stats", callback_data="admin_refresh")],
    ])

    await update.message.reply_text(text_msg, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    return True


# ==================== FALLBACK HANDLERS ====================

async def handle_text(update: Update, context):
    """Handle plain text — show Mini App button or maintenance message."""
    uid = update.effective_user.id

    # Check if admin is in rate limit flow (handled by dedicated handler)
    user_state = db.get_user_state(uid)
    if user_state and user_state.get("state") == "waiting_for_rate_limit":
        return  # already handled by handle_admin_rate_limit_input

    # Non-admin blocked
    if not is_admin(uid):
        if is_maintenance_mode():
            await update.message.reply_text(MAINTENANCE_MSG, parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(
                "⛔ <b>Access Denied</b>\n\nThis bot is currently in private beta.",
                parse_mode=ParseMode.HTML,
            )
        return

    u = db.get_user(uid)
    if not u:
        await start_command(update, context)
        return

    await update.message.reply_text(
        "Use /start to open the Mini App 👾",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🚀 Open Mini App",
                web_app=WebAppInfo(url=MINI_APP_URL),
            )],
        ]),
    )


# ==================== MAIN ====================

def main():
    """Start the bot."""
    db.init_db()  # ensure tables exist

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))

    # Callback queries
    app.add_handler(CallbackQueryHandler(check_joined_callback, pattern="^check_joined$"))
    app.add_handler(CallbackQueryHandler(toggle_maintenance_callback, pattern="^toggle_maintenance_(on|off)$"))
    app.add_handler(CallbackQueryHandler(admin_rate_limit_callback, pattern="^admin_rate_limit$"))
    app.add_handler(CallbackQueryHandler(admin_refresh_callback, pattern="^admin_refresh$"))

    # Admin rate limit input handler (must be before fallback)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_admin_rate_limit_input,
        block=False,
    ))

    # Fallback text handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info(f"🤖 {AGENT_NAME} bot started (Mini App gateway + admin panel mode)")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
