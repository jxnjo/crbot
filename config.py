"""
Zentrale Konfiguration für den CRBot.
Alle Constants, Defaults und Environment-Variable werden hier verwaltet.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Environment laden
load_dotenv()

class BotConfig:
    """Zentrale Konfigurationsklasse für den Bot."""
    
    # Bot-Tokens und API-Keys
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    CLASH_TOKEN: str = os.getenv("CLASH_TOKEN", "")
    
    # Clan-Konfiguration
    CLAN_TAG: str = os.getenv("CLAN_TAG", "RLPR02L0")
    
    # Bot-Verhalten
    OPEN_ATTACKS_ATTEMPTS_DEFAULT: int = int(os.getenv("OPEN_ATTACKS_ATTEMPTS_DEFAULT", "2"))
    STARTUP_CHAT_ID: Optional[int] = int(os.getenv("STARTUP_CHAT_ID", "-4728976794") or "-4728976794")
    
    # API-Timeouts und Limits
    API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "15"))
    MAX_MESSAGE_LENGTH: int = 4096
    
    # Zeitzone
    BOT_TZ: str = os.getenv("BOT_TZ", "Europe/Zurich")
    
    # Clash Royale spezifische Konstanten
    MAX_DECKS_PER_DAY: int = 4
    MAX_CLAN_MEMBERS: int = 50
    
    # Formatierung und Anzeige
    DEFAULT_DONATIONS_LIMIT: int = 10
    DEFAULT_WAR_HISTORY_LIMIT: int = 50
    DEFAULT_SPY_DAYS: int = 20
    PROGRESS_BAR_WIDTH: int = 18
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Version-Info (für Docker/CI)
    VERSION_SHA: str = os.getenv("BOT_VERSION_SHA", "dev")
    VERSION_REF: str = os.getenv("BOT_VERSION_REF", "local")
    VERSION_TIME: str = os.getenv("BOT_VERSION_TIME", "unknown")
    VERSION_AUTHOR: str = os.getenv("BOT_VERSION_AUTHOR", "unknown")
    VERSION_MSG: str = (os.getenv("BOT_VERSION_MSG", "") or "").strip()
    
    @classmethod
    def validate_required_config(cls) -> None:
        """Validiert, dass alle erforderlichen Konfigurationswerte gesetzt sind."""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN ist erforderlich! Bitte in .env setzen.")
        if not cls.CLASH_TOKEN:
            raise ValueError("CLASH_TOKEN ist erforderlich! Bitte in .env setzen.")
        if not cls.CLAN_TAG:
            raise ValueError("CLAN_TAG ist erforderlich! Bitte in .env setzen.")
    
    @classmethod
    def get_version_dict(cls) -> dict:
        """Gibt Version-Informationen als Dictionary zurück."""
        return {
            "sha": cls.VERSION_SHA,
            "ref": cls.VERSION_REF,
            "time": cls.VERSION_TIME,
            "author": cls.VERSION_AUTHOR,
            "msg": cls.VERSION_MSG,
        }

# Singleton-Instanz für einfachen Import
config = BotConfig()

# Command-Definitionen für Telegram Bot
from telegram import BotCommand

COMMANDS_GROUP = [
    BotCommand("status", "🟢 Zeigt den Bot-Status an"),
    BotCommand("start", "🚀 Startet den Bot"),
    BotCommand("hilfe", "❓ Zeigt diese Hilfe an"),
    BotCommand("help", "❓ Shows this help"),
    BotCommand("commands", "📋 Liste aller verfügbaren Befehle"),
    BotCommand("version", "📋 Bot-Version und Informationen"),
    BotCommand("claninfo", "🏛️ Zeigt Clan-Informationen an"),
    BotCommand("aktivitaet", "⚡ Zeigt Aktivität der Clan-Mitglieder"),
    BotCommand("online", "🟢 Zeigt aktuell online Mitglieder"),
    BotCommand("inaktiv", "🔻 Zeigt inaktivste Spieler (optional: spenden|kriegsangriffe|kriegspunkte|trophäenpfad)"),
    BotCommand("offeneangriffe", "⚔️ Zeigt offene Deck-Angriffe im River Race"),
    BotCommand("krieginfo", "🏰 Krieg-Informationen (optional: Anzahl Tage)"),
    BotCommand("krieginfoheute", "📅 Heutige Krieg-Informationen"),
    BotCommand("krieginfogesamt", "📊 Gesamt Krieg-Informationen"),
    BotCommand("spenden", "💰 Spenden-Rangliste (optional: Anzahl Tage)"),
    BotCommand("krieghistorie", "📜 Krieg-Historie (optional: Anzahl Tage)"),
    BotCommand("spion", "🕵️ Spionage des aktivsten Gegnerclans mit Historie"),
]

COMMANDS_PRIVATE = [
    BotCommand("start", "🚀 Startet den Bot"),
    BotCommand("hilfe", "❓ Zeigt diese Hilfe an"),
    BotCommand("help", "❓ Shows this help"),
    BotCommand("version", "📋 Bot-Version und Informationen"),
]

def get_help_text() -> str:
    """Erstellt den Hilfetext für alle verfügbaren Commands."""
    lines = ["<b>📋 Verfügbare Befehle:</b>\n"]
    
    for cmd in COMMANDS_GROUP:
        lines.append(f"/{cmd.command} - {cmd.description}")
    
    lines.extend([
        "",
        "<b>💡 Tipps:</b>",
        "• Befehle mit Parametern: <code>/befehl [parameter]</code>",
        "• Parameter sind optional, wenn nicht anders angegeben",
        "• Für detaillierte Hilfe: <code>/help</code>",
    ])
    
    return "\n".join(lines)