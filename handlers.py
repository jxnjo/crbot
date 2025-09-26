"""
Handler-Abstraktionen und Base-Klassen für Telegram Bot Commands.
Reduziert Code-Duplizierung und vereinheitlicht Error-Handling.
"""
import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable, Optional
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from config import config

log = logging.getLogger("clanbot.handlers")

class BotError(Exception):
    """Basis-Exception für Bot-spezifische Fehler."""
    def __init__(self, message: str, user_message: str = None):
        super().__init__(message)
        self.user_message = user_message or message

class APIError(BotError):
    """Fehler bei API-Aufrufen."""
    pass

class ValidationError(BotError):
    """Fehler bei der Eingabevalidierung."""
    pass

class BaseHandler(ABC):
    """Basis-Klasse für alle Bot-Handler mit einheitlichem Error-Handling."""
    
    def __init__(self, name: str):
        self.name = name
        self.log = logging.getLogger(f"clanbot.handlers.{name}")
    
    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Haupteinstiegspunkt mit Error-Handling."""
        try:
            result = await self.execute(update, context)
            if result:
                await self._send_message(update, result)
        except BotError as e:
            self.log.error(f"Bot error in {self.name}: {e}")
            await self._send_error(update, e.user_message)
        except Exception as e:
            self.log.exception(f"Unexpected error in {self.name}: {e}")
            await self._send_error(update, "Ein unerwarteter Fehler ist aufgetreten.")
    
    @abstractmethod
    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
        """Implementiert die eigentliche Command-Logik."""
        pass
    
    async def _send_message(self, update: Update, text: str) -> None:
        """Sendet eine formatierte Nachricht."""
        await update.effective_chat.send_message(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    
    async def _send_error(self, update: Update, error_message: str) -> None:
        """Sendet eine Fehlernachricht."""
        await update.effective_chat.send_message(
            f"❌ {error_message}",
            parse_mode=ParseMode.HTML
        )

class SimpleHandler(BaseHandler):
    """Handler für einfache Commands ohne Parameter."""
    
    def __init__(self, name: str, message_func: Callable[[], Awaitable[str]]):
        super().__init__(name)
        self.message_func = message_func
    
    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        return await self.message_func()

class ClashHandler(BaseHandler):
    """Handler für Clash Royale API-basierte Commands."""
    
    def __init__(self, name: str, clash_client, formatter_func: Callable):
        super().__init__(name)
        self.clash = clash_client
        self.formatter_func = formatter_func
    
    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        try:
            data = await self.get_data(context)
            return self.formatter_func(data, config.CLAN_TAG)
        except Exception as e:
            raise APIError(f"Clash Royale API Fehler: {e}", "Fehler beim Abrufen der Clash Royale Daten.")
    
    @abstractmethod
    async def get_data(self, context: ContextTypes.DEFAULT_TYPE) -> Any:
        """Holt die benötigten Daten von der Clash Royale API."""
        pass

class ClanInfoHandler(ClashHandler):
    """Handler für Clan-Informationen."""
    
    async def get_data(self, context: ContextTypes.DEFAULT_TYPE) -> Any:
        return await self.clash.get_clan()

class MembersHandler(ClashHandler):
    """Handler für Mitglieder-bezogene Commands."""
    
    async def get_data(self, context: ContextTypes.DEFAULT_TYPE) -> Any:
        return await self.clash.get_members()

class RiverRaceHandler(ClashHandler):
    """Handler für River Race-bezogene Commands."""
    
    def __init__(self, name: str, clash_client, formatter_func: Callable, attempts: int = 2):
        super().__init__(name, clash_client, formatter_func)
        self.attempts = attempts
    
    async def get_data(self, context: ContextTypes.DEFAULT_TYPE) -> Any:
        attempts = self.attempts
        if context.args and context.args[0].lower() in {"force", "refresh", "neu"}:
            attempts = max(attempts, 3)
        return await self.clash.get_current_river_fresh(attempts=attempts)

class ParameterizedHandler(BaseHandler):
    """Handler für Commands mit Parametern."""
    
    def __init__(self, name: str, handler_func: Callable):
        super().__init__(name)
        self.handler_func = handler_func
    
    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
        return await self.handler_func(update, context)

class MultiMessageHandler(BaseHandler):
    """Handler für Commands die mehrere Nachrichten senden."""
    
    def __init__(self, name: str, message_func: Callable):
        super().__init__(name)
        self.message_func = message_func
    
    async def execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> Optional[str]:
        messages = await self.message_func(update, context)
        if isinstance(messages, list):
            for msg in messages:
                await self._send_message(update, msg)
            return None  # Bereits gesendet
        return messages

def create_simple_handler(name: str, message: str) -> BaseHandler:
    """Factory-Funktion für einfache statische Messages."""
    async def get_message():
        return message
    return SimpleHandler(name, get_message)

def create_version_handler(name: str) -> BaseHandler:
    """Factory-Funktion für Version-Handler."""
    from formatters import fmt_version
    
    async def get_version_message():
        return fmt_version(config.get_version_dict())
    
    return SimpleHandler(name, get_version_message)

def create_help_handler(name: str) -> BaseHandler:
    """Factory-Funktion für Hilfe-Handler."""
    from config import get_help_text
    
    async def get_help_message():
        return get_help_text()
    
    return SimpleHandler(name, get_help_message)

def with_error_handling(handler_func: Callable) -> Callable:
    """Decorator für Legacy-Handler um Error-Handling zu ergänzen."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await handler_func(update, context)
        except Exception as e:
            log.exception(f"Error in handler {handler_func.__name__}: {e}")
            await update.effective_chat.send_message(
                "❌ Ein Fehler ist aufgetreten. Bitte versuchen Sie es später erneut.",
                parse_mode=ParseMode.HTML
            )
    return wrapper