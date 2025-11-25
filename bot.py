"""
Refactored Clash Royale Telegram Bot.
Verwendet neue modulare Architektur mit Handler-Pattern und zentraler Konfiguration.
"""
import logging
from telegram import Update, BotCommandScopeAllGroupChats, BotCommandScopeAllPrivateChats
from telegram.ext import Application, CommandHandler, ContextTypes

# Neue Module
from config import config, COMMANDS_GROUP, COMMANDS_PRIVATE, get_help_text
from handlers import (
    BaseHandler, with_error_handling,
    create_simple_handler, create_version_handler, create_help_handler,
    ClanInfoHandler, MembersHandler, RiverRaceHandler, ParameterizedHandler, MultiMessageHandler
)
from clash import ClashClient, _aggregate_war_history, spy_make_messages
from formatters import (
    fmt_clan, fmt_activity_list, fmt_river_scoreboard, fmt_donations_leaderboard,
    fmt_open_decks_overview, fmt_war_history_summary, fmt_war_history_player_multi,
    fmt_startup_message, fmt_inactive_players
)

# Setup Logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
log = logging.getLogger("clanbot")

class CRBot:
    """Hauptklasse für den Clash Royale Bot."""
    
    def __init__(self):
        # Konfiguration validieren
        config.validate_required_config()
        
        # Clash Client initialisieren
        self.clash = ClashClient(config.CLASH_TOKEN, config.CLAN_TAG)
        
        # Bot Application erstellen
        self.app = Application.builder().token(config.BOT_TOKEN).build()
        
        # Handler registrieren
        self._register_handlers()
        
        # Post-init Hook für Commands
        self.app.post_init = self._on_startup

    def _register_handlers(self) -> None:
        """Registriert alle Command-Handler."""
        
        # Einfache Handler
        self.app.add_handler(CommandHandler("status", create_simple_handler("status", "✅ Bot läuft und hört zu!").handle))
        self.app.add_handler(CommandHandler("start", create_simple_handler("start", "✅ Bot läuft und hört zu!").handle))
        self.app.add_handler(CommandHandler("version", create_version_handler("version").handle))
        self.app.add_handler(CommandHandler("hilfe", create_help_handler("hilfe").handle))
        self.app.add_handler(CommandHandler("commands", create_help_handler("commands").handle))
        self.app.add_handler(CommandHandler("help", create_help_handler("help").handle))
        
        # Clash Royale API Handler
        self.app.add_handler(CommandHandler("claninfo", ClanInfoHandler("claninfo", self.clash, fmt_clan).handle))
        self.app.add_handler(CommandHandler("aktivitaet", MembersHandler("aktivitaet", self.clash, fmt_activity_list).handle))
        self.app.add_handler(CommandHandler("online", MembersHandler("online", self.clash, fmt_activity_list).handle))
        
        # River Race Handler
        self.app.add_handler(CommandHandler("offeneangriffe", 
            RiverRaceHandler("offeneangriffe", self.clash, fmt_open_decks_overview).handle))
        
        # Parametrisierte Handler
        self.app.add_handler(CommandHandler("krieginfo", ParameterizedHandler("krieginfo", self._krieginfo_handler).handle))
        self.app.add_handler(CommandHandler("krieginfoheute", ParameterizedHandler("krieginfoheute", self._krieginfo_heute_handler).handle))
        self.app.add_handler(CommandHandler("krieginfogesamt", ParameterizedHandler("krieginfogesamt", self._krieginfo_gesamt_handler).handle))
        self.app.add_handler(CommandHandler("spenden", ParameterizedHandler("spenden", self._spenden_handler).handle))
        self.app.add_handler(CommandHandler("krieghistorie", ParameterizedHandler("krieghistorie", self._krieghistorie_handler).handle))
        self.app.add_handler(CommandHandler("inaktiv", ParameterizedHandler("inaktiv", self._inaktiv_handler).handle))
        self.app.add_handler(CommandHandler("spion", MultiMessageHandler("spion", self._spion_handler).handle))

    async def _krieginfo_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Handler für /krieginfo mit optionalem Mode-Parameter."""
        rr = await self.clash.get_current_river_fresh(attempts=2)
        arg = (context.args[0].lower() if context.args else "auto")
        if arg not in {"auto", "heute", "gesamt"}:
            arg = "auto"
        return fmt_river_scoreboard(rr, config.CLAN_TAG, mode=arg)

    async def _krieginfo_heute_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Handler für /krieginfoheute."""
        rr = await self.clash.get_current_river_fresh(attempts=2)
        return fmt_river_scoreboard(rr, config.CLAN_TAG, mode="heute")

    async def _krieginfo_gesamt_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Handler für /krieginfogesamt."""
        rr = await self.clash.get_current_river_fresh(attempts=2)
        return fmt_river_scoreboard(rr, config.CLAN_TAG, mode="gesamt")

    async def _spenden_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Handler für /spenden mit optionalem Limit-Parameter."""
        limit = config.DEFAULT_DONATIONS_LIMIT
        if context.args:
            arg = context.args[0].strip().lower()
            if arg in {"all", "alle"}:
                limit = 0
            else:
                try:
                    limit = max(1, int(arg))
                except ValueError:
                    limit = config.DEFAULT_DONATIONS_LIMIT

        members = await self.clash.get_members()
        return fmt_donations_leaderboard(members, limit=(0 if limit == 0 else limit), include_received=True)

    async def _krieghistorie_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Handler für /krieghistorie mit optionalem Spielername."""
        log_data = await self.clash.get_river_log(limit=config.DEFAULT_WAR_HISTORY_LIMIT)
        
        if context.args:
            query = " ".join(context.args).strip()
            msgs = fmt_war_history_player_multi(log_data, config.CLAN_TAG, query, _aggregate_war_history)
            if len(msgs) > 1:
                # Mehrere Treffer - sende Warnung und dann alle Ergebnisse
                await update.effective_chat.send_message(
                    f"⚠️ Es wurden {len(msgs)} Spieler mit dem Namen '{query}' gefunden:",
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            for msg in msgs:
                await update.effective_chat.send_message(
                    msg, 
                    parse_mode="HTML", 
                    disable_web_page_preview=True
                )
            return None  # Bereits gesendet
        else:
            return fmt_war_history_summary(log_data, config.CLAN_TAG, _aggregate_war_history)

    async def _inaktiv_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        """Handler für /inaktiv mit optionalem Sortierkriterium."""
        # Hole beide Datenquellen: Mitglieder und aktuelle River Race
        members = await self.clash.get_members()
        river_race = await self.clash.get_current_river_fresh(attempts=2)
        
        # Bestimme Sortierkriterium
        sort_by = "gesamt"  # Standard
        if context.args:
            arg = context.args[0].strip().lower()
            valid_sorts = ["spenden", "kriegsangriffe", "kriegspunkte", "trophäenpfad", "gesamt"]
            if arg in valid_sorts:
                sort_by = arg
        
        return fmt_inactive_players(members, river_race, sort_by=sort_by, limit=10)

    async def _spion_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> list[str]:
        """Handler für /spion - Gegner-Spionage mit historischer Analyse."""
        messages = await spy_make_messages(self.clash, config.CLAN_TAG, days=config.DEFAULT_SPY_DAYS)
        return messages

    async def _setup_commands(self) -> None:
        """Setzt die sichtbaren Slash-Commands in Telegram."""
        await self.app.bot.set_my_commands(COMMANDS_GROUP, scope=BotCommandScopeAllGroupChats())
        await self.app.bot.set_my_commands(COMMANDS_PRIVATE, scope=BotCommandScopeAllPrivateChats())
        log.info("Commands via Bot-API registriert (Scopes: Group, Private).")

    async def _on_startup(self, app: Application) -> None:
        """Wird beim Bot-Start ausgeführt."""
        # Commands zuerst registrieren
        await self._setup_commands()

        # Startmeldung senden, wenn Chat-ID konfiguriert ist
        if config.STARTUP_CHAT_ID:
            try:
                text = fmt_startup_message(config.get_version_dict())
                await app.bot.send_message(
                    config.STARTUP_CHAT_ID, 
                    text, 
                    parse_mode="HTML", 
                    disable_web_page_preview=True
                )
                log.info(f"Startmeldung gesendet an Chat {config.STARTUP_CHAT_ID}")
            except Exception as e:
                log.warning(f"Konnte Startmeldung nicht senden: {e}")

    def run(self) -> None:
        """Startet den Bot."""
        log.info("Bot startet (Polling)…")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Haupteinstiegspunkt."""
    try:
        bot = CRBot()
        bot.run()
    except Exception as e:
        log.exception(f"Fehler beim Starten des Bots: {e}")
        raise SystemExit(f"Bot konnte nicht gestartet werden: {e}")

if __name__ == "__main__":
    main()