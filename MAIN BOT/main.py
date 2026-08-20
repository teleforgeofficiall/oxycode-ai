"""
OXYGENT — Telegram Bot Main Module
===================================

This module implements the main Telegram bot interface for OXYGENT,
an autonomous AI coding agent. It handles:

- User commands (/start, /help, /status, /voice, etc.)
- Callback query routing for inline keyboards
- AI response orchestration with voice support
- Session management for code creation
- Force-join channel enforcement
- Referral system with deep-link support
- Admin panel and broadcast functionality
- Rate limiting and daily message quotas

Architecture:
    main.py serves as the entry point and orchestrator, delegating:
    - Agent loop → agent_engine.py
    - Tool execution → coding_tools.py
    - Memory → memory_system.py
    - Database → database.py
    - Payments → payments.py
    - Configuration → config.py

Author: OXYCODE TEAM
"""

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    MessageEntity,
)
from telegram.constants import ParseMode, ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    PreCheckoutQueryHandler,
    filters,
)
import database as db
import asyncio
import re
import io
import os
import json
import aiohttp
import logging
import datetime


def _entities_to_list(entities):
    """Serialize a list of Telegram MessageEntity objects to plain dicts
    (JSON-serializable) for storage in the broadcast payload."""
    if not entities:
        return None
    out = []
    for e in entities:
        try:
            out.append(e.to_dict())
        except Exception:
            # Fallback: reconstruct the minimal dict
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
    """Rebuild Telegram MessageEntity objects from a stored dict list."""
    if not lst:
        return None
    return [MessageEntity.de_json(d) for d in lst]


def _reset_countdown():
    """Seconds left until the daily limit resets (next midnight UTC)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    tomorrow = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((tomorrow - now).total_seconds())


def _fmt_countdown(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


async def _limit_reached(update, context, daily):
    """Reply with a rate-limit message that includes a live countdown to reset."""
    secs = _reset_countdown()
    await update.message.reply_text(
        f"**⏳ Daily Limit Reached!**\n\n"
        f"You've used all **{daily}** free messages today and have no bonus credits left.\n\n"
        f"🔄 Resets in: **{_fmt_countdown(secs)}** (24h rolling)\n\n"
        f"Get more credits with **Telegram Stars** ⭐ to keep chatting:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Buy Credits", callback_data="menu_buy", style="success")],
            [InlineKeyboardButton("Back to Menu", callback_data="menu_back", style="primary")]
        ])
    )
    return True
import memory_system

from config import (
    BOT_TOKEN,
    ADMIN_IDS,
    OPENCODE_ZEN_BASE_URL,
    OPENCODE_ZEN_MODEL,
    OPENCODE_ZEN_FALLBACKS,
    WELCOME_MESSAGE,
    HELP_MESSAGE,
    SYSTEM_PROMPT,
    AGENT_NAME,
)

from coding_tools import send_code_blocks, cleanup_sandbox
from payments import handle_pre_checkout, handle_successful_payment, get_buy_keyboard
import agent_engine as ae

logger = logging.getLogger(__name__)


async def _zen_chat(prompt, system=None, max_retries=3):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {"model": OPENCODE_ZEN_MODEL, "messages": messages, "stream": False}

    # Try primary model, then configured fallbacks (handles rate-limits / 502s).
    # Each model gets a couple of retries with backoff so a momentary 429/5xx
    # spike doesn't kill the whole request (that caused the "AI unavailable" msg).
    models = [OPENCODE_ZEN_MODEL] + [m for m in OPENCODE_ZEN_FALLBACKS if m != OPENCODE_ZEN_MODEL]
    last_err = ""
    async with aiohttp.ClientSession() as s:
        for model in models:
            payload["model"] = model
            for attempt in range(max_retries + 1):
                try:
                    async with s.post(
                        f"{OPENCODE_ZEN_BASE_URL}/chat/completions",
                        headers={"Content-Type": "application/json"},
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as r:
                        if r.status == 200:
                            res = await r.json()
                            content = res.get('choices', [{}])[0].get('message', {}).get('content', '')
                            return content
                        body = await r.text()
                        last_err = f"HTTP {r.status}: {body[:120]}"
                        # 429/5xx = transient -> retry this model; 4xx (401/400) = fatal for this model
                        if r.status in (429, 500, 502, 503, 504) and attempt < max_retries:
                            await asyncio.sleep(2.0 * (attempt + 1))
                            continue
                        break  # fatal or out of retries -> move to next model
                except Exception as e:
                    last_err = f"{type(e).__name__}: {str(e)[:120]}"
                    if attempt < max_retries:
                        await asyncio.sleep(2.0 * (attempt + 1))
                        continue
                    break
    logger.error(f"_zen_chat failed on all models. Last error: {last_err}")
    return None  # signal failure (caller shows a proper message)


# ==================== AI RESPONSE + VOICE ====================

EDGE_VOICES = {
    "female": "en-US-AriaNeural",
    "male": "en-US-GuyNeural",
}

# Friendly message shown only when the AI genuinely can't be reached after all
# retries + model fallbacks. (Usually a temporary free-tier rate-limit spike.)
AI_UNAVAILABLE_MSG = (
    "⚠️ **The AI is temporarily busy** (free-tier rate limit).\n\n"
    "It auto-retries across multiple models, but all are saturated right now. "
    "Please try again in ~30 seconds — it'll work then."
)


async def _send_ai_reply(update, context, prompt, system=None, reply_markup=None,
                         thinking="Thinking...", limit_check=False, progress_label=None):
    """Send an AI text reply, and optionally a voice note if the user enabled voice.

    `limit_check=True` runs the daily/paid limit enforcement for this AI call.
    `progress_label` (str) shows a single Hermes-style progress step instead of
    just a typing indicator.
    """
    uid = update.effective_user.id

    if limit_check:
        # Reuse the same single-pass limit logic as handle_text (free -> paid -> block)
        count, _ = db.get_msg_count(uid, datetime.date.today().isoformat())
        daily = db.get_daily_limit()
        u = db.get_user(uid)
        bonus = u.get('bonus_messages', 0) if u else 0
        free_left = daily - count
        if free_left > 0:
            db.increment_msg_count(uid, datetime.date.today().isoformat())
        elif bonus > 0:
            db.consume_bonus_message(uid, 1)
        else:
            return await _limit_reached(update, context, daily)

    if progress_label:
        _, results = await run_steps(update, context, [
            (progress_label, _zen_chat(prompt, system)),
        ])
        text = results[0]
    else:
        text = await _typing_while(update, context, _zen_chat(prompt, system))
    if text is None:
        await _safe_markdown(
            update.message,
            AI_UNAVAILABLE_MSG,
            reply_markup=reply_markup)
        return True
    text = text if text else "Sorry, I had trouble generating a response. Try rephrasing."
    await _safe_markdown(update.message, text, reply_markup=reply_markup)

    # Voice note (if enabled)
    enabled, gender = db.get_voice_pref(uid)
    if enabled:
        try:
            await _send_voice(update, context, text[:4000], gender)
        except Exception as e:
            logger.error(f"Voice send failed: {e}")
    return True


def _plan_md(header, plan):
    """Build a Telegram-Markdown-v1-safe plan message with a blockquote body.

    - `header` (already trusted, e.g. '**Plan for X**') stays bold.
    - Every line of the AI `plan` body is prefixed with '> ' so Telegram
      renders it as a quote block (multiline quotes need '>' per line).
    - Stray '*'/'_'/backtick that would break Markdown v1 parsing are escaped,
      while matched '**bold**' pairs are preserved.
    """
    plan = (plan or "").strip()
    out_lines = []
    for line in plan.split("\n"):
        if line.strip() == "":
            # an empty quoted line still needs the '>' so the block stays open
            out_lines.append(">")
            continue
        escaped = line
        # escape backticks
        escaped = escaped.replace("`", "\\`")
        # escape underscores (AI rarely intends italics here)
        escaped = escaped.replace("_", "\\_")
        # escape lone asterisks but keep ** pairs
        # first protect ** pairs
        protected = escaped.replace("**", "\x00BOLD\x00")
        # escape remaining single *
        protected = protected.replace("*", "\\*")
        # restore ** pairs
        escaped = protected.replace("\x00BOLD\x00", "**")
        out_lines.append("> " + escaped)
    quote_body = "\n".join(out_lines)
    return f"{header}\n\n{quote_body}\n\nApprove to start building:"


async def _safe_html(target, text, reply_markup=None, edit=False):
    """Send/edit text with HTML, falling back to plain text if parsing fails.

    Telegram HTML (needed for <blockquote class="expandable">) can break on
    unescaped chars. Failing to send makes the bot look dead — so we retry as
    plain text rather than throwing.
    """
    text = text or ""
    if len(text) > 4000:
        text = text[:4000]
    try:
        if edit:
            await target.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
        else:
            await target.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=reply_markup)
    except Exception:
        try:
            if edit:
                await target.edit_text(text, reply_markup=reply_markup)
            else:
                await target.reply_text(text, reply_markup=reply_markup)
        except Exception:
            pass


async def _safe_markdown(target, text, reply_markup=None, edit=False):
    """Send/edit text with Markdown, falling back to plain text if parsing fails.

    AI responses often contain unescaped '*' or backticks that break Telegram's
    Markdown parser. Failing to send makes the bot look dead/slow — so we retry
    as plain text rather than throwing.
    """
    text = text or ""
    if len(text) > 4000:
        text = text[:4000]
    try:
        if edit:
            await target.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        else:
            await target.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception:
        try:
            if edit:
                await target.edit_text(text, reply_markup=reply_markup)
            else:
                await target.reply_text(text, reply_markup=reply_markup)
        except Exception:
            pass


async def _typing_while(update, context, coro):
    """Show the Telegram 'typing…' indicator while awaiting `coro`.

    Telegram's typing action expires after ~5s, so we keep refreshing it
    for as long as the AI call takes (in 4s bursts). Returns coro's result.
    """
    chat_id = update.effective_chat.id
    task = asyncio.ensure_future(coro)
    try:
        while not task.done():
            try:
                await context.bot.send_chat_action(chat_id, ChatAction.TYPING)
            except Exception:
                pass
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=4.0)
            except asyncio.TimeoutError:
                continue  # still running -> refresh typing
            break
    finally:
        return await task


async def run_steps(update, context, steps):
    """Show a live, in-place progress checklist (Hermes-style) and run each step.

    `steps` = list of (label, coro). Each label shows ⏳ while running, ✅ when
    done. The message edits itself in place so the user always sees what the bot
    is doing. Returns a list of the coroutine results in order.

    Example:
        res = await run_steps(update, context, [
            ("Analyzing your request", _zen_chat(p1, s1)),
            ("Building the HTML",      _zen_chat(p2, s2)),
        ])
    """
    labels = [s[0] for s in steps]
    lines = ["⏳ " + l for l in labels]
    msg = await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def _run(i, coro):
        lines[i] = "🔄 " + labels[i]
        try:
            await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
        try:
            result = await coro
        except Exception as e:
            lines[i] = "❌ " + labels[i]
            try:
                await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
            except Exception:
                pass
            raise
        lines[i] = "✅ " + labels[i]
        try:
            await msg.edit_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
        return result

    results = []
    for i, (label, coro) in enumerate(steps):
        results.append(await _run(i, coro))
    return msg, results


async def _send_voice(update, context, text, gender="female"):
    """Generate a voice note via edge-tts and send it, then clean up."""
    import edge_tts
    import tempfile
    voice = EDGE_VOICES.get(gender, EDGE_VOICES["female"])
    mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    mp3_path = mp3.name
    mp3.close()
    communicate = edge_tts.Communicate(text[:4000], voice)
    await communicate.save(mp3_path)
    with open(mp3_path, "rb") as f:
        await context.bot.send_voice(update.effective_chat.id, f)
    try:
        os.remove(mp3_path)
    except Exception:
        pass


# ==================== MENU ====================

def get_menu(user_id=None):
    btns = [
        [InlineKeyboardButton("Create Code", callback_data="menu_create", style="success")],
        [InlineKeyboardButton("My Profile", callback_data="menu_profile", style="primary"),
         InlineKeyboardButton("Refer & Earn", callback_data="menu_refer", style="primary")],
        [InlineKeyboardButton("Buy Credit", callback_data="menu_buy", style="success"),
         InlineKeyboardButton("Support", callback_data="menu_support", style="success")],
    ]
    if user_id and user_id in ADMIN_IDS:
        btns.append([InlineKeyboardButton("Admin Panel", callback_data="menu_admin", style="danger")])
    return InlineKeyboardMarkup(btns)


def back_btn(text="Back to Menu", data="menu_back"):
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=data, style="primary")]])


# ==================== COMMANDS ====================

async def start_command(update, context):
    user = update.effective_user
    uid = user.id
    is_new_user = db.add_user(uid, user.username, user.first_name, user.last_name)
    u = db.get_user(uid)
    if u and u.get('is_banned'):
        await update.message.reply_text("You are banned.")
        return

    # Notify the admin in real time when a brand-new user starts the bot.
    if is_new_user:
        # Get count AFTER the insert commits, then pass it to avoid race conditions
        total_users = db.get_user_count()
        # Fire-and-forget: real-time admin notification. Must NEVER crash /start
        # even if Telegram is unreachable or the DB count fails.
        try:
            asyncio.create_task(notify_admin_new_user(context.bot, user, total_users))
        except Exception:
            try:
                asyncio.ensure_future(notify_admin_new_user(context.bot, user, total_users))
            except Exception as e:
                logger.error(f"notify_admin_new_user sched failed: {e}")

    # Capture referral deep-link: /start ref_OXY1B762D
    # Stored as a PENDING referral; credited automatically once the user
    # joins the required channel(s) (no manual code entry needed).
    if context.args:
        arg = context.args[0].strip()
        if arg.lower().startswith("ref_"):
            code = arg[4:].strip().upper()
            if code and not (u and u.get('referred_by')):
                db.set_user_state(uid, "pending_ref", data=code)

    joined, not_joined = await check_channel_membership(uid, context)
    if not joined:
        await update.message.reply_text(
            f"**{AGENT_NAME}**\n\nJoin all required channels:",
            reply_markup=get_force_join_keyboard(not_joined),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    # User is already joined — apply any pending referral immediately
    await apply_referral(uid, context)
    await update.message.reply_text(WELCOME_MESSAGE, parse_mode=ParseMode.HTML, reply_markup=get_menu(uid))


async def notify_admin_new_user(bot, user, user_count: int):
    """Send a real-time notification to every admin when a NEW user starts the bot.

    Includes an ordinal counter (1st, 2nd, 3rd user) + username/first_name + user_id
    so the admin immediately knows who joined. Best-effort: never raised on failure.
    """
    total = user_count  # Use pre-computed count to avoid race condition
    # Ordinal label (1st, 2nd, 3rd, 4th...)
    try:
        s = str(total)
        if s.endswith("11") or s.endswith("12") or s.endswith("13"):
            order = f"{total}th"
        elif s.endswith("1"):
            order = f"{total}st"
        elif s.endswith("2"):
            order = f"{total}nd"
        elif s.endswith("3"):
            order = f"{total}rd"
        else:
            order = f"{total}th"
    except Exception:
        order = f"{total}th"

    name = user.first_name or (user.username or "unknown")
    uname = f"@{user.username}" if user.username else ""
    text = (
        f"<b>🆕 New User #{total} ({order}) joined {AGENT_NAME}!</b>\n\n"
        f"<b>Name:</b> {name} {uname}\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>Total Users:</b> {total}\n\n"
        f"<blockquote>📋 Admin alert — a fresh user just started the bot. Tap their profile for details. Join gates & referrals are tracked automatically on channel join.</blockquote>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode=ParseMode.HTML)
        except Exception:
            # Fallback: send as plain text so the admin never misses a notification
            try:
                await bot.send_message(admin_id, text)
            except Exception as e2:
                logger.error(f"notify_admin_new_user -> {admin_id}: {e2}")


async def menu_command(update, context):
    await update.message.reply_text("**Menu**", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(update.effective_user.id))


async def help_command(update, context):
    await update.message.reply_text(HELP_MESSAGE, parse_mode=ParseMode.HTML, reply_markup=back_btn())


async def cancel_command(update, context):
    uid = update.effective_user.id
    db.clear_user_state(uid)
    await update.message.reply_text("**Cancelled.**", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(uid))


async def create_command(update, context):
    await show_sessions(update, context, update.effective_user.id)


# ==================== MISSING COMMANDS (made working) ====================

async def status_command(update, context):
    """/status - show the user's info, limits and credits."""
    uid = update.effective_user.id
    u = db.get_user(uid)
    if not u:
        await update.message.reply_text("Use /start first.", reply_markup=get_menu(uid))
        return
    rem, daily, bonus, used = db.get_remaining_messages(uid, datetime.date.today().isoformat())
    sessions = db.get_user_sessions(uid)
    max_s = int(db.get_setting('max_sessions', '5'))
    enabled, gender = db.get_voice_pref(uid)
    t = (
        f"**Your Status**\n\n"
        f"**Name:** {u.get('first_name','N/A')} {u.get('last_name','')}\n"
        f"**ID:** `{uid}`\n\n"
        f"**Messages Today:** {used}/{daily}\n"
        f"**Free Remaining:** {max(0, daily-used)}\n"
        f"**Bonus Credits:** {bonus}\n"
        f"**Total Remaining:** {rem}\n\n"
        f"**Sessions:** {len(sessions)}/{max_s}\n"
        f"**Voice:** {'ON ('+gender+')' if enabled else 'OFF'}\n"
        f"**Referral Code:** `{db.generate_referral_code(uid)}`\n"
        f"**Referred:** {db.get_referred_count(uid)}"
    )
    await update.message.reply_text(t, parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn())


async def voice_command(update, context):
    """/voice - toggle voice-note replies, OR /voice <text> to speak a message now."""
    uid = update.effective_user.id
    speak = " ".join(context.args).strip()

    # /voice hello  -> speak "hello" right now as a voice note
    if speak:
        enabled, gender = db.get_voice_pref(uid)
        await update.message.reply_text("🔊 Generating voice...", parse_mode=ParseMode.MARKDOWN)
        try:
            await _send_voice(update, context, speak[:4000], gender)
        except Exception as e:
            logger.error(f"Voice speak failed: {e}")
            await update.message.reply_text(f"❌ Voice failed: {speak}")
        return

    # plain /voice -> toggle the always-on voice preference
    enabled, gender = db.get_voice_pref(uid)
    new_state = not enabled
    db.update_voice_pref(uid, enabled=new_state)
    await update.message.reply_text(
        f"🔊 **Voice replies {'ENABLED' if new_state else 'DISABLED'}**\n\n"
        f"Voice gender: `{gender}` (change with /voicegender)\n\n"
        f"When enabled, I'll send a voice note with every reply.\n\n"
        f"Tip: use `/voice <text>` to speak something instantly, e.g. `/voice hello there`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_btn()
    )


async def voicegender_command(update, context):
    """/voicegender - set voice to male or female."""
    uid = update.effective_user.id
    arg = context.args[0] if context.args else ''
    if not arg or arg.lower() not in ('male', 'female', 'm', 'f'):
        db.update_voice_pref(uid, enabled=True)
        await update.message.reply_text(
            "🎙 **Voice Gender**\n\nSend `/voicegender male` or `/voicegender female`.\nVoice is now **ON**.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn()
        )
        return
    gender = 'male' if arg.lower().startswith('m') else 'female'
    db.update_voice_pref(uid, enabled=True, gender=gender)
    await update.message.reply_text(
        f"🎙 **Voice set to {gender.upper()}** and enabled.\nUse /voice to toggle off.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn()
    )


async def background_command(update, context):
    """/background <question> - ask a quick question without touching session state."""
    uid = update.effective_user.id
    q = " ".join(context.args).strip()
    if not q:
        await update.message.reply_text(
            "Usage: `/background <your question>`\nAsk anything while in a session flow.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn()
        )
        return
    await _send_ai_reply(
        update, context,
        f"(Quick background question, keep it brief)\nUser: {q}",
        system=SYSTEM_PROMPT,
        thinking="Background thinking...",
        progress_label="Researching your question",
        limit_check=True
    )


async def search_command(update, context):
    """/search <query> - web search via DuckDuckGo."""
    from coding_tools import web_search
    q = " ".join(context.args).strip()
    if not q:
        await update.message.reply_text(
            "Usage: `/search <query>`\ne.g. `/search python asyncio tutorial`",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn()
        )
        return
    await update.message.reply_text("🔎 Searching...", parse_mode=ParseMode.MARKDOWN)
    res = await web_search(q, num_results=5)
    if not res.get("success") or not res.get("results"):
        await update.message.reply_text("No results found.", reply_markup=back_btn())
        return
    t = f"**Search: `{q}`**\n\n"
    for i, r in enumerate(res["results"][:5], 1):
        title = (r.get("title") or r.get("snippet") or "result")[:60]
        url = r.get("url", "")
        t += f"{i}. [{title}]({url})\n"
    await update.message.reply_text(t, parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn())


async def memory_command(update, context):
    """/memory - show the user's stored memory notes."""
    from memory_system import get_memory
    mem = get_memory(uid := update.effective_user.id)
    profile = mem.get_user_profile()
    body = ""
    if profile.strip():
        body += f"**USER PROFILE**\n{profile}\n\n"
    m = mem.get_memory()
    if m.strip():
        body += f"**MEMORY**\n{m}\n\n"
    if not body.strip():
        body = "No memory stored yet. I'll learn about you as we chat."
    await update.message.reply_text(
        f"**Your Memory**\n\n{body[:3900]}",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn()
    )


async def forget_command(update, context):
    """/forget - clear stored memory for this user."""
    from memory_system import get_memory
    mem = get_memory(update.effective_user.id)
    try:
        mem.hermes_memory.user_dir.joinpath("MEMORY.md").write_text("")
        mem.hermes_memory.user_dir.joinpath("USER.md").write_text("")
    except Exception:
        pass
    # Reset cached instance so future calls start clean
    if update.effective_user.id in memory_system._memory_instances:
        del memory_system._memory_instances[update.effective_user.id]
    await update.message.reply_text(
        "🧹 **Memory cleared.**\nYour stored notes and profile have been wiped.",
        parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn()
    )


async def explain_command(update, context):
    """/explain - explain code. Paste code after the command or send it next."""
    uid = update.effective_user.id
    code = " ".join(context.args).strip()
    if code:
        await _explain_code(update, context, code)
    else:
        db.set_user_state(uid, "explain_code")
        await update.message.reply_text(
            "**Explain Code**\n\nSend me the code you want explained:",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn("Cancel", "menu_back")
        )


async def fix_command(update, context):
    """/fix - debug code. Paste code (+ error) or send it next."""
    uid = update.effective_user.id
    code = " ".join(context.args).strip()
    if code:
        await _fix_code(update, context, code)
    else:
        db.set_user_state(uid, "fix_code")
        await update.message.reply_text(
            "**Fix Code**\n\nSend me the broken code (paste the error too if you have it):",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn("Cancel", "menu_back")
        )


async def ui_command(update, context):
    """/ui - generate a UI/website from a text description."""
    uid = update.effective_user.id
    desc = " ".join(context.args).strip()
    if desc:
        await _gen_ui(update, context, desc)
    else:
        db.set_user_state(uid, "ui_gen")
        await update.message.reply_text(
            "**Generate UI**\n\nDescribe the UI/website you want (e.g. 'a dark login page with glassmorphism'):",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn("Cancel", "menu_back")
        )


# ==================== EXPLAIN / FIX / UI CORE ====================

async def _explain_code(update, context, code):
    await _send_ai_reply(
        update, context,
        f"Explain this code clearly, line by line where helpful, in plain English:\n\n{code[:2000]}",
        system="You are OXYGENT, a coding tutor. Explain code clearly and concisely.",
        thinking="Explaining code...",
        progress_label="Reading your code",
        limit_check=True
    )


async def _fix_code(update, context, code):
    await _send_ai_reply(
        update, context,
        f"Find and fix bugs in this code. Return the corrected code in a single code block plus a short explanation:\n\n{code[:2000]}",
        system="You are OXYGENT, a debugging expert. Fix code and explain the fix.",
        thinking="Debugging...",
        progress_label="Analyzing your code for bugs",
        limit_check=True
    )


async def _gen_ui(update, context, desc):
    prompt = (
        f"Build a single-file HTML UI for: {desc[:500]}\n"
        "Return ONLY one HTML code block (with embedded CSS/JS). "
        "Start the block with '# file: index.html'."
    )
    _, results = await run_steps(update, context, [
        ("Understanding your design request", _zen_chat(prompt, "You output only a single HTML file in a code block.")),
    ])
    resp = results[0]
    if resp is None:
        await _safe_markdown(
            update.message,
            AI_UNAVAILABLE_MSG,
            reply_markup=back_btn())
        return True

    blocks = re.findall(r'```(?:html)?\n(.*?)```', resp or "", re.DOTALL)
    html = blocks[0] if blocks else (resp or "")
    if html.startswith('# file: '):
        html = '\n'.join(html.split('\n')[1:])
    try:
        await context.bot.send_document(
            update.effective_chat.id,
            io.BytesIO(html.encode('utf-8')),
            filename="index.html",
            caption="🎨 Your UI (index.html)"
        )
    except Exception:
        pass
    await _safe_markdown(
        update.message,
        resp[:3900] if resp else "Couldn't generate UI.",
        reply_markup=back_btn()
    )


# ==================== FORCE JOIN ====================

async def check_channel_membership(uid, context):
    channels = db.get_all_channels()
    if not channels:
        return True, []
    not_joined = []

    async def _check(ch):
        try:
            m = await context.bot.get_chat_member(ch['channel_id'], uid)
            return ch if m.status == 'left' else None
        except Exception:
            return None

    # Run all membership checks in parallel (was serial -> stacked latency).
    results = await asyncio.gather(*[_check(ch) for ch in channels])
    not_joined = [ch for ch in results if ch is not None]
    return len(not_joined) == 0, not_joined


def get_force_join_keyboard(chs):
    btns = []
    for ch in chs:
        url = f"https://t.me/{ch['channel_username']}" if ch['channel_username'] else f"https://t.me/c/{str(ch['channel_id'])[4:]}"
        btns.append([InlineKeyboardButton(ch['channel_name'], url=url)])
    btns.append([InlineKeyboardButton("Joined! Check", callback_data="check_join", style="success")])
    return InlineKeyboardMarkup(btns)


async def check_join_callback(update, context):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()
    joined, not_joined = await check_channel_membership(uid, context)
    if joined:
        try: await q.message.delete()
        except: pass
        # Auto-apply any pending referral from a /start ref_CODE deep-link.
        # User B gets credited too — no manual code entry required.
        applied = await apply_referral(uid, context)
        msg = f"**Access Granted!**\n\n{WELCOME_MESSAGE}"
        if applied:
            bonus = int(db.get_setting('referral_bonus', '20'))
            msg = (f"**Access Granted! 🎉**\n\nYou joined via a referral link — "
                   f"you and your friend each got **{bonus} credits**!\n\n{WELCOME_MESSAGE}")
        await context.bot.send_message(uid, msg, parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(uid))
    else:
        await q.edit_message_text(f"**{AGENT_NAME}**\n\nJoin all channels:", reply_markup=get_force_join_keyboard(not_joined), parse_mode=ParseMode.MARKDOWN)


# ==================== SESSIONS ====================

async def show_sessions(update, context, uid):
    sessions = db.get_user_sessions(uid)
    max_s = int(db.get_setting('max_sessions', '5'))

    if not sessions:
        text = "<b>Create Code</b>\n\n"
        text += "<blockquote>You have no sessions yet. Create your first one to start building with the AI agent.</blockquote>"
        btns = [
            [InlineKeyboardButton("New Session", callback_data="new_session", style="success")],
            [InlineKeyboardButton("Back to Menu", callback_data="menu_back", style="primary")]
        ]
    else:
        text = f"<b>Your Sessions ({len(sessions)}/{max_s})</b>\n\n"
        text += "<blockquote>"
        for s in sessions:
            text += f"<b>{s['session_name']}</b> — {s.get('project_type') or 'General'}\n"
            text += f"Updated: {s['updated_at']}\n\n"
        text += "Tap a session to continue.</blockquote>"
        btns = []
        for s in sessions:
            btns.append([
                InlineKeyboardButton(s['session_name'], callback_data=f"open_{s['id']}", style="primary"),
                InlineKeyboardButton("Delete", callback_data=f"del_{s['id']}", style="danger")
            ])
        if len(sessions) < max_s:
            btns.append([InlineKeyboardButton("New Session", callback_data="new_session", style="success")])
        btns.append([InlineKeyboardButton("Back to Menu", callback_data="menu_back", style="primary")])

    msg = text
    rp = InlineKeyboardMarkup(btns)
    if hasattr(update, 'callback_query') and update.callback_query:
        try: await update.callback_query.edit_message_text(msg, reply_markup=rp, parse_mode=ParseMode.HTML)
        except: await context.bot.send_message(uid, msg, reply_markup=rp, parse_mode=ParseMode.HTML)
    elif hasattr(update, 'message') and update.message:
        await update.message.reply_text(msg, reply_markup=rp, parse_mode=ParseMode.HTML)
    else:
        await context.bot.send_message(uid, msg, reply_markup=rp, parse_mode=ParseMode.HTML)


async def handle_new_session(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    db.set_user_state(uid, "select_session_type")
    await q.edit_message_text(
        "**New Session**\n\nSelect your project type:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("WEBSITE \U0001F310", callback_data="stype_website"),
             InlineKeyboardButton("MINIAPP \U0001F4F1", callback_data="stype_miniapp")],
            [InlineKeyboardButton("BOT \U0001F916", callback_data="stype_bot"),
             InlineKeyboardButton("OTHER \U0001F9A6", callback_data="stype_other")],
            [InlineKeyboardButton("\u2B05 Back", callback_data="menu_create")]
        ])
    )


SESSION_TYPE_MAP = {
    "stype_website": "Website",
    "stype_miniapp": "MiniApp",
    "stype_bot": "Telegram Bot",
    "stype_other": "Other",
}


async def handle_session_type_select(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    d = q.data
    if d not in SESSION_TYPE_MAP:
        return
    project_type = SESSION_TYPE_MAP[d]
    db.set_user_state(uid, "wait_session_name", data=project_type)
    emoji = {"Website": "\U0001F310", "MiniApp": "\U0001F4F1", "Telegram Bot": "\U0001F916", "Other": "\U0001F9A6"}.get(project_type, "")
    await q.edit_message_text(
        f"**{emoji} {project_type}** selected!\n\n"
        f"Enter a name for your session:\nExample: `Portfolio`, `My Bot`, `Snake Game`",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_btn("Cancel", "menu_create")
    )


async def handle_session_name_input(update, context):
    uid = update.effective_user.id
    state = db.get_user_state(uid)
    if not state or state['state'] != 'wait_session_name':
        return False

    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("Name cannot be empty! Try a name like `My App`.")
        return True

    max_s = int(db.get_setting('max_sessions', '5'))

    # Reject a name the user already owns (per-user uniqueness).
    existing = db.get_user_sessions(uid)
    if any(s['session_name'].lower() == name.lower() for s in existing):
        await update.message.reply_text(
            f"You already have a session named **{name}**. Pick a different name "
            f"or delete the old one from the menu.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_btn("Back", "menu_create"))
        return True

    # Enforce the per-user max-session cap.
    if len(existing) >= max_s:
        await update.message.reply_text(
            f"**Session limit reached ({len(existing)}/{max_s}).**\n\n"
            f"Delete an old session from the menu before creating a new one.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_btn("Back to Sessions", "menu_create"))
        return True

    # Create the session (unique name guaranteed by the checks above).
    project_type = state.get('data') or 'General'
    sid = db.create_session(uid, name, project_type=project_type)
    if not sid:
        await update.message.reply_text(
            "Couldn't create that session. Try a different name.",
            reply_markup=back_btn("Back", "menu_create"))
        db.clear_user_state(uid)
        return True

    db.set_user_state(uid, "create_session_requirements", data=str(sid))
    await update.message.reply_text(
        f"**Session '{name}' created!** 🤖\n\n"
        f"Now tell me what to build — describe it in one or two lines.\n"
        f"**Example:** _Build a calculator_ / _Dark-theme portfolio website_ / _A Telegram bot that replies hello_\n\n"
        f"I'll make a **plan** first. I only start building after you approve it. 👇",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_btn("Back", "menu_create")
    )
    return True


async def open_session(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    sid = int(q.data.replace("open_", ""))

    session = db.get_session_by_id(sid)
    if not session:
        await q.edit_message_text("Session not found!")
        return

    db.set_user_state(uid, "session_chat", data=str(sid))

    ctx = session.get('context_data', {}) or {}
    code = session.get('code_files', []) or []

    text = f"**Session: {session['session_name']}**\n\n"
    text += f"Project: {session.get('project_type') or 'General'}\n"
    if ctx.get('requirements'):
        text += f"Requirements: {ctx['requirements'][:120]}{'...' if len(ctx.get('requirements',''))>120 else ''}\n"
    if ctx.get('plan'):
        text += f"Plan: saved ✅\n"
    if code:
        text += f"Code files: {len(code)} (I remember what we built — just tell me to fix/change something)\n"
    text += "\nSend me any message to continue working."

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Back to Menu", callback_data="menu_back", style="primary")]
    ]), parse_mode=ParseMode.MARKDOWN)


async def confirm_delete_session(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    sid = int(q.data.replace("del_", ""))
    session = db.get_session_by_id(sid)
    if not session:
        await q.edit_message_text("Session not found!")
        return

    await q.edit_message_text(
        f"Delete **{session['session_name']}**?\n\nThis cannot be undone.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes, Delete", callback_data=f"delok_{sid}", style="danger"),
             InlineKeyboardButton("Cancel", callback_data="menu_create", style="primary")]
        ])
    )


async def do_delete_session(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    sid = int(q.data.replace("delok_", ""))
    db.delete_session_by_id(uid, sid)
    await q.edit_message_text("Session deleted!")
    await show_sessions(q, context, uid)


# ==================== SESSION CHAT ====================

async def handle_session_chat(update, context):
    uid = update.effective_user.id
    state = db.get_user_state(uid)
    if not state or state['state'] != 'session_chat':
        return False

    sid = int(state['data'])
    session = db.get_session_by_id(sid)
    if not session:
        await update.message.reply_text("Session not found!")
        db.clear_user_state(uid)
        return True

    msg = update.message.text.strip()
    if not msg:
        return True

    # Load current session code up front (needed for the plan-first gate below).
    session = db.get_session_by_id(sid)
    code = (session.get('code_files', []) or []) if session else []

    # PLAN-FIRST gate: if this session has NOT built anything yet and the user
    # asks to build something, show a PLAN first (with Approve / Plan More / Back)
    # instead of generating code directly. Once code exists, requests go straight
    # to build/fix (agent behavior).
    build_intent = bool(re.search(
        r"\b(build|create|write|make|generate|code|program|function|script|app|website|"
        r"api|class|bot|scraper|automation|develop|design|calculator|portfolio|game|tool)\b",
        msg, re.IGNORECASE))
    if build_intent and not code:
        db.update_session_context(sid, {
            "requirements": msg,
            "project_type": session.get('project_type') or 'General',
            "step": "generate"
        })
        plan_prompt = (
            f"You are OXYGENT, an autonomous AI coding AGENT. A user wants to build something.\n"
            f"Project type: {session.get('project_type') or 'General'}\n"
            f"Request: {msg}\n\n"
            "Produce a concise IMPLEMENTATION PLAN (plain text, no code). Cover:\n"
            "1. Recommended language/stack\n"
            "2. Files to create (list with one-line purpose each)\n"
            "3. Key features / steps\n"
            "4. How to run it\n"
            "Keep it tight and scannable."
        )
        await update.message.reply_text("Generating plan...")
        plan = await _typing_while(update, context, _zen_chat(plan_prompt))
        if plan is None:
            plan = "Couldn't generate a plan right now. Tap Approve to start building anyway, or Plan More to add details."
        db.update_session_context(sid, {"plan": plan, "step": "approval"})
        plan_text = _plan_md(f"**Plan for {session['session_name']}**", plan)
        await _safe_markdown(update.message, plan_text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve & Build", callback_data=f"plan_approve_{sid}", style="success"),
             InlineKeyboardButton("✏️ Plan More", callback_data=f"plan_more_{sid}", style="primary")],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back", style="primary")]
        ]))
        return True

    ctx = session.get('context_data', {}) or {}
    reqs = ctx.get('requirements', '')
    plan = ctx.get('plan', '')

    prompt = (
        "You are OXYGENT, an autonomous AI coding AGENT (not a rigid code generator). "
        "You can BOTH hold a normal conversation AND write/fix real code when asked.\n\n"
        "CONTEXT (this session):\n"
        f"Session name: {session['session_name']}\n"
        f"Project type: {session.get('project_type') or 'General'}\n"
    )
    if reqs:
        prompt += f"Requirements: {reqs[:800]}\n"
    if plan:
        prompt += f"Plan: {plan[:500]}\n"
    if code:
        prompt += "\nEXISTING CODE FILES in this session (edit THESE when the user asks for a fix/change):\n"
        for i, entry in enumerate(code[:5]):
            if isinstance(entry, dict) and entry.get("filename"):
                prompt += f"\n--- {entry['filename']} ---\n{entry.get('content','')[:1500]}\n"
            else:
                prompt += f"\n--- File {i+1} ---\n{str(entry)[:1500]}\n"
    prompt += (
        "\nBEHAVIOR RULES:\n"
        "1. Judge the user's INTENT first.\n"
        "2. If it's casual chat, a greeting, a question, brainstorming, or planning -> "
        "REPLY CONVERSATIONALLY. Do NOT generate code and do NOT create files. Just talk like a smart dev friend.\n"
        "3. If the user asks to build/create/write/make/generate/fix/debug/change/update/modify/refactor code "
        "or a specific program, file, function, app, website, API -> WRITE/UPDATE CODE.\n"
        "4. When writing code, return fenced code blocks. If updating an existing file, the block's FIRST line "
        "MUST be `# file: <filename>` (use the same name as the file you're editing) then the FULL new file content.\n"
        "5. For a new multi-file build, create up to 5 files with `# file:` first lines. No explanations outside the code blocks.\n"
        "6. Keep conversational replies concise and natural. Match the user's language/tone.\n\n"
        f"User: {msg}\n\n"
        "Respond according to the intent rules above."
    )

    # Detect whether the user is asking for code (build/fix) vs casual chat.
    code_intent = bool(re.search(
        r"\b(build|create|write|make|generate|code|program|function|script|app|website|"
        r"api|class|bot|scraper|automation|fix|debug|refactor|implement|develop|design|"
        r"change|update|modify|edit|add|remove|delete)\b",
        msg, re.IGNORECASE))

    # Route to the agent when this session already built code, UNLESS the
    # message is pure casual chit-chat (greeting/thanks/bye). The agent itself
    # judges chat-vs-edit internally (its system prompt says so), which handles
    # Hinglish fix requests like "button color red kr do" / "bhai ye bug fix kr"
    # that a narrow keyword regex would miss.
    is_casual = bool(re.match(
        r"^\s*(hi+|hey+|hello+|yo+|hiya|thanks+|thx+|ty+|ok+|okay+|k+|hmm+|bye+|gn+|good\s*(morning|night)|"
        r"namaste|सुप्रभात|धन्यवाद|हेलो|हाय)\b",
        msg, re.IGNORECASE))
    route_to_agent = code_intent or build_intent or (bool(code) and not is_casual)

    if route_to_agent:
        seed = {}
        if code:
            for entry in code[:5]:
                if isinstance(entry, dict) and entry.get("filename"):
                    seed[entry["filename"]] = entry.get("content", "")
                else:
                    seed[f"file_{len(seed)}.txt"] = str(entry)
        fix_req = (
            f"PROJECT: {session['session_name']}\n"
            f"TYPE: {session.get('project_type') or 'General'}\n"
            f"USER REQUEST: {msg}\n\n"
            "The existing files are already in your sandbox. If this is a fix/change, "
            "read_file the relevant file then patch_file it. If it's a new build, create files. "
            "When done, reply with a short summary (no tool calls)."
        )

        # Run agent_build with a timeout so it never hangs forever
        result = None
        try:
            async def _build_coro():
                return await ae.agent_build(uid, sid, fix_req, seed_files=seed if seed else None)
            task = asyncio.ensure_future(_build_coro())
            overall = asyncio.ensure_future(asyncio.wait_for(task, timeout=900.0))
            while not overall.done():
                try:
                    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
                except Exception:
                    pass
                try:
                    await asyncio.wait_for(asyncio.shield(overall), timeout=4.0)
                except asyncio.TimeoutError:
                    continue
                break
            result = await overall
        except (asyncio.TimeoutError, Exception):
            result = None

        # Handle pending approval — show buttons to user
        if result and result.get("pending_approval"):
            pending = result["pending_approval"]
            await _show_approval_buttons(update, context, uid, pending)
            return True

        if not result or not result.get("ok") or not result.get("files"):
            err = result.get("error", "") if result else "timeout"
            await _safe_markdown(
                update.message,
                f"⚠️ Build failed ({err}). Try again or send a different request.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back", style="primary")
                ]])
            )
            return True
        new_files = list(result["files"].items())[:MAX_BUILD_FILES]
        db.update_session_code(sid, [{"filename": fn, "content": c} for fn, c in new_files])
        for fn, c in new_files:
            try:
                await context.bot.send_document(
                    uid, io.BytesIO(c.encode('utf-8')),
                    filename=fn, caption=f"Updated: {fn}"
                )
            except Exception:
                pass
        summary = result.get("summary", "")[:800]
        body = summary or "Done. Files updated."
        await _safe_markdown(update.message, body,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back", style="primary")
            ]])
        )
        return True

    # Otherwise: normal conversational reply (no files created).
    response = await _typing_while(update, context, _zen_chat(prompt, SYSTEM_PROMPT))

    body = response[:4000] if response else "Sorry, I had trouble generating a response. Try rephrasing."
    await _safe_markdown(update.message, body,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Back to Menu", callback_data="menu_back", style="primary")
        ]])
    )
    return True


# ==================== CALLBACK ROUTER ====================

async def main_callback_handler(update, context):
    q = update.callback_query
    d = q.data

    # Acknowledge the callback IMMEDIATELY so Telegram shows the tap as handled
    # (instant feedback). Without this, the button feels "slow / not responding"
    # because Telegram keeps showing a loading spinner until we finally edit.
    try:
        await q.answer()
    except Exception:
        pass

    if d == "check_join":
        await check_join_callback(update, context); return
    if d.startswith("stype_"):
        await handle_session_type_select(update, context); return
    if d.startswith("plan_approve_") or d.startswith("plan_more_") or d.startswith("plan_cancel_"):
        await plan_callback(update, context); return
    if d.startswith("delok_"):
        await do_delete_session(update, context); return
    if d.startswith("del_"):
        await confirm_delete_session(update, context); return
    if d.startswith("open_"):
        await open_session(update, context); return
    if d.startswith("proj_"):
        await handle_project_type(update, context); return
    if d.startswith("buy_"):
        await handle_buy(update, context); return
    if d.startswith("admin_"):
        await admin_callback(update, context); return
    if d.startswith("approve_") or d.startswith("reject_"):
        await handle_approval_callback(update, context); return
    if d == "selftest":
        await selftest_command(update, context, edit_mode=True); return
    if d == "bc_approve":
        await broadcast_approve(update, context); return
    if d == "bc_cancel":
        await broadcast_cancel(update, context); return
    if d.startswith("ref_"):
        await handle_ref_callback(update, context); return

    if d == "menu_create":
        await show_sessions(q, context, q.from_user.id); return
    if d == "new_session":
        await handle_new_session(update, context); return
    if d == "menu_sessions":
        await show_sessions(q, context, q.from_user.id); return
    if d == "menu_profile":
        await show_profile(q, context); return
    if d == "menu_refer":
        await show_refer(q, context); return
    if d == "menu_buy":
        await show_buy(q, context); return
    if d == "menu_support":
        await show_support(q, context); return
    if d == "menu_back":
        uid = q.from_user.id
        db.clear_user_state(uid)
        await q.edit_message_text("**Menu**", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(uid)); return
    if d == "menu_admin":
        await admin_panel(update, context); return
    if d == "cancel":
        uid = q.from_user.id
        db.clear_user_state(uid)
        await q.edit_message_text("**Cancelled.**", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(uid)); return


# ==================== PROFILE ====================

async def show_profile(q, context):
    uid = q.from_user.id
    prof = db.get_user_profile(uid, datetime.date.today().isoformat())
    if not prof:
        await q.edit_message_text("Use /start first.", reply_markup=back_btn())
        return
    u = prof['user']
    rem, daily, bonus, used = prof['remaining'], prof['daily'], prof['bonus'], prof['used']
    sessions = prof['sessions']
    max_s = int(db.get_setting('max_sessions', '5'))
    ref = u.get('referral_code') or db.generate_referral_code(uid)
    refs = prof['referred_count']

    t = "<b>My Profile</b>\n\n"
    t += "<blockquote>"
    t += f"<b>Name:</b> {u.get('first_name', 'N/A')} {u.get('last_name', '')}\n"
    t += f"<b>Username:</b> @{u.get('username', 'N/A')}\n"
    t += f"<b>ID:</b> <code>{uid}</code>\n\n"
    t += f"<b>Free Messages:</b> {used}/{daily} (resets daily)\n"
    t += f"<b>Bonus Credits:</b> {bonus} (from referrals/stars)\n"
    t += f"<b>Total Available:</b> {rem}\n"
    ref_bonus = db.get_setting('referral_bonus', '20')
    t += f"<b>How it works:</b> You get {daily} free messages every day. "
    t += f"Every friend you refer adds +{ref_bonus} bonus messages "
    t += f"(permanent, used after free ones run out).\n\n"
    t += f"<b>Sessions:</b> {len(sessions)}/{max_s}\n"
    t += f"<b>Friends Referred:</b> {refs}\n"
    t += f"<b>Joined:</b> {u.get('joined_at', 'N/A')}"
    t += "</blockquote>"

    await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Buy Credit", callback_data="menu_buy", style="success"),
         InlineKeyboardButton("Refer & Earn", callback_data="menu_refer", style="primary")],
        [InlineKeyboardButton("Back to Menu", callback_data="menu_back", style="primary")]
    ]), parse_mode=ParseMode.HTML)


# ==================== REFER ====================

async def show_refer(q, context):
    uid = q.from_user.id
    ref = db.generate_referral_code(uid)
    refs = db.get_referred_count(uid)
    bonus = int(db.get_setting('referral_bonus', '20'))

    t = "<b>Refer &amp; Earn</b> 🎉\n\n"
    t += f"<b>Friends Referred:</b> {refs}\n"
    t += f"<b>Bonus:</b> {bonus} credits each (auto-credited on join)\n\n"
    t += "<blockquote>Share your link below. When someone starts the bot through it and joins the channel, both of you get the bonus automatically — no code entry needed.</blockquote>\n\n"
    t += f"<code>https://t.me/{context.bot.username}?start=ref_{ref}</code>"

    await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Back to Menu", callback_data="menu_back", style="primary")]
    ]), parse_mode=ParseMode.HTML)


async def handle_ref_callback(update, context):
    # Manual code entry removed — referral is fully automatic via the
    # /start ref_CODE deep-link (credited on channel join). Any stray
    # "ref_" callback just re-shows the Refer & Earn card.
    q = update.callback_query
    await q.answer()
    await show_refer(q, context)


async def apply_referral(uid: int, context=None) -> bool:
    """
    Credit a referral for `uid` using their PENDING referral code (set via
    /start ref_CODE deep-link OR the manual 'Enter Code' flow).

    Returns True if a referral was successfully applied (first time only).
    Credits BOTH the referrer and the new user with the configured bonus.
    Idempotent: if already referred, returns False.
    """
    u = db.get_user(uid)
    if u and u.get('referred_by'):
        db.clear_user_state(uid)  # drop stale pending_ref if any
        return False

    state = db.get_user_state(uid)
    code = state['data'] if state and state.get('state') == 'pending_ref' else None
    if not code:
        return False

    referrer = db.get_user_by_referral_code(code)
    if not referrer or referrer['user_id'] == uid:
        db.clear_user_state(uid)
        return False

    bonus = int(db.get_setting('referral_bonus', '20'))
    db.set_referred_by(uid, referrer['user_id'])
    db.credit_referrer(referrer['user_id'], bonus)
    db.add_bonus_messages(uid, bonus)
    db.clear_user_state(uid)
    
    # Notify the referrer (User A) that User B joined via their link
    try:
        referrer_name = u.get('first_name') or u.get('username') or 'Someone'
        await context.bot.send_message(
            referrer['user_id'],
            f"🎉 <b>New Referral!</b>\n\n<b>{referrer_name}</b> joined via your link.\nYou both received <b>{bonus} credits</b>!",
            parse_mode=ParseMode.HTML
        )
    except Exception:
        pass  # Best effort - don't crash if notification fails
    
    return True


# ==================== BUY ====================

async def show_buy(q, context):
    t = "<b>Buy Credits</b>\n\n"
    t += "<blockquote>Select a package and pay with <b>Telegram Stars</b>.\n\n<b>1 Credit = 1 message</b></blockquote>"
    btns = [
        [InlineKeyboardButton("10 Credits - 3 Stars", callback_data="buy_3", style="success"),
         InlineKeyboardButton("35 Credits - 10 Stars", callback_data="buy_10", style="success")],
        [InlineKeyboardButton("120 Credits - 30 Stars", callback_data="buy_30", style="success"),
         InlineKeyboardButton("400 Credits - 100 Stars", callback_data="buy_100", style="success")],
        [InlineKeyboardButton("1500 Credits - 300 Stars", callback_data="buy_300", style="success")],
        [InlineKeyboardButton("Back to Menu", callback_data="menu_back", style="primary")]
    ]
    await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.HTML)


async def handle_buy(update, context):
    q = update.callback_query
    await q.answer()
    d = q.data
    if not d.startswith("buy_"):
        return
    raw = d.replace("buy_", "")
    if not raw.isdigit():
        return  # e.g. buy_cancel - ignore
    stars = int(raw)
    pkgs = {3: 10, 10: 35, 30: 120, 100: 400, 300: 1500}
    if stars not in pkgs: return
    credits = pkgs[stars]
    uid = q.from_user.id
    prices = [LabeledPrice(f"{credits} Credits", stars)]
    payload = f"credit_{credits}:{uid}"
    await context.bot.send_invoice(q.message.chat.id, f"{credits} Credits", f"Get {credits} credits for {stars} Stars.", payload, "XTR", prices, "")


# ==================== SUPPORT ====================

async def show_support(q, context):
    t = "<b>Support</b> ☎️\n\n"
    t += "<blockquote>Stuck? Need help?\nJoin our support group and we'll resolve it fast.</blockquote>"
    support_link = "https://t.me/+YXwFGkYYjdJlNjE1"
    rp = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 Join Support Group", url=support_link)],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_back", style="success")],
    ])
    await q.edit_message_text(t, reply_markup=rp, parse_mode=ParseMode.HTML)


# ==================== PLAN FLOW ====================

async def plan_callback(update, context):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id

    if d.startswith("plan_approve_"):
        sid = int(d.replace("plan_approve_", ""))
        await q.edit_message_text("Building your project...", parse_mode=ParseMode.MARKDOWN)
        await build_from_plan(q, context, sid)
    elif d.startswith("plan_more_"):
        sid = int(d.replace("plan_more_", ""))
        db.set_user_state(uid, "plan_more", data=str(sid))
        await q.edit_message_text("Tell me what to change or add to the plan:", parse_mode=ParseMode.MARKDOWN)
    elif d.startswith("plan_cancel_"):
        db.clear_user_state(uid)
        await q.edit_message_text("Plan cancelled.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(uid))


MAX_BUILD_FILES = 5


# ==================== TOOL APPROVAL SYSTEM ====================

TOOL_LABELS = {
    "write_file": "📝 Create/Edit File",
    "patch_file": "✏️ Patch File",
    "terminal": "🖥️ Run Terminal Command",
    "execute_code": "▶️ Execute Code",
}


def _format_approval_text(pending: list) -> str:
    """Build a readable message listing all tool calls needing approval."""
    lines = ["**🔧 Actions Requiring Approval**\n"]
    lines.append("The AI wants to perform these actions:\n")
    for i, tc in enumerate(pending, 1):
        label = TOOL_LABELS.get(tc["name"], tc["name"])
        args = tc.get("args", {})
        detail = ""
        if tc["name"] == "write_file":
            detail = f"File: `{args.get('path', '?')}` ({len(args.get('content', ''))} chars)"
        elif tc["name"] == "patch_file":
            detail = f"File: `{args.get('path', '?')}`"
        elif tc["name"] == "terminal":
            detail = f"Command: `{args.get('command', '?')[:80]}`"
        elif tc["name"] == "execute_code":
            detail = f"Language: {args.get('language', '?')}"
        lines.append(f"**{i}.** {label}\n   {detail}\n")
    lines.append("Approve or reject each action:")
    return "\n".join(lines)


def _approval_keyboard(pending: list) -> InlineKeyboardMarkup:
    """Build approve/reject buttons for pending tool calls."""
    btns = []
    # Single approve all / reject all
    btns.append([
        InlineKeyboardButton("✅ Approve All", callback_data="approve_all", style="success"),
        InlineKeyboardButton("❌ Reject All", callback_data="reject_all", style="danger"),
    ])
    # Individual approve/reject for each tool
    for tc in pending:
        label = TOOL_LABELS.get(tc["name"], tc["name"])
        btns.append([
            InlineKeyboardButton(f"✅ {label}", callback_data=f"approve_{tc['id']}", style="success"),
            InlineKeyboardButton(f"❌ Reject", callback_data=f"reject_{tc['id']}", style="danger"),
        ])
    return InlineKeyboardMarkup(btns)


async def _show_approval_buttons(update, context, uid, pending):
    """Send the approval request message with buttons."""
    text = _format_approval_text(pending)
    kb = _approval_keyboard(pending)
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def handle_approval_callback(update, context):
    """Handle approve/reject button taps."""
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    d = q.data

    state = db.get_user_state(uid)
    if not state or state['state'] != 'session_chat':
        await q.edit_message_text("Session expired. Start a new session.")
        return

    sid = int(state['data'])
    pending = ae.get_pending_approvals(uid)
    if not pending:
        await q.edit_message_text("No pending actions to approve.")
        return

    approved_ids = []

    if d == "approve_all":
        approved_ids = [tc["id"] for tc in pending]
        await q.edit_message_text("✅ **All actions approved.** Resuming build...", parse_mode=ParseMode.MARKDOWN)
    elif d == "reject_all":
        approved_ids = []
        await q.edit_message_text("❌ **All actions rejected.** Build stopped.", parse_mode=ParseMode.MARKDOWN)
    elif d.startswith("approve_"):
        tc_id = d.replace("approve_", "")
        approved_ids = [tc_id]
        await q.edit_message_text(f"✅ **Action approved.** Resuming...", parse_mode=ParseMode.MARKDOWN)
    elif d.startswith("reject_"):
        tc_id = d.replace("reject_", "")
        approved_ids = []
        await q.edit_message_text(f"❌ **Action rejected.** Build stopped.", parse_mode=ParseMode.MARKDOWN)
    else:
        return

    # Resume the agent with approval results
    result = await ae.agent_resume(uid, sid, approved_ids)

    # Handle another round of pending approval
    if result and result.get("pending_approval"):
        pending2 = result["pending_approval"]
        text = _format_approval_text(pending2)
        kb = _approval_keyboard(pending2)
        await context.bot.send_message(uid, text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        return

    if not result or not result.get("ok") or not result.get("files"):
        await context.bot.send_message(uid,
            "⚠️ Build completed with issues or the AI is unavailable.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back", style="primary")
            ]])
        )
        return

    # Deliver files
    new_files = list(result["files"].items())[:MAX_BUILD_FILES]
    db.update_session_code(sid, [{"filename": fn, "content": c} for fn, c in new_files])
    for fn, c in new_files:
        try:
            await context.bot.send_document(
                uid, io.BytesIO(c.encode('utf-8')),
                filename=fn, caption=f"Updated: {fn}"
            )
        except Exception:
            pass
    summary = result.get("summary", "")[:800]
    body = summary or "Done. Files updated."
    await context.bot.send_message(uid, body, parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back", style="primary")
        ]])
    )


async def build_from_plan(q, context, sid):
    """Generate the project from the approved plan and deliver files (max 5).
    Files are also saved to the user sandbox and the session for later fixes."""
    from coding_tools import cleanup_sandbox
    import os

    session = db.get_session_by_id(sid)
    if not session:
        await q.edit_message_text("Session not found!")
        return
    pt = session.get('project_type', 'General')
    ctx = session.get('context_data', {}) or {}
    reqs = ctx.get('requirements', '')
    plan = ctx.get('plan', '')

    cid = q.message.chat.id
    uid = q.from_user.id

    build_req = (
        f"PROJECT: {session['session_name']}\n"
        f"TYPE: {pt}\nREQUIREMENTS: {reqs}\nPLAN:\n{plan}\n\n"
        "Build this now using the write_file tool. Create up to 5 files. "
        "When done, reply with a short summary (no tool calls)."
    )

    result = None
    try:
        async def _build_coro():
            return await ae.agent_build(uid, sid, build_req, seed_files=None)
        task = asyncio.ensure_future(_build_coro())
        overall = asyncio.ensure_future(asyncio.wait_for(task, timeout=900.0))
        while not overall.done():
            try:
                await context.bot.send_chat_action(cid, ChatAction.TYPING)
            except Exception:
                pass
            try:
                await asyncio.wait_for(asyncio.shield(overall), timeout=4.0)
            except asyncio.TimeoutError:
                continue
            break
        result = await overall
    except (asyncio.TimeoutError, Exception):
        result = None

    # Handle pending approval — send approval message to the chat
    if result and result.get("pending_approval"):
        pending = result["pending_approval"]
        text = _format_approval_text(pending)
        kb = _approval_keyboard(pending)
        await context.bot.send_message(cid, text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
        return

    if not result or not result.get("ok") or not result.get("files"):
        await _safe_markdown(
            q.message,
            "⚠️ Build timed out or the AI is unavailable right now. Tap **Approve** to retry, or **Back to Menu**.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Retry Build", callback_data=f"plan_approve_{sid}", style="success")
            ], [
                InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back", style="primary")
            ]])
        )
        return

    files = list(result["files"].items())[:MAX_BUILD_FILES]

    db.update_session_code(sid, [{"filename": fn, "content": code} for fn, code in files])

    for fn, code in files:
        try:
            await context.bot.send_document(
                cid, io.BytesIO(code.encode('utf-8')), filename=fn, caption=fn
            )
        except Exception:
            pass

    summary = result.get("summary", "")
    await _safe_markdown(
        q.message,
        f"✅ **Built `{session['session_name']}`** — {len(files)} file(s) ready.\n\n"
        f"{summary[:800]}\n\n"
        f"Send a fix/change request here (e.g. \"bhai ye bug hai fix kr\") and I'll update the code. "
        f"Or tap Back to Menu for a fresh session.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back", style="primary")
        ]])
    )
    db.set_user_state(uid, "session_chat", data=str(sid))


# ==================== PROJECT TYPE ====================

async def handle_project_type(update, context):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    d = q.data

    state = db.get_user_state(uid)
    if not state or state['state'] != 'create_session_type':
        return

    types = {"proj_bot": "Telegram Bot", "proj_web": "Website", "proj_api": "API Server", "proj_app": "Mobile App", "proj_ml": "AI/ML", "proj_other": "Other"}
    if d not in types: return

    sid = int(state['data'])
    db.update_session_context(sid, {"project_type": types[d], "step": "requirements"})
    session = db.get_session_by_id(sid)
    db.set_user_state(uid, "create_session_requirements", data=str(sid))

    await q.edit_message_text(
        f"Project: **{types[d]}**\n\nDescribe what you want to build:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=back_btn("Cancel", "menu_create")
    )


# ==================== ADMIN ====================

async def admin_panel(update, context):
    uid = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    if uid not in ADMIN_IDS:
        if hasattr(update, 'message') and update.message:
            await update.message.reply_text("Admin only!")
        else:
            await update.callback_query.answer("Admin only!", show_alert=True)
        return

    t = db.get_user_count()
    s = db.get_total_stars_received()
    m = db.get_setting('max_sessions', '5')
    rb = db.get_setting('referral_bonus', '20')
    chan = db.get_channel_count() if hasattr(db, 'get_channel_count') else '?'

    text = (
        f"**🛡️ Admin Panel**\n\n"
        f"👥 **Users:** {t}\n"
        f"⭐ **Stars Received:** {s}\n"
        f"📡 **Channels:** {chan}\n"
        f"🎯 **Max Sessions:** {m}\n"
        f"🎁 **Referral Bonus:** {rb}\n\n"
        f"Tap a button below to manage."
    )
    btns = [
        [InlineKeyboardButton("Stats", callback_data="admin_stats", style="primary"),
         InlineKeyboardButton("User Check", callback_data="admin_users", style="primary")],
        [InlineKeyboardButton("Broadcast", callback_data="admin_broadcast", style="primary"),
         InlineKeyboardButton("Manage Channels", callback_data="admin_channels", style="success")],
        [InlineKeyboardButton("Ban User", callback_data="admin_ban", style="danger"),
         InlineKeyboardButton("Unban", callback_data="admin_unban", style="success")],
        [InlineKeyboardButton("Daily Limit", callback_data="admin_daily", style="primary"),
         InlineKeyboardButton("Max Sessions", callback_data="admin_maxsessions", style="primary")],
        [InlineKeyboardButton("Referral Bonus", callback_data="admin_refbonus", style="primary"),
         InlineKeyboardButton("Health Check", callback_data="selftest", style="primary")],
        [InlineKeyboardButton("Back to Menu", callback_data="menu_back", style="primary")]
    ]

    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)


async def show_users(q, context):
    """Admin: list every user as inline buttons + a plain-text summary.

    Each row shows the user (name @username / id) and a 'View' button that
    opens that user's detail card. A 'Back' button returns to the Admin Panel.
    """
    users = db.get_all_users()
    total = len(users)

    # Plain-text summary (newest first)
    lines = [f"**All Users ({total})**\n"]
    for i, u in enumerate(users, 1):
        name = u.get('first_name') or u.get('username') or 'unknown'
        uname = f"@{u['username']}" if u.get('username') else ''
        ref = f" ← ref {u['referred_by']}" if u.get('referred_by') else ''
        banned = " 🚫" if u.get('is_banned') else ""
        lines.append(f"{i}. {name} {uname} `{u['user_id']}`{ref}{banned}")

    text = "\n".join(lines)

    # Inline buttons: one 'View' per user (2 per row) + Back
    btns = []
    row = []
    for u in users:
        label = (u.get('first_name') or u.get('username') or str(u['user_id']))[:12]
        row.append(InlineKeyboardButton(f"👤 {label}", callback_data=f"admin_user_{u['user_id']}", style="primary"))
        if len(row) == 2:
            btns.append(row); row = []
    if row:
        btns.append(row)
    btns.append([InlineKeyboardButton("Back to Admin", callback_data="admin_users_back", style="primary")])

    try:
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
    except Exception:
        # Markdown parse can fail on weird usernames — fall back to plain text
        plain = text.replace("**", "").replace("`", "")
        await q.edit_message_text(plain, reply_markup=InlineKeyboardMarkup(btns))


async def show_user_detail(q, context, uid: int):
    """Admin: detail card for a single user."""
    u = db.get_user(uid)
    if not u:
        await q.answer("User not found", show_alert=True); return
    name = u.get('first_name') or 'unknown'
    uname = f"@{u['username']}" if u.get('username') else '(no username)'
    referrer = db.get_user(u['referred_by']) if u.get('referred_by') else None
    ref_txt = f"{referrer.get('first_name') or referrer.get('username')} (`{u['referred_by']}`)" if referrer else "—"
    text = (
        f"**User Detail**\n\n"
        f"**Name:** {name}\n"
        f"**Username:** {uname}\n"
        f"**ID:** `{u['user_id']}`\n"
        f"**Referral Code:** `{u.get('referral_code') or '—'}`\n"
        f"**Referred By:** {ref_txt}\n"
        f"**Bonus Credits:** {u.get('bonus_messages', 0)}\n"
        f"**Banned:** {'Yes 🚫' if u.get('is_banned') else 'No'}\n"
        f"**Joined:** {u.get('joined_at')}"
    )
    btns = [[InlineKeyboardButton("Back to Users", callback_data="admin_users", style="primary")]]
    try:
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN)
    except Exception:
        plain = text.replace("**", "").replace("`", "")
        await q.edit_message_text(plain, reply_markup=InlineKeyboardMarkup(btns))


# ==================== CLONE -> MAIN DEPLOY ====================


async def admin_callback(update, context):

    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    if uid not in ADMIN_IDS:
        await q.edit_message_text("Admin only!"); return
    d = q.data

    if d == "admin_stats":
        st = db.get_bot_stats()
        users = st.get('users', 0)
        banned = st.get('banned', 0)
        referred = st.get('referred', 0)
        channels = st.get('channels', 0)
        sessions = st.get('sessions', 0)
        active = st.get('active_states', 0)
        stars = st.get('stars', 0)
        payments = st.get('payments', 0)
        bonus = st.get('bonus_given', 0)
        new24 = st.get('new_24h', 0)
        top = st.get('top_referrer')
        top_txt = ""
        if top:
            rid = top.get('referred_by')
            cnt = top.get('c')
            uname = "—"
            try:
                ru = db.get_user(rid)
                if ru:
                    uname = ru.get('username') and f"@{ru['username']}" or str(rid)
            except Exception:
                pass
            top_txt = f"\n🔝 **Top Referrer:** {uname} ({cnt} refs)"
        text = (
            f"📊 **Bot Statistics**\n\n"
            f"👥 **Total Users:** {users}\n"
            f"   ├ 🆕 New (24h): {new24}\n"
            f"   ├ 🚫 Banned: {banned}\n"
            f"   └ 🔗 Via Referral: {referred}\n"
            f"⭐ **Stars Received:** {stars}\n"
            f"💳 **Payments:** {payments}\n"
            f"🎁 **Bonus Credits Given:** {bonus}\n"
            f"📡 **Channels:** {channels}\n"
            f"💻 **Code Sessions:** {sessions}\n"
            f"🟢 **Active States:** {active}"
            f"{top_txt}"
        )
        await q.edit_message_text(text, reply_markup=back_btn("Back", "menu_admin"), parse_mode=ParseMode.MARKDOWN); return

    if d == "admin_users":
        await show_users(q, context); return

    if d.startswith("admin_user_"):
        # admin_user_<id> -> show single user detail
        try:
            uid = int(d.split("_", 2)[2])
        except Exception:
            await q.answer("Bad user id", show_alert=True); return
        await show_user_detail(q, context, uid); return

    if d == "admin_users_back":
        await admin_panel(update, context); return

    if d == "admin_broadcast":
        db.set_user_state(uid, "admin_broadcast")
        await q.edit_message_text("**Broadcast**\n\nSend the message:", parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn("Cancel", "menu_admin")); return

    if d == "admin_ban":
        db.set_user_state(uid, "admin_ban")
        await q.edit_message_text("**Ban User**\n\nSend user ID:", parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn("Cancel", "menu_admin")); return

    if d == "admin_unban":
        db.set_user_state(uid, "admin_unban")
        await q.edit_message_text("**Unban User**\n\nSend user ID:", parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn("Cancel", "menu_admin")); return

    if d == "admin_daily":
        db.set_user_state(uid, "admin_daily")
        await q.edit_message_text("**Daily Limit**\n\nSend new limit:", parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn("Cancel", "menu_admin")); return

    if d == "admin_maxsessions":
        db.set_user_state(uid, "admin_maxsessions")
        await q.edit_message_text("**Max Sessions**\n\nSend new limit:", parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn("Cancel", "menu_admin")); return

    if d == "admin_refbonus":
        cur = db.get_setting('referral_bonus', '20')
        db.set_user_state(uid, "admin_refbonus")
        await q.edit_message_text(f"**Referral Bonus**\n\nCurrent: {cur} credits per referral.\n\nSend the new amount (a number):", parse_mode=ParseMode.MARKDOWN, reply_markup=back_btn("Cancel", "menu_admin")); return

    if d == "admin_channels":
        channels = db.get_all_channels()
        if not channels:
            t = "**Manage Channels**\n\nNo channels added yet."
        else:
            t = f"**Manage Channels**\n\nChannels: {len(channels)}\n\n"
            for i, ch in enumerate(channels, 1):
                t += f"{i}. {ch['channel_name']}\n"
                if ch['channel_username']:
                    t += f"   @{ch['channel_username']}\n"
                t += "\n"
        btns = [
            [InlineKeyboardButton("Add Channel", callback_data="admin_add_ch", style="success"),
             InlineKeyboardButton("Channel List", callback_data="admin_list_ch", style="primary")],
            [InlineKeyboardButton("Back to Admin", callback_data="menu_admin", style="primary")]
        ]
        await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN); return

    if d == "admin_add_ch":
        db.set_user_state(uid, "wait_channel_input")
        await q.edit_message_text(
            "**Add Channel**\n\nForward a message from the channel,\nor send the channel username/link.\n\nExample: `@mychannel` or `https://t.me/mychannel`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_btn("Cancel", "admin_channels")
        ); return

    if d == "admin_list_ch":
        channels = db.get_all_channels()
        if not channels:
            t = "**Channel List**\n\nNo channels added."
        else:
            t = "**Channel List**\n\n"
            btns = []
            for i, ch in enumerate(channels, 1):
                name = ch['channel_name']
                username = ch['channel_username'] or 'N/A'
                t += f"{i}. {name} (@{username})\n"
                btns.append([InlineKeyboardButton(f"{i}. {name}", callback_data=f"admin_delch_{ch['channel_id']}", style="danger")])
            btns.append([InlineKeyboardButton("Back to Manage Channels", callback_data="admin_channels", style="primary")])
            await q.edit_message_text(t, reply_markup=InlineKeyboardMarkup(btns), parse_mode=ParseMode.MARKDOWN); return

    if d.startswith("admin_delch_"):
        ch_id = d.replace("admin_delch_", "")
        channels = db.get_all_channels()
        ch = next((c for c in channels if str(c['channel_id']) == ch_id), None)
        if not ch:
            await q.edit_message_text("Channel not found!", reply_markup=back_btn("Back", "admin_channels")); return
        await q.edit_message_text(
            f"Remove **{ch['channel_name']}**?\n\nThis will remove force-join for this channel.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Yes, Remove", callback_data=f"admin_delchok_{ch_id}", style="danger"),
                 InlineKeyboardButton("Cancel", callback_data="admin_channels", style="primary")]
            ])
        ); return

    if d.startswith("admin_delchok_"):
        ch_id = d.replace("admin_delchok_", "")
        db.remove_channel(ch_id)
        await q.edit_message_text("Channel removed!", reply_markup=back_btn("Back to Channels", "admin_channels")); return

    if d == "menu_admin":
        await admin_panel(update, context); return


# ==================== ADMIN INPUT ====================

async def handle_admin_input(update, context):
    uid = update.effective_user.id
    if uid not in ADMIN_IDS: return False
    state = db.get_user_state(uid)
    if not state: return False
    s = state['state']
    t = update.message.text.strip()

    if s == "admin_broadcast":
        # Capture the message (text/photo/video/voice/document) and show a
        # preview with Approve/Cancel buttons instead of sending instantly.
        await broadcast_capture(update, context)
        return True

    if s == "admin_ban":
        db.clear_user_state(uid)
        try: db.ban_user(int(t)); await update.message.reply_text(f"Banned {t}!", reply_markup=get_menu(uid))
        except: await update.message.reply_text("Invalid ID!", reply_markup=get_menu(uid))
        return True

    if s == "admin_unban":
        db.clear_user_state(uid)
        try: db.unban_user(int(t)); await update.message.reply_text(f"Unbanned {t}!", reply_markup=get_menu(uid))
        except: await update.message.reply_text("Invalid ID!", reply_markup=get_menu(uid))
        return True

    if s == "admin_daily":
        db.clear_user_state(uid)
        try: db.set_setting('daily_limit', t); await update.message.reply_text(f"Daily limit: {t}", reply_markup=get_menu(uid))
        except: await update.message.reply_text("Invalid!", reply_markup=get_menu(uid))
        return True

    if s == "admin_maxsessions":
        db.clear_user_state(uid)
        try: db.set_setting('max_sessions', t); await update.message.reply_text(f"Max sessions: {t}", reply_markup=get_menu(uid))
        except: await update.message.reply_text("Invalid!", reply_markup=get_menu(uid))
        return True

    if s == "admin_refbonus":
        db.clear_user_state(uid)
        try:
            amt = int(t.strip())
            if amt < 0:
                raise ValueError
            db.set_setting('referral_bonus', amt)
            await update.message.reply_text(f"Referral bonus set to **{amt} credits** per referral!", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(uid))
        except:
            await update.message.reply_text("Invalid amount! Send a number.", reply_markup=get_menu(uid))
        return True

    if s == "wait_channel_input":
        db.clear_user_state(uid)
        # Check if forwarded message from channel
        if update.message.forward_origin:
            origin = update.message.forward_origin
            if hasattr(origin, 'chat'):
                chat = origin.chat
                ch_id = chat.id
                ch_name = chat.title or chat.username or str(ch_id)
                ch_username = chat.username or ''
                ok = db.add_channel(ch_id, ch_name, ch_username, uid)
                if ok:
                    await update.message.reply_text(f"Channel added!\n\n**{ch_name}**\nID: `{ch_id}`\nUsername: @{ch_username or 'N/A'}", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(uid))
                else:
                    await update.message.reply_text("Channel already exists!", reply_markup=get_menu(uid))
                return True
        # Check if username or link
        ch_match = re.match(r'(?:https?://t\.me/|@)(\w+)', t.strip())
        if ch_match:
            username = ch_match.group(1)
            try:
                chat = await context.bot.get_chat(f"@{username}")
                ch_id = chat.id
                ch_name = chat.title or username
                ok = db.add_channel(ch_id, ch_name, username, uid)
                if ok:
                    await update.message.reply_text(f"Channel added!\n\n**{ch_name}**\nID: `{ch_id}`\nUsername: @{username}", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(uid))
                else:
                    await update.message.reply_text("Channel already exists!", reply_markup=get_menu(uid))
            except Exception as e:
                await update.message.reply_text(f"Could not find channel: {e}\n\nMake sure the bot is an admin in the channel.", reply_markup=get_menu(uid))
            return True
        await update.message.reply_text("Could not detect a channel. Please forward a message from the channel or send @username/link.", reply_markup=back_btn("Cancel", "admin_channels"))
        return True

    return False


# ==================== ADVANCED BROADCAST ====================

def _bc_buttons():
    """Approve (green) + Cancel (red) buttons for the broadcast preview."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve & Send", callback_data="bc_approve", style="success"),
         InlineKeyboardButton("❌ Cancel", callback_data="bc_cancel", style="danger")]
    ])


async def broadcast_capture(update, context):
    """Capture any content the admin sends while in 'admin_broadcast' state,
    show it back as a PREVIEW with Approve/Cancel buttons (no instant send)."""
    uid = update.effective_user.id
    msg = update.message
    if not msg:
        return

    if msg.photo:
        kind, file_id = "photo", msg.photo[-1].file_id
        text = msg.caption or ""
        ents = msg.caption_entities
    elif msg.video:
        kind, file_id = "video", msg.video.file_id
        text = msg.caption or ""
        ents = msg.caption_entities
    elif msg.voice:
        kind, file_id = "voice", msg.voice.file_id
        text = msg.caption or ""
        ents = msg.caption_entities
    elif msg.audio:
        kind, file_id = "audio", msg.audio.file_id
        text = msg.caption or ""
        ents = msg.caption_entities
    elif msg.document:
        kind, file_id = "document", msg.document.file_id
        text = msg.caption or ""
        ents = msg.caption_entities
    elif msg.text:
        kind, file_id = "text", None
        text = msg.text
        ents = msg.entities
    else:
        await msg.reply_text(
            "Unsupported content. Send text, photo, video, voice or document to broadcast.",
            reply_markup=back_btn("Cancel", "menu_admin"))
        return

    payload = json.dumps({
        "kind": kind,
        "file_id": file_id,
        "text": text,
        "entities": _entities_to_list(ents),
    })
    db.set_user_state(uid, "bc_preview", data=payload)

    mk = _bc_buttons()
    # Re-send the same content as a preview, with Approve/Cancel buttons.
    # Preserve the admin's NATIVE formatting (bold/italic/quote made via the
    # Telegram UI) by passing `entities`. Fall back to Markdown for typed
    # *bold* / > quote syntax (those have no entities but literal chars).
    if kind == "text":
        if ents:
            await msg.reply_text(text, entities=ents, reply_markup=mk)
        else:
            await msg.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=mk)
    elif kind == "photo":
        if ents:
            await msg.reply_photo(file_id, caption=text, caption_entities=ents, reply_markup=mk)
        else:
            await msg.reply_photo(file_id, caption=text, parse_mode=ParseMode.MARKDOWN, reply_markup=mk)
    elif kind == "video":
        if ents:
            await msg.reply_video(file_id, caption=text, caption_entities=ents, reply_markup=mk)
        else:
            await msg.reply_video(file_id, caption=text, parse_mode=ParseMode.MARKDOWN, reply_markup=mk)
    elif kind == "voice":
        if ents:
            await msg.reply_voice(file_id, caption=text, caption_entities=ents, reply_markup=mk)
        else:
            await msg.reply_voice(file_id, caption=text, parse_mode=ParseMode.MARKDOWN, reply_markup=mk)
    elif kind == "audio":
        if ents:
            await msg.reply_audio(file_id, caption=text, caption_entities=ents, reply_markup=mk)
        else:
            await msg.reply_audio(file_id, caption=text, parse_mode=ParseMode.MARKDOWN, reply_markup=mk)
    elif kind == "document":
        if ents:
            await msg.reply_document(file_id, caption=text, caption_entities=ents, reply_markup=mk)
        else:
            await msg.reply_document(file_id, caption=text, parse_mode=ParseMode.MARKDOWN, reply_markup=mk)


async def broadcast_approve(update, context):
    """Admin tapped Approve -> send the captured content to ALL users."""
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    st = db.get_user_state(uid)
    if not st or st['state'] != 'bc_preview':
        try: await q.edit_message_text("Nothing to broadcast.")
        except: pass
        return
    payload = json.loads(st['data'])
    db.clear_user_state(uid)

    kind, file_id, text = payload['kind'], payload['file_id'], payload['text']
    ents = _list_to_entities(payload.get('entities'))

    # Immediate feedback: edit the preview to "starting..." (buttons removed).
    # Works for both text previews and media previews (edits the caption).
    try:
        await q.edit_message_text(
            "🚀 **Broadcast started...**\n\nSending to all users, please wait ⏳",
            parse_mode=ParseMode.MARKDOWN, reply_markup=None)
    except Exception:
        pass

    users = db.get_all_users()
    ok = fail = 0
    for u in users:
        try:
            if kind == "text":
                if ents:
                    await context.bot.send_message(u['user_id'], text, entities=ents)
                else:
                    await context.bot.send_message(u['user_id'], text, parse_mode=ParseMode.MARKDOWN)
            elif kind == "photo":
                if ents:
                    await context.bot.send_photo(u['user_id'], file_id, caption=text, caption_entities=ents)
                else:
                    await context.bot.send_photo(u['user_id'], file_id, caption=text, parse_mode=ParseMode.MARKDOWN)
            elif kind == "video":
                if ents:
                    await context.bot.send_video(u['user_id'], file_id, caption=text, caption_entities=ents)
                else:
                    await context.bot.send_video(u['user_id'], file_id, caption=text, parse_mode=ParseMode.MARKDOWN)
            elif kind == "voice":
                if ents:
                    await context.bot.send_voice(u['user_id'], file_id, caption=text, caption_entities=ents)
                else:
                    await context.bot.send_voice(u['user_id'], file_id, caption=text, parse_mode=ParseMode.MARKDOWN)
            elif kind == "audio":
                if ents:
                    await context.bot.send_audio(u['user_id'], file_id, caption=text, caption_entities=ents)
                else:
                    await context.bot.send_audio(u['user_id'], file_id, caption=text, parse_mode=ParseMode.MARKDOWN)
            elif kind == "document":
                if ents:
                    await context.bot.send_document(u['user_id'], file_id, caption=text, caption_entities=ents)
                else:
                    await context.bot.send_document(u['user_id'], file_id, caption=text, parse_mode=ParseMode.MARKDOWN)
            ok += 1
        except Exception:
            fail += 1
    db.log_broadcast(text or kind, uid, len(users), ok)
    # Final edit: show the result on the (previously "starting...") preview.
    try:
        await q.edit_message_text(
            f"✅ **Broadcast sent!**\n\nSuccess: **{ok}**\nFailed: **{fail}**",
            parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(uid))
    except Exception:
        await context.bot.send_message(uid, f"✅ Broadcast sent! {ok} ok, {fail} failed", reply_markup=get_menu(uid))


async def broadcast_cancel(update, context):
    """Admin tapped Cancel -> discard the captured broadcast."""
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    db.clear_user_state(uid)
    try:
        await q.edit_message_text("❌ **Broadcast cancelled.**", parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(uid))
    except Exception:
        await context.bot.send_message(uid, "❌ Broadcast cancelled.", reply_markup=get_menu(uid))


async def handle_broadcast_media(update, context):
    """Media handler: only acts when admin is in 'admin_broadcast' state."""
    uid = update.effective_user.id
    if uid not in ADMIN_IDS:
        return
    st = db.get_user_state(uid)
    if not st or st['state'] != 'admin_broadcast':
        return
    await broadcast_capture(update, context)


# ==================== MESSAGE ROUTER ====================

async def handle_text(update, context):
    uid = update.effective_user.id

    # Admin input handling
    if uid in ADMIN_IDS:
        if await handle_admin_input(update, context): return True

    state = db.get_user_state(uid)
    if state:
        s = state['state']
        if s == 'wait_session_name':
            return await handle_session_name_input(update, context)
        if s == 'create_session_requirements':
            return await handle_session_requirements(update, context)
        if s == 'plan_more':
            return await handle_plan_more(update, context)
        if s == 'session_chat':
            return await handle_session_chat(update, context)
        if s == 'explain_code':
            db.clear_user_state(uid)
            await _explain_code(update, context, update.message.text.strip())
            return True
        if s == 'fix_code':
            db.clear_user_state(uid)
            await _fix_code(update, context, update.message.text.strip())
            return True
        if s == 'ui_gen':
            db.clear_user_state(uid)
            await _gen_ui(update, context, update.message.text.strip())
            return True

    # No active session / state -> the bot does NOT answer freely.
    # AI replies only happen inside a session (session_chat) or via the
    # /explain /fix /ui /background /search tool commands. Point the user there.
    await update.message.reply_text(
        "**Start a coding session to chat with the AI.**\n\n"
        "Use **Create Code** to open a session, or try a tool command:\n"
        "> /explain - explain code\n"
        "> /fix - debug code\n"
        "> /ui - generate UI\n"
        "> /search - web search\n"
        "> /background <q> - quick question",
        parse_mode=ParseMode.MARKDOWN, reply_markup=get_menu(uid)
    )
    return True


# ---------------------------------------------------------------------------
# Smart intent gate — stop the agent from "building" on gibberish.
# A real task = has a build noun/verb (EN or Hinglish) OR is descriptive enough.
# Single-word junk like "B", "test", "hi", "xyz" must NOT trigger a plan.
# ---------------------------------------------------------------------------
_BUILD_NOUNS = re.compile(
    r"\b(website|web|app|bot|telegram|discord|calculator|game|script|api|cli|tool|"
    r"dashboard|portfolio|landing|ecommerce|blog|chatbot|scraper|automation|extension|"
    r"plugin|library|package|crm|todo|note|editor|player|generator|analyzer|server|"
    r"frontend|backend|ui|gui|component|class|function|code|program|software|saas|"
    r"calculator|kaalcultor|bot|coding|project|application)\b", re.I)
_BUILD_VERBS = re.compile(
    r"\b(make|build|create|write|code|develop|generate|design|implement|automate|"
    r"scrape|fix|debug|add|update|modify|refactor|bana|banana|banao|bnao|bna|kr|kar|"
    r"karo|chaiye|banwana|develop|setup|set up|launch)\b", re.I)


def _looks_like_real_task(text: str) -> bool:
    """Return True only if `text` reads like an actual build/code request."""
    t = (text or "").strip()
    if len(t) < 6:
        return False  # "B", "hi", "test", "xyz" -> too short to be a task
    if _BUILD_NOUNS.search(t) or _BUILD_VERBS.search(t):
        return True
    # Long, descriptive free-text (>=4 words) counts as a real description.
    if len(t.split()) >= 4:
        return True
    return False


async def handle_session_requirements(update, context):
    uid = update.effective_user.id
    state = db.get_user_state(uid)
    if not state or state['state'] != 'create_session_requirements': return False
    reqs = update.message.text.strip()
    if not reqs:
        await update.message.reply_text("Cannot be empty!"); return True

    # SMART GATE: if the text isn't a real build task (junk like "B", "test",
    # "hi"), DON'T generate a fake plan. Ask a clarifying question and stay in
    # the same state so the next message is re-evaluated. The agent only acts
    # on genuine tasks.
    if not _looks_like_real_task(reqs):
        await update.message.reply_text(
            "That's not clear enough to build yet 😅\n\n"
            "Describe what you want in one or two lines. Examples:\n"
            "• Build a calculator\n"
            "• Dark-theme portfolio website\n"
            "• A Telegram bot that replies hello\n\n"
            "Tell me and I'll make a proper plan! 👇",
            reply_markup=back_btn("Cancel", "menu_create"))
        return True

    sid = int(state['data'])
    db.update_session_context(sid, {"requirements": reqs, "step": "generate"})

    session = db.get_session_by_id(sid)
    plan_prompt = (
        f"You are OXYGENT, an autonomous AI coding AGENT. A user wants to build something.\n"
        f"Project type: {session.get('project_type', 'General')}\n"
        f"Request: {reqs}\n\n"
        "Produce a concise IMPLEMENTATION PLAN (plain text, no code). Cover:\n"
        "1. Recommended language/stack\n"
        "2. Files to create (list with one-line purpose each)\n"
        "3. Key features / steps\n"
        "4. How to run it\n"
        "Keep it tight and scannable."
    )
    await update.message.reply_text("Generating plan...")
    plan = await _typing_while(update, context, _zen_chat(plan_prompt))
    if plan is None:
        plan = "Couldn't generate a plan right now. Tap Approve to start building anyway, or Plan More to add details."
    db.update_session_context(sid, {"requirements": reqs, "plan": plan, "step": "approval"})

    # Plan shown inside a quote block (>) as the user requested
    plan_text = _plan_md(f"**Plan for {session['session_name']}**", plan)
    await _safe_markdown(update.message, plan_text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve & Build", callback_data=f"plan_approve_{sid}", style="success"),
         InlineKeyboardButton("✏️ Plan More", callback_data=f"plan_more_{sid}", style="primary")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back", style="primary")]
    ]))
    return True


async def handle_plan_more(update, context):
    uid = update.effective_user.id
    state = db.get_user_state(uid)
    if not state or state['state'] != 'plan_more': return False
    sid = int(state['data'])
    add = update.message.text.strip()
    session = db.get_session_by_id(sid)
    ctx = session.get('context_data', {}) or {}

    # If the user just says "nothing"/"ok"/"looks good", there's nothing to
    # change — re-show the existing plan immediately (no pointless regeneration).
    if re.search(r'^(nothing|none|ok|okay|k|no change|no|looks good|lgtm|same|nop|nah)\b', add, re.IGNORECASE):
        plan = ctx.get('plan', '')
        plan_text = _plan_md(f"**Plan for {session['session_name']}**", plan)
        await _safe_markdown(update.message, plan_text, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Approve & Build", callback_data=f"plan_approve_{sid}", style="success"),
             InlineKeyboardButton("✏️ Plan More", callback_data=f"plan_more_{sid}", style="primary")],
            [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back", style="primary")]
        ]))
        return True

    new_reqs = ctx.get('requirements', '') + "\n\n" + add
    db.update_session_context(sid, {"requirements": new_reqs, "step": "generate"})
    # regenerate plan with the extra details
    plan_prompt = (
        f"You are OXYGENT, an autonomous AI coding AGENT. Refined request:\n{new_reqs}\n\n"
        "Produce a concise IMPLEMENTATION PLAN (plain text, no code): language/stack, "
        "files to create, key features, how to run. Tight and scannable."
    )
    await update.message.reply_text("Updating plan...")
    plan = await _typing_while(update, context, _zen_chat(plan_prompt))
    if plan is None:
        plan = "Couldn't regenerate the plan. Tap Approve to build, or add more details."
    db.update_session_context(sid, {"plan": plan, "step": "approval"})
    plan_text = _plan_md(f"**Updated Plan for {session['session_name']}**", plan)
    await _safe_markdown(update.message, plan_text, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve & Build", callback_data=f"plan_approve_{sid}", style="success"),
         InlineKeyboardButton("✏️ Plan More", callback_data=f"plan_more_{sid}", style="primary")],
        [InlineKeyboardButton("⬅️ Back to Menu", callback_data="menu_back", style="primary")]
    ]))
    return True


# ==================== HANDLERS ====================

def setup_handlers(app):
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("menu", menu_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel_command))
    app.add_handler(CommandHandler("create", create_command))
    app.add_handler(CommandHandler("admin", admin_panel))
    # Previously-listed-but-broken commands, now fully working:
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("voice", voice_command))
    app.add_handler(CommandHandler("voicegender", voicegender_command))
    app.add_handler(CommandHandler("background", background_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("forget", forget_command))
    app.add_handler(CommandHandler("explain", explain_command))
    app.add_handler(CommandHandler("fix", fix_command))
    app.add_handler(CommandHandler("ui", ui_command))
    app.add_handler(CommandHandler("selftest", selftest_command))
    app.add_handler(PreCheckoutQueryHandler(handle_pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_successful_payment))
    app.add_handler(CallbackQueryHandler(main_callback_handler))
    # Advanced broadcast: capture media (photo/video/voice/audio/document)
    # when the admin is in 'admin_broadcast' state. Registered before the
    # generic text handler so media isn't dropped.
    app.add_handler(MessageHandler(
        filters.PHOTO | filters.VIDEO | filters.VOICE | filters.AUDIO | filters.Document.ALL,
        handle_broadcast_media))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app


BOT_COMMANDS = [
    ("start", "Start & join check"),
    ("menu", "Open main menu"),
    ("create", "Create / manage code sessions"),
    ("status", "Your info, limits & credits"),
    ("voice", "Toggle voice-note replies"),
    ("voicegender", "Set voice male/female"),
    ("background", "Ask a quick question"),
    ("search", "Web search"),
    ("explain", "Explain pasted code"),
    ("fix", "Debug broken code"),
    ("ui", "Generate UI from text"),
    ("memory", "View stored memory"),
    ("forget", "Clear your memory"),
    ("help", "Show help"),
    ("cancel", "Cancel current operation"),
    ("admin", "Admin panel"),
    ("selftest", "Run health self-test"),
]


async def set_my_commands(app):
    """Publish the command list so Telegram shows it in the '/' menu."""
    try:
        from telegram import BotCommand
        await app.bot.set_my_commands([BotCommand(c, d) for c, d in BOT_COMMANDS])
    except Exception as e:
        logger.warning(f"set_my_commands failed: {e}")


async def main():
    try: db.init_db(); print("[DB] OK!")
    except Exception as e: print(f"[DB] Error: {e}")

    app = Application.builder().token(BOT_TOKEN).build()
    setup_handlers(app)
    await set_my_commands(app)
    print("OXYGENT Bot starting...")
    await app.initialize()
    await app.start()
    # Drop pending updates to avoid Conflict on restart
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    try:
        while True: await asyncio.sleep(3600)
    except asyncio.CancelledError: pass
    finally:
        await app.updater.stop(); await app.stop(); await app.shutdown()


# ==================== SELFTEST (admin) ====================

async def selftest_command(update, context, edit_mode=False):
    """/selftest - run an automated health check of core subsystems.

    `edit_mode=True` is used when launched from the admin-panel button (callback
    query): it edits the button message in place instead of using
    `update.message` (which is None for callback queries and previously made
    the button appear to do nothing).
    """
    uid = update.effective_user.id
    # Acknowledge the callback query immediately so Telegram shows the tap as
    # handled (no sticky "loading..." / delayed UI). Required for the admin-panel
    # button; harmless for the /selftest command.
    q = getattr(update, "callback_query", None)
    if q is not None:
        try:
            await q.answer()
        except Exception:
            pass
    # Resolve the message target: a callback message to edit, or a fresh reply.
    if edit_mode and update.callback_query:
        target = update.callback_query.message
    else:
        target = update.message
    if uid not in ADMIN_IDS:
        await _safe_markdown(target, "Admin only!", reply_markup=back_btn(), edit=edit_mode)
        return

    await _safe_markdown(target, "🩺 Running self-test...", edit=edit_mode)
    results = []

    def add(name, ok, detail=""):
        results.append((name, ok, detail))

    # 1) DB connectivity
    try:
        db.get_user_count()
        add("DB connect", True)
    except Exception as e:
        add("DB connect", False, str(e)[:80])

    # 2) create_session returns a real int id (RETURNING id fix)
    try:
        sid = db.create_session(uid, f"SELFTEST_{datetime.datetime.now().timestamp()}")
        ok = isinstance(sid, int) and sid > 0
        add("create_session id", ok, f"id={sid}" if ok else f"got {sid!r}")
        if ok:
            db.delete_session_by_id(uid, sid)
    except Exception as e:
        add("create_session id", False, str(e)[:80])

    # 3) daily counter increments
    try:
        before = db.get_msg_count(uid, datetime.date.today().isoformat())[0]
        db.increment_msg_count(uid, datetime.date.today().isoformat())
        after = db.get_msg_count(uid, datetime.date.today().isoformat())[0]
        add("daily counter", after == before + 1, f"{before} -> {after}")
    except Exception as e:
        add("daily counter", False, str(e)[:80])

    # 4) limit enforcement logic (free -> paid -> block) simulated
    try:
        t = uid + 7_000_000
        db.add_user(t)
        conn = db.get_db(); c = conn.cursor()
        c.execute('UPDATE users SET msg_count=0, msg_date=%s, bonus_messages=1 WHERE user_id=%s',
                  (datetime.date.today().isoformat(), t)); conn.commit(); conn.close()
        # exhaust free
        count, _ = db.get_msg_count(t, datetime.date.today().isoformat())
        daily = db.get_daily_limit()
        if daily - count > 0:
            db.increment_msg_count(t, datetime.date.today().isoformat())
            decision = "free"
        elif db.get_user(t).get('bonus_messages', 0) > 0:
            db.consume_bonus_message(t, 1); decision = "paid"
        else:
            decision = "block"
        conn = db.get_db(); c = conn.cursor()
        c.execute('DELETE FROM users WHERE user_id=%s', (t,)); conn.commit(); conn.close()
        add("limit logic", decision in ("free", "paid", "block"), f"decision={decision}")
    except Exception as e:
        add("limit logic", False, str(e)[:80])

    # 5) voice prefs persist
    try:
        db.update_voice_pref(uid, enabled=True, gender="male")
        enabled, gender = db.get_voice_pref(uid)
        add("voice prefs", enabled is True and gender == "male", f"{enabled}/{gender}")
        db.update_voice_pref(uid, enabled=False)
    except Exception as e:
        add("voice prefs", False, str(e)[:80])

    # 6) web search returns results
    try:
        from coding_tools import web_search
        r = await web_search("python", 3)
        add("web search", bool(r.get("success") and r.get("results")),
            f"{r.get('total', 0)} results")
    except Exception as e:
        add("web search", False, str(e)[:80])

    # 7) all menu commands have handlers registered
    try:
        regs = set()
        app = getattr(context, "application", None)
        if app is not None:
            for grp in app.handlers.values():
                for h in grp:
                    if isinstance(h, CommandHandler):
                        regs.update(h.commands)
        missing = [c for c, _ in BOT_COMMANDS if c not in regs]
        add("command handlers", not missing,
            f"{len(regs)} handlers, missing={missing or 'none'}")
    except Exception as e:
        add("command handlers", False, str(e)[:80])

    # Build report
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    lines = [f"🩺 **Self-Test: {passed}/{total} passed**\n"]
    for name, ok, detail in results:
        lines.append(f"{'✅' if ok else '❌'} {name}" + (f" — {detail}" if detail else ""))
    await _safe_markdown(target, "\n".join(lines), reply_markup=back_btn(), edit=edit_mode)


if __name__ == "__main__":
    try: asyncio.run(main())
    except RuntimeError as e:
        if "already running" in str(e): asyncio.get_event_loop().run_until_complete(main())
        else: raise
