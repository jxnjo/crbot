import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram import (
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
)

# Eigene Module
from clash import (
    ClashClient,
    fmt_clan,
    fmt_activity_list,
    fmt_river_scoreboard,
    fmt_donations_leaderboard,
    fmt_open_decks_overview,
    fmt_war_history_summary,      # NEU
    fmt_war_history_player,       # NEU
)

# Optional: zentrale Command-Liste/Hilfe aus commands.py
from commands import COMMANDS_GROUP, COMMANDS_PRIVATE, get_help_text

# ----------------- Setup & Globals -----------------
load_dotenv()
BOT_TOKEN   = os.getenv("BOT_TOKEN")
CLASH_TOKEN = os.getenv("CLASH_TOKEN")
CLAN_TAG    = os.getenv("CLAN_TAG", "RLPR02L0")

# Wie viele Versuche beim Fresh-Fetch von /currentriverrace
OPEN_ATTACKS_ATTEMPTS_DEFAULT = int(os.getenv("OPEN_ATTACKS_ATTEMPTS_DEFAULT", "2"))

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("clanbot")

# --- Version aus Docker-ENV lesen ---
STARTUP_CHAT_ID = int(os.getenv("STARTUP_CHAT_ID", "0") or 0)

def _read_version() -> dict:
    return {
        "sha": os.getenv("BOT_VERSION_SHA", "dev"),
        "ref": os.getenv("BOT_VERSION_REF", "local"),
        "time": os.getenv("BOT_VERSION_TIME", "unknown"),
        "author": os.getenv("BOT_VERSION_AUTHOR", "unknown"),
        "msg": (os.getenv("BOT_VERSION_MSG", "") or "").strip(),
    }

def _format_version(v: dict) -> str:
    short = v["sha"][:7]
    note = f"\n📝 {v['msg']}" if v["msg"] else ""
    return (
        f"🔧 <b>Bot-Version</b>\n"
        f"• Commit: <code>{short}</code> ({v['ref']})\n"
        f"• Autor: {v['author']}\n"
        f"• Build: {v['time']}{note}"
    )

# Einmaligen Clash-Client erstellen
clash = ClashClient(CLASH_TOKEN, CLAN_TAG)

# ----------------- Command-Setup per API -----------------
async def setup_commands(app: Application) -> None:
    """Setzt die sichtbaren Slash-Commands in Telegram (Gruppen & Privat)."""
    await app.bot.set_my_commands(COMMANDS_GROUP, scope=BotCommandScopeAllGroupChats())
    await app.bot.set_my_commands(COMMANDS_PRIVATE, scope=BotCommandScopeAllPrivateChats())
    log.info("Commands via Bot-API registriert (Scopes: Group, Private).")

# ----------------- Command-Handler -----------------
async def version_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(
        _format_version(_read_version()), parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )

async def on_startup(app: Application):
    # Commands zuerst registrieren
    await setup_commands(app)

    # Startmeldung in definierte Chat-ID schicken (Gruppe/DM), wenn gesetzt
    if STARTUP_CHAT_ID:
        v = _read_version()
        short = v["sha"][:7]
        text = (
            f"🚀 <b>Drablibe-Bot wurde gestartet und/oder geupdatet!</b>\n"
            f"• Commit: <code>{short}</code> ({v['ref']})\n"
            f"• Autor: {v['author']}\n"
            f"• Build: {v['time']}\n"
            f"{'📝 ' + v['msg'] if v['msg'] else ''}"
        )
        try:
            await app.bot.send_message(STARTUP_CHAT_ID, text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
        except Exception as e:
            log.warning("Konnte Startmeldung nicht senden: %s", e)

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot läuft und hört zu!")

async def hilfe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_chat.send_message(
        get_help_text(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def claninfo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = await clash.get_clan()
    await update.effective_chat.send_message(
        fmt_clan(data, CLAN_TAG),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

async def offeneangriffe_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # benutze den ENV-Default
    attempts = OPEN_ATTACKS_ATTEMPTS_DEFAULT
    if context.args and context.args[0].lower() in {"force", "refresh", "neu"}:
        attempts = max(attempts, 3)

    rr = await clash.get_current_river_fresh(attempts=attempts)
    msg = fmt_open_decks_overview(rr, CLAN_TAG, max_decks=4)
    await update.effective_chat.send_message(
        msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )

async def aktivitaet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    members = await clash.get_members()
    await update.effective_chat.send_message(
        fmt_activity_list(members),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )

# /krieginfo [heute|gesamt]  (Default: auto)
async def krieginfo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rr = await clash.get_current_river_fresh(attempts=2)
    arg = (context.args[0].lower() if context.args else "auto")
    if arg not in {"auto", "heute", "gesamt"}:
        arg = "auto"
    msg = fmt_river_scoreboard(rr, CLAN_TAG, mode=arg)
    await update.effective_chat.send_message(
        msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )

# Explizite Varianten
async def krieginfo_heute_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rr = await clash.get_current_river_fresh(attempts=2)
    msg = fmt_river_scoreboard(rr, CLAN_TAG, mode="heute")
    await update.effective_chat.send_message(
        msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )

async def krieginfo_gesamt_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rr = await clash.get_current_river_fresh(attempts=2)
    msg = fmt_river_scoreboard(rr, CLAN_TAG, mode="gesamt")
    await update.effective_chat.send_message(
        msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )

async def spenden_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /spenden [anzahl]  -> default 10, 'all' zeigt alle
    limit = 10
    if context.args:
        arg = context.args[0].strip().lower()
        if arg in {"all", "alle"}:
            limit = 0
        else:
            try:
                limit = max(1, int(arg))
            except ValueError:
                limit = 10

    members = await clash.get_members()
    msg = fmt_donations_leaderboard(
        members, limit=(0 if limit == 0 else limit), include_received=True
    )
    await update.effective_chat.send_message(
        msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )

# --- NEU: /krieghistorie [Name?] ---
async def krieghistorie_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Hole mehrere Wochen Log (z. B. 50 Einträge)
    log_data = await clash.get_river_log(limit=50)
    if context.args:
        query = " ".join(context.args).strip()
        msg = fmt_war_history_player(log_data, CLAN_TAG, query)
    else:
        msg = fmt_war_history_summary(log_data, CLAN_TAG)
    await update.effective_chat.send_message(
        msg, parse_mode=ParseMode.HTML, disable_web_page_preview=True
    )

# ----------------- Main -----------------
def main():
    if not BOT_TOKEN or not CLASH_TOKEN:
        raise SystemExit("Bitte BOT_TOKEN & CLASH_TOKEN in .env setzen.")

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands registrieren
    app.add_handler(CommandHandler("version", version_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("start", status_cmd))  # Alias
    app.add_handler(CommandHandler("hilfe", hilfe_cmd))
    app.add_handler(CommandHandler("commands", hilfe_cmd))   # Alias
    app.add_handler(CommandHandler("claninfo", claninfo_cmd))
    app.add_handler(CommandHandler("offeneangriffe", offeneangriffe_cmd))
    app.add_handler(CommandHandler("aktivitaet", aktivitaet_cmd))
    app.add_handler(CommandHandler("online", aktivitaet_cmd))  # Alias
    app.add_handler(CommandHandler("krieginfo", krieginfo_cmd))
    app.add_handler(CommandHandler("krieginfoheute", krieginfo_heute_cmd))
    app.add_handler(CommandHandler("krieginfogesamt", krieginfo_gesamt_cmd))
    app.add_handler(CommandHandler("spenden", spenden_cmd))
    app.add_handler(CommandHandler("krieghistorie", krieghistorie_cmd))  # NEU

    # Commands beim Start in Telegram setzen
    app.post_init = on_startup

    log.info("Bot startet (Polling)…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
