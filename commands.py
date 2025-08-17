from telegram import BotCommand

COMMANDS_GROUP = [
    BotCommand("status", "Prüft, ob der Bot läuft"),
    BotCommand("claninfo", "Claninfos"),
    BotCommand("offeneangriffe", "Offene Kriegsangriffe (heute)"),
    BotCommand("aktivitaet", "Am längsten offline → zuletzt online"),
    BotCommand("krieginfo", "Punktevergleich (auto) – Tipp: /krieginfo [heute|gesamt]"),
    BotCommand("krieginfoheute", "Punktevergleich nur für heute (Tagespunkte)"),
    BotCommand("krieginfogesamt", "Punktevergleich gesamt (Wochenpunkte)"),
    BotCommand("hilfe", "Zeigt alle Befehle"),
]

COMMANDS_PRIVATE = [
    BotCommand("status", "Ping/Status"),
    BotCommand("claninfo", "Claninfos"),
    BotCommand("krieginfo", "Punktevergleich (auto)"),
    BotCommand("krieginfoheute", "Punktevergleich: heute"),
    BotCommand("krieginfogesamt", "Punktevergleich: gesamt"),
    BotCommand("hilfe", "Zeigt alle Befehle"),
]

def get_help_text() -> str:
    lines = [
        "🤖 <b>Verfügbare Befehle</b>\n",
        "/status – Prüft, ob der Bot läuft",
        "/claninfo – Claninfos",
        "/offeneangriffe – Offene Kriegsangriffe (heute)",
        "/aktivitaet – Am längsten offline → zuletzt online",
        "/krieginfo – Punktevergleich (auto). Tipp: <i>/krieginfo heute</i> oder <i>/krieginfo gesamt</i>",
        "/krieginfoheute – Punktevergleich nur für heute (Tagespunkte)",
        "/krieginfogesamt – Punktevergleich gesamt (Wochenpunkte)",
        "/hilfe – Diese Übersicht",
    ]
    return "\n".join(lines)
