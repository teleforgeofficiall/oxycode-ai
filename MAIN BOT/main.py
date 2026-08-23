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
from telegram.error import NetworkError, Conflict, TelegramError
import httpcore
import database as db
import asyncio
import logging
import datetime
import json
import providers
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

    # Get active provider info
    active_provider = db.get_active_provider()
    provider_name = active_provider["name"] if active_provider else "None"
    provider_status = "Working" if active_provider and active_provider.get("is_working") else "Not Working"

    # Build admin panel
    maint_status = "ON" if maintenance else "OFF"
    maint_btn_text = "Turn Maintenance OFF" if maintenance else "Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"

    text = (
        f"{AGENT_NAME} Admin Panel\n\n"
        f"Stats:\n"
        f"  Total Users: {total_users}\n"
        f"  Daily Limit: {daily_limit} msgs/user\n"
        f"  Maintenance: {maint_status}\n"
        f"  Primary: OpenCode (Free, IP-based)\n"
        f"  Fallback: {provider_name} ({provider_status})\n\n"
        f"Controls:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"Provider: {provider_name}", callback_data="admin_providers")],
        [InlineKeyboardButton(f"Change Rate Limit (now: {daily_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("Refresh Stats", callback_data="admin_refresh")],
    ])

    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def toggle_maintenance_callback(update: Update, context):
    """Handle maintenance toggle button."""
    query = update.callback_query
    uid = query.from_user.id

    if not is_admin(uid):
        await query.answer("Admin only!", show_alert=True)
        return

    # Toggle maintenance mode
    db.toggle_maintenance()

    # Build new admin panel
    total_users = db.get_user_count()
    daily_limit = db.get_daily_limit()
    maintenance = is_maintenance_mode()

    active_provider = db.get_active_provider()
    provider_name = active_provider["name"] if active_provider else "None"
    provider_status = "Working" if active_provider and active_provider.get("is_working") else "Not Working"

    maint_status = "ON" if maintenance else "OFF"
    maint_btn_text = "Turn Maintenance OFF" if maintenance else "Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"

    text = (
        f"{AGENT_NAME} Admin Panel\n\n"
        f"Stats:\n"
        f"  Total Users: {total_users}\n"
        f"  Daily Limit: {daily_limit} msgs/user\n"
        f"  Maintenance: {maint_status}\n"
        f"  Primary: OpenCode (Free, IP-based)\n"
        f"  Fallback: {provider_name} ({provider_status})\n\n"
        f"Controls:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"Provider: {provider_name}", callback_data="admin_providers")],
        [InlineKeyboardButton(f"Change Rate Limit (now: {daily_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("Refresh Stats", callback_data="admin_refresh")],
    ])

    await query.edit_message_text(text, reply_markup=keyboard)

    # Notify admin
    status_text = "ENABLED" if maintenance else "DISABLED"
    await query.answer(f"Maintenance mode {status_text}!", show_alert=True)


async def admin_refresh_callback(update: Update, context):
    """Handle refresh stats button."""
    query = update.callback_query
    uid = query.from_user.id

    if not is_admin(uid):
        await query.answer("Admin only!", show_alert=True)
        return

    # Rebuild admin panel with fresh stats
    total_users = db.get_user_count()
    daily_limit = db.get_daily_limit()
    maintenance = is_maintenance_mode()

    active_provider = db.get_active_provider()
    provider_name = active_provider["name"] if active_provider else "None"
    provider_status = "Working" if active_provider and active_provider.get("is_working") else "Not Working"

    maint_status = "ON" if maintenance else "OFF"
    maint_btn_text = "Turn Maintenance OFF" if maintenance else "Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"

    text = (
        f"{AGENT_NAME} Admin Panel\n\n"
        f"Stats:\n"
        f"  Total Users: {total_users}\n"
        f"  Daily Limit: {daily_limit} msgs/user\n"
        f"  Maintenance: {maint_status}\n"
        f"  Primary: OpenCode (Free, IP-based)\n"
        f"  Fallback: {provider_name} ({provider_status})\n\n"
        f"Controls:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"Provider: {provider_name}", callback_data="admin_providers")],
        [InlineKeyboardButton(f"Change Rate Limit (now: {daily_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("Refresh Stats", callback_data="admin_refresh")],
    ])

    await query.edit_message_text(text, reply_markup=keyboard)
    await query.answer("Stats refreshed!")


async def admin_rate_limit_callback(update: Update, context):
    """Handle rate limit change button — ask admin to send new value."""
    query = update.callback_query
    uid = query.from_user.id

    if not is_admin(uid):
        await query.answer("Admin only!", show_alert=True)
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
        f"✅ Daily limit updated to {new_limit} msgs/24h\n\n"
        f"{AGENT_NAME} Admin Panel\n\n"
        f"Stats:\n"
        f"  Total Users: {total_users}\n"
        f"  Daily Limit: {new_limit} msgs/user\n"
        f"  Maintenance: {maint_status}\n"
        f"  Primary: OpenCode (Free, IP-based)\n\n"
        f"Controls:"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"⚙️ Change Rate Limit (now: {new_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("📊 Refresh Stats", callback_data="admin_refresh")],
    ])

    await update.message.reply_text(text_msg, reply_markup=keyboard)
    return True


# ==================== PROVIDER MANAGEMENT ====================

async def _build_admin_panel():
    """Build admin panel text and keyboard."""
    total_users = db.get_user_count()
    daily_limit = db.get_daily_limit()
    maintenance = is_maintenance_mode()
    active_provider = db.get_active_provider()
    provider_name = active_provider["name"] if active_provider else "None"
    provider_status = "Working" if active_provider and active_provider.get("is_working") else "Not Working"
    maint_status = "ON" if maintenance else "OFF"
    maint_btn_text = "Turn Maintenance OFF" if maintenance else "Turn Maintenance ON"
    maint_callback = "toggle_maintenance_off" if maintenance else "toggle_maintenance_on"
    text = (
        f"{AGENT_NAME} Admin Panel\n\n"
        f"Stats:\n"
        f"  Total Users: {total_users}\n"
        f"  Daily Limit: {daily_limit} msgs/user\n"
        f"  Maintenance: {maint_status}\n"
        f"  Primary: OpenCode (Free, IP-based)\n"
        f"  Fallback: {provider_name} ({provider_status})\n\n"
        f"Controls:"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(maint_btn_text, callback_data=maint_callback)],
        [InlineKeyboardButton(f"Provider: {provider_name}", callback_data="admin_providers")],
        [InlineKeyboardButton(f"Change Rate Limit (now: {daily_limit})", callback_data="admin_rate_limit")],
        [InlineKeyboardButton("Refresh Stats", callback_data="admin_refresh")],
    ])
    return text, keyboard


async def admin_providers_callback(update: Update, context):
    """Handle Provider button - show provider list."""
    query = update.callback_query
    uid = query.from_user.id
    if not is_admin(uid):
        await query.answer("Admin only!", show_alert=True)
        return
    await query.answer()
    providers_list = db.get_all_providers()
    text = "Provider Management\n\n"
    keyboard_rows = []
    if providers_list:
        for p in providers_list:
            status_icon = "✅" if p.get("is_working") else "❌"
            active_icon = " ⭐" if p.get("is_active") else ""
            text += f"  {status_icon} {p['name']}{active_icon}\n"
            keyboard_rows.append([InlineKeyboardButton(
                f"{status_icon} {p['name']}{active_icon}",
                callback_data=f"provider_detail_{p['id']}"
            )])
    else:
        text += "  No providers configured yet.\n"
    keyboard_rows.append([InlineKeyboardButton("+ Add OpenCode (Free, No API Key)", callback_data="provider_add_opencode")])
    keyboard_rows.append([InlineKeyboardButton("+ Add Gemini", callback_data="provider_add_gemini")])
    keyboard_rows.append([InlineKeyboardButton("+ Add Nara Router", callback_data="provider_add_nararouter")])
    keyboard_rows.append([InlineKeyboardButton("+ Add Custom", callback_data="provider_add_custom")])
    keyboard_rows.append([InlineKeyboardButton("Back", callback_data="admin_back")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard_rows))


async def admin_back_callback(update: Update, context):
    """Handle Back button - return to admin panel."""
    query = update.callback_query
    uid = query.from_user.id
    if not is_admin(uid):
        await query.answer("Admin only!", show_alert=True)
        return
    await query.answer()
    text, keyboard = await _build_admin_panel()
    await query.edit_message_text(text, reply_markup=keyboard)


async def provider_detail_callback(update: Update, context):
    """Show provider detail with options."""
    query = update.callback_query
    uid = query.from_user.id
    if not is_admin(uid):
        await query.answer("Admin only!", show_alert=True)
        return
    await query.answer()
    provider_id = int(query.data.replace("provider_detail_", ""))
    provider = db.get_provider(provider_id)
    if not provider:
        await query.answer("Provider not found!", show_alert=True)
        return
    status = "✅ Working" if provider.get("is_active") else ("✅ Available" if provider.get("is_working") else "❌ Error")
    active = "⭐ Active" if provider.get("is_active") else "Inactive"
    auth_type = "IP-based (no key)" if provider["provider_type"] == "opencode" else "API Key"
    text = (
        f"{provider['name']}\n"
        f"Type: {provider['provider_type']}\n"
        f"Auth: {auth_type}\n"
        f"Status: {status}\n"
        f"Active: {active}\n"
        f"Base URL: {provider.get('base_url', 'default')}\n"
    )
    if provider.get("error_message"):
        text += f"Error: {provider['error_message']}\n"
    keyboard_rows = []
    if not provider.get("is_active"):
        keyboard_rows.append([InlineKeyboardButton("⭐ Set Active", callback_data=f"provider_activate_{provider_id}")])
    keyboard_rows.append([InlineKeyboardButton("Test Provider", callback_data=f"provider_test_{provider_id}")])
    keyboard_rows.append([InlineKeyboardButton("Delete", callback_data=f"provider_delete_{provider_id}")])
    keyboard_rows.append([InlineKeyboardButton("Back", callback_data="admin_providers")])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard_rows))


async def provider_activate_callback(update: Update, context):
    """Activate a provider."""
    query = update.callback_query
    uid = query.from_user.id
    if not is_admin(uid):
        await query.answer("Admin only!", show_alert=True)
        return
    provider_id = int(query.data.replace("provider_activate_", ""))
    provider = db.get_provider(provider_id)
    if not provider:
        await query.answer("Provider not found!", show_alert=True)
        return
    db.set_provider_active(provider_id)
    await query.answer(f"Provider {provider['name']} activated!", show_alert=True)
    # Go back to provider detail
    query.data = f"provider_detail_{provider_id}"
    await provider_detail_callback(update, context)


async def provider_test_callback(update: Update, context):
    """Test a provider."""
    query = update.callback_query
    uid = query.from_user.id
    if not is_admin(uid):
        await query.answer("Admin only!", show_alert=True)
        return
    await query.answer("Testing provider...")
    provider_id = int(query.data.replace("provider_test_", ""))
    result = await providers.test_provider(provider_id)
    if result["ok"]:
        models_count = len(result["models"])
        await query.answer(f"Provider works! Found {models_count} models.", show_alert=True)
    else:
        await query.answer(f"Provider failed: {result['error'][:100]}", show_alert=True)
    # Refresh detail view
    query.data = f"provider_detail_{provider_id}"
    await provider_detail_callback(update, context)


async def provider_delete_callback(update: Update, context):
    """Delete a provider after confirmation."""
    query = update.callback_query
    uid = query.from_user.id
    if not is_admin(uid):
        await query.answer("Admin only!", show_alert=True)
        return
    provider_id = int(query.data.replace("provider_delete_", ""))
    provider = db.get_provider(provider_id)
    if not provider:
        await query.answer("Provider not found!", show_alert=True)
        return
    db.delete_provider(provider_id)
    await query.answer(f"Provider {provider['name']} deleted!", show_alert=True)
    await admin_providers_callback(update, context)


async def provider_add_callback(update: Update, context):
    """Start add provider flow - skip name for built-in providers."""
    query = update.callback_query
    uid = query.from_user.id
    if not is_admin(uid):
        await query.answer("Admin only!", show_alert=True)
        return
    await query.answer()
    provider_type = query.data.replace("provider_add_", "")
    defaults = providers.PROVIDER_DEFAULTS.get(provider_type, {})
    display = defaults.get("display_name", provider_type)

    if provider_type == "opencode":
        # OpenCode = IP-based, no API key needed — add directly
        await query.edit_message_text(f"Adding OpenCode (IP-based, no API key needed)...\n\nTesting...")
        is_valid, models, error = await providers.validate_opencode()
        if is_valid:
            provider_id = db.add_provider(display, "opencode", api_key="")
            db.update_provider_status(provider_id, is_working=1, models_json=json.dumps(models))
            existing = db.get_all_providers()
            if len(existing) == 1:
                db.set_provider_active(provider_id)
            models_preview = ", ".join(models[:5]) if models else "none"
            if len(models) > 5:
                models_preview += f" (+{len(models)-5} more)"
            await query.edit_message_text(
                f"✅ OpenCode added!\n\n"
                f"Auth: IP-based (no API key)\n"
                f"Models: {len(models)}\n"
                f"Preview: {models_preview}\n"
                f"Status: Working\n\n"
                f"OpenCode is now the PRIMARY provider (tried first on every request)."
            )
        else:
            await query.edit_message_text(
                f"❌ OpenCode validation failed:\n{error}\n\n"
                f"Provider was NOT added."
            )
    elif provider_type in ("gemini", "nararouter"):
        # Skip name - go straight to API key
        auto_name = display
        db.set_user_state(uid, "waiting_for_provider_apikey", data=json.dumps({"type": provider_type, "name": auto_name}))
        await query.edit_message_text(
            f"Adding {display}\n\n"
            f"Send the API key:\n\n"
            f"Send /cancel to abort."
        )
    else:
        # Custom - ask for name first
        db.set_user_state(uid, "waiting_for_provider_name", data=provider_type)
        await query.edit_message_text(
            f"Adding Custom Provider\n\n"
            f"Send a name for this provider:"
        )


async def handle_provider_name_input(update: Update, context):
    """Handle provider name input (custom providers only)."""
    uid = update.effective_user.id
    user_state = db.get_user_state(uid)
    if not user_state or user_state.get("state") != "waiting_for_provider_name":
        return False
    if not is_admin(uid):
        return False
    name = update.message.text.strip()
    provider_type = user_state.get("data", "custom")
    db.set_user_state(uid, "waiting_for_provider_apikey", data=json.dumps({"type": provider_type, "name": name}))
    await update.message.reply_text(
        f"Send the API key for {name}:\n\n"
        f"Send /cancel to abort."
    )
    return True


async def handle_provider_apikey_input(update: Update, context):
    """Handle API key input."""
    uid = update.effective_user.id
    user_state = db.get_user_state(uid)
    if not user_state or user_state.get("state") != "waiting_for_provider_apikey":
        return False
    if not is_admin(uid):
        return False
    api_key = update.message.text.strip()
    state_data = json.loads(user_state.get("data", "{}"))
    provider_type = state_data.get("type", "custom")
    name = state_data.get("name", "Custom Provider")

    if provider_type == "custom":
        # Custom needs base URL next
        db.set_user_state(uid, "waiting_for_provider_baseurl", data=json.dumps({
            "type": provider_type, "name": name, "api_key": api_key
        }))
        await update.message.reply_text("Send the Base URL:\n(e.g. https://api.example.com/v1)\n\nSend /cancel to abort.")
    else:
        # Built-in (opencode/gemini/nararouter) - validate immediately
        await update.message.reply_text("Testing API key...")
        is_valid, models, error = await providers.validate_provider(provider_type, api_key)
        if is_valid:
            provider_id = db.add_provider(name, provider_type, api_key=api_key)
            db.update_provider_status(provider_id, is_working=1, models_json=json.dumps(models))
            existing = db.get_all_providers()
            if len(existing) == 1:
                db.set_provider_active(provider_id)
            models_preview = ", ".join(models[:5]) if models else "none"
            if len(models) > 5:
                models_preview += f" (+{len(models)-5} more)"
            await update.message.reply_text(
                f"Provider \"{name}\" added!\n\n"
                f"Models found: {len(models)}\n"
                f"Preview: {models_preview}\n\n"
                f"Status: Working"
            )
        else:
            await update.message.reply_text(
                f"Provider validation failed:\n{error}\n\n"
                f"Provider was NOT added. Try again with /admin."
            )
        db.clear_user_state(uid)
    return True


async def handle_provider_baseurl_input(update: Update, context):
    """Handle base URL input for custom provider."""
    uid = update.effective_user.id
    user_state = db.get_user_state(uid)
    if not user_state or user_state.get("state") != "waiting_for_provider_baseurl":
        return False
    if not is_admin(uid):
        return False
    base_url = update.message.text.strip()
    state_data = json.loads(user_state.get("data", "{}"))
    provider_type = state_data.get("type", "custom")
    name = state_data.get("name", "Custom Provider")
    api_key = state_data.get("api_key", "")

    # Ask for model IDs
    db.set_user_state(uid, "waiting_for_provider_model_ids", data=json.dumps({
        "type": provider_type, "name": name, "api_key": api_key, "base_url": base_url
    }))
    await update.message.reply_text(
        "Send model ID(s) for this provider:\n\n"
        "Single: gpt-4\n"
        "Multiple: gpt-4, gpt-3.5-turbo, claude-3\n\n"
        "Send /skip to auto-detect from API."
    )
    return True


async def handle_provider_model_ids_input(update: Update, context):
    """Handle model ID input for custom provider."""
    uid = update.effective_user.id
    user_state = db.get_user_state(uid)
    if not user_state or user_state.get("state") != "waiting_for_provider_model_ids":
        return False
    if not is_admin(uid):
        return False

    state_data = json.loads(user_state.get("data", "{}"))
    provider_type = state_data.get("type", "custom")
    name = state_data.get("name", "Custom Provider")
    api_key = state_data.get("api_key", "")
    base_url = state_data.get("base_url", "")

    text = update.message.text.strip()
    if text == "/skip":
        models = []
    else:
        models = [m.strip() for m in text.split(",") if m.strip()]

    # Validate
    await update.message.reply_text("Testing provider...")
    is_valid, detected_models, error = await providers.validate_provider(provider_type, api_key, base_url)
    if is_valid:
        final_models = models if models else detected_models
        provider_id = db.add_provider(name, provider_type, api_key=api_key, base_url=base_url)
        db.update_provider_status(provider_id, is_working=1, models_json=json.dumps(final_models))
        existing = db.get_all_providers()
        if len(existing) == 1:
            db.set_provider_active(provider_id)
        models_preview = ", ".join(final_models[:5]) if final_models else "none"
        if len(final_models) > 5:
            models_preview += f" (+{len(final_models)-5} more)"
        await update.message.reply_text(
            f"Provider \"{name}\" added!\n\n"
            f"Models: {len(final_models)}\n"
            f"Preview: {models_preview}\n\n"
            f"Status: Working"
        )
    else:
        await update.message.reply_text(
            f"Provider validation failed:\n{error}\n\n"
            f"Provider was NOT added. Try again with /admin."
        )
    db.clear_user_state(uid)
    return True


# ==================== FALLBACK HANDLERS ====================

async def cancel_command(update: Update, context):
    """/cancel — Cancel current operation."""
    uid = update.effective_user.id
    db.clear_user_state(uid)
    await update.message.reply_text("Operation cancelled.")


async def handle_text(update: Update, context):
    """Handle plain text - route to appropriate handler based on state."""
    uid = update.effective_user.id

    # Check state-based routing first
    user_state = db.get_user_state(uid)
    if user_state:
        state = user_state.get("state", "")
        if state == "waiting_for_rate_limit":
            return await handle_admin_rate_limit_input(update, context)
        elif state == "waiting_for_provider_name":
            return await handle_provider_name_input(update, context)
        elif state == "waiting_for_provider_apikey":
            return await handle_provider_apikey_input(update, context)
        elif state == "waiting_for_provider_baseurl":
            return await handle_provider_baseurl_input(update, context)
        elif state == "waiting_for_provider_model_ids":
            return await handle_provider_model_ids_input(update, context)

    u = db.get_user(uid)
    if not u:
        await start_command(update, context)
        return

    await update.message.reply_text(
        "Use /start to open the Mini App",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "Open Mini App",
                web_app=WebAppInfo(url=MINI_APP_URL),
            )],
        ]),
    )


# ==================== ERROR HANDLER ====================

async def error_handler(update: object, context):
    """Handle errors from handlers — prevents silent failures."""
    error = context.error

    if isinstance(error, Conflict):
        logger.warning(f"Polling conflict (expected during restart): {error}")
        return

    if isinstance(error, (NetworkError, httpcore.ReadError, httpcore.WriteError)):
        logger.warning(f"Network error (will continue polling): {error}")
        return

    if isinstance(error, TelegramError):
        logger.error(f"Telegram API error: {error}")
        return

    logger.exception(f"Unhandled exception in handler: {error}")


# ==================== MAIN ====================

def main():
    """Start the bot."""
    db.init_db()  # ensure tables exist

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("admin", admin_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # Callback queries
    app.add_handler(CallbackQueryHandler(check_joined_callback, pattern="^check_joined$"))
    app.add_handler(CallbackQueryHandler(toggle_maintenance_callback, pattern="^toggle_maintenance_(on|off)$"))
    app.add_handler(CallbackQueryHandler(admin_rate_limit_callback, pattern="^admin_rate_limit$"))
    app.add_handler(CallbackQueryHandler(admin_refresh_callback, pattern="^admin_refresh$"))
    app.add_handler(CallbackQueryHandler(admin_providers_callback, pattern="^admin_providers$"))
    app.add_handler(CallbackQueryHandler(admin_back_callback, pattern="^admin_back$"))
    app.add_handler(CallbackQueryHandler(provider_detail_callback, pattern=r"^provider_detail_\d+$"))
    app.add_handler(CallbackQueryHandler(provider_activate_callback, pattern=r"^provider_activate_\d+$"))
    app.add_handler(CallbackQueryHandler(provider_test_callback, pattern=r"^provider_test_\d+$"))
    app.add_handler(CallbackQueryHandler(provider_delete_callback, pattern=r"^provider_delete_\d+$"))
    app.add_handler(CallbackQueryHandler(provider_add_callback, pattern="^provider_add_(opencode|gemini|nararouter|custom)$"))

    # Single text handler - routes based on user state
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Error handler — prevents silent failures
    app.add_error_handler(error_handler)

    logger.info(f"🤖 {AGENT_NAME} bot started (Mini App gateway + admin panel mode)")
    app.run_polling(
        drop_pending_updates=False,
        allowed_updates=["message", "callback_query"],
    )


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    main()
