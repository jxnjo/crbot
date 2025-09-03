from telegram import BotCommand

COMMANDS_GROUP = [
    BotCommand("status", "Prüft, ob der Bot läuft"),
    BotCommand("claninfo", "Claninfos"),
    BotCommand("offeneangriffe", "Offene Kriegsangriffe (heute)"),
    BotCommand("aktivitaet", "Am längsten offline → zuletzt online"),
    BotCommand("krieginfo", "Punktevergleich (auto) – Tipp: /krieginfo [heute|gesamt]"),
    BotCommand("krieginfoheute", "Punktevergleich nur für heute (Tagespunkte)"),
    BotCommand("krieginfogesamt", "Punktevergleich gesamt (Wochenpunkte)"),
    BotCommand("krieghistorie", "Kriegshistorie (optional Name: /krieghistorie Max)"),  # NEU
    BotCommand("hilfe", "Zeigt alle Befehle"),
]

COMMANDS_PRIVATE = [
    BotCommand("status", "Ping/Status"),
    BotCommand("claninfo", "Claninfos"),
    BotCommand("krieginfo", "Punktevergleich (auto)"),
    BotCommand("krieginfoheute", "Punktevergleich: heute"),
    BotCommand("krieginfogesamt", "Punktevergleich: gesamt"),
    BotCommand("krieghistorie", "Kriegshistorie (optional mit Name)"),  # NEU
    BotCommand("hilfe", "Zeigt alle Befehle"),
]

def get_help_text() -> str:
    lines = [
        "🤖 <b>Verfügbare Befehle & Alternativen</b>\n",
        "/status – Prüft, ob der Bot läuft (Alias: /start)",
        "/claninfo – Zeigt aktuelle Claninfos von Drablibe",
        "/offeneangriffe – Offene Kriegsangriffe heute (Versuche: 2, Alias: /offeneangriffe force)",
        "/online – Zeigt Mitglieder nach letzter Online-Zeit (Alias: /aktivitaet)",
        "/krieginfo – Punktevergleich (auto, Alias: /krieginfo heute /krieginfo gesamt)",
        "/krieginfoheute – Punktevergleich nur für heute (Tagespunkte)",
        "/krieginfogesamt – Punktevergleich gesamt (Wochenpunkte)",
        "/spenden [Nummer|all] – Spenden-Übersicht, z.B. /spenden 5 für Top 5, /spenden all für alle",
        "/krieghistorie [Name?] – Clanwar-Historie, optional mit Name für Details (z.B. /krieghistorie Max)",
        "/hilfe – Diese Übersicht (Alias: /commands /help)",
    ]
    return "\n".join(lines)
