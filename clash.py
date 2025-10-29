"""
Refactored Clash Royale API Client.
Konzentriert sich nur auf API-Kommunikation und Datenverarbeitung.
Formatierungs-Funktionen wurden nach formatters.py ausgelagert.
"""
import os
import time
import httpx
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from config import config

logger = logging.getLogger(__name__)
from handlers import APIError

# zoneinfo + Fallback
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except Exception:
    ZoneInfo = None
    class ZoneInfoNotFoundError(Exception): 
        pass

def get_local_tz():
    """Gibt die lokale Zeitzone zurück."""
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(config.BOT_TZ)
    except ZoneInfoNotFoundError:
        return timezone.utc

LOCAL_TZ = get_local_tz()

class ClashClient:
    """Clash Royale API Client mit robustem Error-Handling."""
    
    BASE = "https://api.clashroyale.com/v1"

    def __init__(self, token: str, clan_tag: str, timeout: int = None):
        if not token:
            raise ValueError("Clash Royale API Token ist erforderlich")
        if not clan_tag:
            raise ValueError("Clan Tag ist erforderlich")
            
        self.token = token
        self.clan_tag = clan_tag.lstrip("#").upper()
        self.timeout = timeout or config.API_TIMEOUT
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def _clan_path(self, suffix: str = "") -> str:
        """Erstellt den API-Pfad für den konfigurierten Clan."""
        tag = f"%23{self.clan_tag}"
        return f"{self.BASE}/clans/{tag}{suffix}"

    async def _get(self, url: str, cache_bust: bool = False) -> Dict[str, Any]:
        """Führt einen HTTP GET-Request zur Clash Royale API aus."""
        headers = {
            **self.headers,
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
        }
        params = {"ts": int(time.time() * 1000)} if cache_bust else None
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.TimeoutException as e:
            raise APIError(f"API Timeout: {e}", "Die Clash Royale API antwortet nicht rechtzeitig.")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise APIError(f"Clan nicht gefunden: {self.clan_tag}", "Der angegebene Clan wurde nicht gefunden.")
            elif e.response.status_code == 403:
                raise APIError("API Token ungültig", "Clash Royale API Token ist ungültig oder abgelaufen.")
            elif e.response.status_code == 429:
                raise APIError("API Rate Limit erreicht", "Zu viele API-Anfragen. Bitte versuchen Sie es später erneut.")
            else:
                raise APIError(f"API Fehler: {e.response.status_code}", "Fehler beim Abrufen der Daten von Clash Royale.")
        except Exception as e:
            raise APIError(f"Unerwarteter Fehler: {e}", "Ein unerwarteter Fehler ist beim API-Aufruf aufgetreten.")

    # --- API calls (eigener Clan) ---
    async def get_clan(self) -> Dict[str, Any]:
        """Holt Clan-Informationen."""
        return await self._get(self._clan_path(""), cache_bust=False)

    async def get_clan_info(self, clan_tag: str) -> Dict[str, Any]:
        """Holt Clan-Informationen für einen spezifischen Clan."""
        # Entferne # falls vorhanden und füge es wieder hinzu
        clean_tag = clan_tag.lstrip('#')
        encoded_tag = f"%23{clean_tag}"
        url = f"https://api.clashroyale.com/v1/clans/{encoded_tag}"
        
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(self.timeout)) as client:
                response = await client.get(url, headers={"Authorization": f"Bearer {self.token}"})
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise APIError("Clan nicht gefunden", f"Clan {clan_tag} existiert nicht.")
            else:
                raise APIError(f"API Fehler: {e.response.status_code}", "Fehler beim Abrufen der Clan-Daten.")
        except Exception as e:
            raise APIError(f"Unerwarteter Fehler: {e}", "Ein unerwarteter Fehler ist beim API-Aufruf aufgetreten.")

    async def get_current_river(self, force: bool = True) -> Dict[str, Any]:
        """Holt aktuelle River Race Daten."""
        return await self._get(self._clan_path("/currentriverrace"), cache_bust=force)

    async def get_members(self) -> Dict[str, Any]:
        """Holt Clan-Mitglieder."""
        return await self._get(self._clan_path("/members"), cache_bust=False)

    async def get_river_log(self, limit: int = None) -> Dict[str, Any]:
        """Holt River Race Log."""
        if limit is None:
            limit = config.DEFAULT_WAR_HISTORY_LIMIT
        return await self._get(self._clan_path(f"/riverracelog?limit={limit}"), cache_bust=True)

    # --- API calls (beliebiger Clan) ---
    async def get_members_of(self, clan_tag_nohash: str) -> Dict[str, Any]:
        """Holt Mitglieder eines beliebigen Clans."""
        tag = clan_tag_nohash.upper().lstrip("#")
        return await self._get(f"{self.BASE}/clans/%23{tag}/members", cache_bust=False)

    async def get_river_log_of(self, clan_tag_nohash: str, limit: int = 80) -> Dict[str, Any]:
        """Holt River Race Log eines beliebigen Clans."""
        tag = clan_tag_nohash.upper().lstrip("#")
        return await self._get(f"{self.BASE}/clans/%23{tag}/riverracelog?limit={limit}", cache_bust=True)

    # ---------- Fresh-Strategy für /currentriverrace ----------
    async def get_current_river_fresh(self, attempts: int = None, max_decks: int = None) -> Dict[str, Any]:
        """
        Holt aktuelle River Race Daten mit mehreren Versuchen bei vermutlich veralteten Daten.
        """
        if attempts is None:
            attempts = config.OPEN_ATTACKS_ATTEMPTS_DEFAULT
        if max_decks is None:
            max_decks = config.MAX_DECKS_PER_DAY
            
        rr = await self.get_current_river(force=True)
        
        if attempts <= 1:
            return rr
            
        if self._looks_stale(rr, max_decks=max_decks):
            rr = await self.get_current_river(force=True)
            if attempts >= 3 and self._looks_stale(rr, max_decks=max_decks):
                rr = await self.get_current_river(force=True)
                
        return rr

    def _looks_stale(self, rr: Dict[str, Any], max_decks: int = None) -> bool:
        """
        Heuristik: ist die River Race Liste vermutlich "alt"?
        Prüft ob zu viele Spieler noch alle Decks haben (nach 17 Uhr).
        """
        if max_decks is None:
            max_decks = config.MAX_DECKS_PER_DAY
            
        clan = rr.get("clan") or {}
        participants = clan.get("participants") or []
        
        if not participants:
            return False
            
        rows = []
        for p in participants:
            used = int(p.get("decksUsedToday") or 0)
            remaining = max(max_decks - used, 0)
            rows.append(remaining)
            
        total = len(rows)
        four_open = sum(1 for r in rows if r == max_decks)
        hour_local = datetime.now(LOCAL_TZ).hour
        
        return total > 0 and four_open / total >= 0.70 and hour_local >= 17

# ---------- War History Aggregation ----------
def _aggregate_war_history(rlog: Dict[str, Any], my_tag_nohash: str) -> Dict[str, Dict[str, Any]]:
    """
    Aggregiert alle Teilnehmer unseres Clans über das RiverRace-Log.
    Rückgabe: dict[tag] = {name, fame, repair, decks, boats, wars, first_seen, last_seen}
    """
    from formatters import parse_sc_time  # Import hier um zirkuläre Imports zu vermeiden
    
    my_tag = my_tag_nohash.upper().lstrip("#")
    items = rlog.get("items") or []
    acc: Dict[str, Dict[str, Any]] = {}

    for it in items:
        # Zeitstempel der Woche/Section
        at = parse_sc_time(it.get("createdDate") or it.get("endTime") or 
                          it.get("finishedTime") or it.get("updatedTime"))

        standings = it.get("standings") or []
        for st in standings:
            clan_obj = st.get("clan") or {}
            tag = (clan_obj.get("tag") or "").upper().lstrip("#")
            if tag != my_tag:
                continue
                
            for p in (clan_obj.get("participants") or []):
                ptag = (p.get("tag") or "").upper().lstrip("#")
                if not ptag:
                    # Falls Tag fehlt, über Name fallen lassen (kann doppeln)
                    ptag = f"NON-{p.get('name','?')}"
                    
                entry = acc.setdefault(ptag, {
                    "name": p.get("name", "Unbekannt"),
                    "fame": 0, "repair": 0,
                    "decks": 0, "boats": 0,
                    "wars": 0,
                    "first_seen": at, "last_seen": at,
                })
                
                entry["name"] = p.get("name", entry["name"])
                entry["fame"] += int(p.get("fame") or 0)
                entry["repair"] += int(p.get("repairPoints") or 0)
                entry["decks"] += int(p.get("decksUsed") or 0)
                entry["boats"] += int(p.get("boatAttacks") or 0)
                entry["wars"] += 1
                
                if at:
                    if not entry["first_seen"] or (entry["first_seen"] and at < entry["first_seen"]):
                        entry["first_seen"] = at
                    if not entry["last_seen"] or (entry["last_seen"] and at > entry["last_seen"]):
                        entry["last_seen"] = at
                        
    return acc

# =====================  SPIONAGE: aktivsten Gegner ermitteln  =====================



async def _pick_best_opponent(client: ClashClient, rr: dict, my_tag_nohash: str) -> Optional[dict]:
    """Wählt den aktivsten Gegnerclan basierend auf aktuellen River Race Daten."""
    my_tag = my_tag_nohash.upper().lstrip("#")

    # Gegner aus aktuellem RiverRace einsammeln (inkl. periodPoints für bessere Bewertung)
    enemy_list: List[Dict] = []
    
    # Alle Clans aus der aktuellen River Race durchgehen
    all_clans = (rr.get("clans") or [])
    
    # Unser Clan hinzufügen wenn er nicht in clans steht
    our_clan = rr.get("clan")
    if our_clan and (our_clan.get("tag") or "").upper().lstrip("#") == my_tag:
        # Unser Clan ist bereits der Haupteintrag, Gegner sind in clans Array
        pass  
    else:
        # Unser Clan könnte in clans Array stehen
        if our_clan:
            all_clans.append(our_clan)

    for c in all_clans:
        tag = (c.get("tag") or "").upper().lstrip("#")
        if not tag or tag == my_tag:
            continue
            
        # Aktivitätsbewertung basierend auf aktuellen Daten
        fame = int(c.get("fame") or 0)
        period_points = int(c.get("periodPoints") or 0)  # Tagespunkte
        participants = c.get("participants") or []
        
        # Berechne Aktivitätsmetriken
        active_players = sum(1 for p in participants if int(p.get("fame") or 0) > 0)
        total_decks_used = sum(int(p.get("decksUsed") or 0) for p in participants)
        total_decks_today = sum(int(p.get("decksUsedToday") or 0) for p in participants)
        
        # Score: kombiniert Gesamtpunkte, heutige Aktivität und Spielerbeteiligung
        activity_score = (
            fame * 0.4 +           # Gesamtleistung
            period_points * 0.4 +   # Heutige Leistung (wichtig!)
            active_players * 50 +   # Anzahl aktiver Spieler
            total_decks_used * 10   # Gesamte Deck-Nutzung
        )
        
        enemy_list.append({
            "tag": tag,
            "name": c.get("name", "Unbekannt"),
            "fame": fame,
            "period_points": period_points,
            "participants": len(participants),
            "active_players": active_players,
            "total_decks_used": total_decks_used,
            "total_decks_today": total_decks_today,
            "activity_score": activity_score,
            "clan_data": c  # Originaldaten für Details
        })

    if not enemy_list:
        return None

    # Besten Gegner nach Activity-Score auswählen
    best = max(enemy_list, key=lambda x: x["activity_score"])
    
    if best["activity_score"] == 0:
        # Alle Gegner inaktiv, nehme den mit den meisten Mitgliedern
        best = max(enemy_list, key=lambda x: x["participants"])
    
    return best

async def spy_make_messages(client: ClashClient, my_tag_nohash: str, days: int = None) -> List[str]:
    """
    Baut die Nachrichten für /spion mit historischer Analyse.
    Nachricht 1: Kurz-Summary.
    Nachricht 2: Historische Leistungsanalyse.
    Nachricht 3: Aktuelle Details.
    """
    if days is None:
        days = config.DEFAULT_SPY_DAYS
        
    rr = await client.get_current_river_fresh(attempts=2)
    best = await _pick_best_opponent(client, rr, my_tag_nohash)
    
    if not best:
        return ["Es wurden keine Gegner im aktuellen River Race gefunden."]

    # Hole zusätzliche Clan-Info für tatsächliche Mitgliederzahl
    try:
        clan_info = await client.get_clan_info(best["tag"])
        best["total_members"] = len(clan_info.get("memberList", []))
    except Exception as e:
        logger.warning(f"Konnte Clan-Info für {best['tag']} nicht laden: {e}")
        best["total_members"] = best["participants"]  # Fallback

    messages = []
    
    # Nachricht 1: Kurz-Summary
    summary = _format_spy_summary(best)
    messages.append(summary)
    
    # Nachricht 2: Historische Analyse
    try:
        river_log = await client.get_river_log_of(best["tag"])
        historical_analysis = _analyze_opponent_history(best["tag"], river_log)
        logger.info(f"Spion Debug: Gegnerclan {best['tag']}, Historische Daten: {len(historical_analysis) if historical_analysis else 0}")
        if historical_analysis:
            history_msg = _format_historical_analysis(best, historical_analysis)
            messages.append(history_msg)
            logger.info(f"Spion Debug: Historische Nachricht erstellt ({len(history_msg)} Zeichen)")
        else:
            debug_msg = f"⚠️ Keine historischen Daten für Gegnerclan {best['name']} ({best['tag']}) gefunden."
            messages.append(debug_msg)
            logger.info(f"Spion Debug: {debug_msg}")
    except Exception as e:
        error_msg = f"⚠️ Historische Daten konnten nicht geladen werden: {str(e)}"
        logger.error(f"Fehler beim Laden der historischen Daten: {e}")
        messages.append(error_msg)
    
    # Nachricht 3: Aktuelle Details
    details = _format_spy_details(best, rr)
    messages.append(details)

    logger.info(f"Spion Debug: Insgesamt {len(messages)} Nachrichten erstellt")
    return messages

def _format_spy_summary(opponent: dict) -> str:
    """Formatiert die Kurz-Zusammenfassung für den besten Gegner."""
    from formatters import _bar
    
    name = opponent["name"]
    tag = opponent["tag"] 
    fame = opponent["fame"]
    period_points = opponent["period_points"]
    participants = opponent["participants"]
    active_players = opponent["active_players"]
    total_members = opponent.get("total_members", participants)
    
    # Aktivitätsrate berechnen
    activity_rate = active_players / participants if participants > 0 else 0.0
    bar = _bar(activity_rate)
    
    lines = [
        f"<b>Gegner-Spionage: Aktivster Clan</b>",
        f"",
        f"<b>{name}</b> (#{tag})",
        f"Clan-Mitglieder: <b>{total_members}/50</b>",
        f"River Race: <b>{participants}</b> Teilnehmer | <b>{active_players}</b> aktiv ({int(activity_rate*100)}%)",
        f"Aktivitaetsrate: <code>{bar}</code>",
        f"",
        f"<b>Aktuelle Leistung:</b>",
        f"Gesamtpunkte: <b>{fame:,}</b>",
        f"Heute: <b>{period_points:,}</b> Punkte"
    ]
    
    return "\n".join(lines)[:config.MAX_MESSAGE_LENGTH]

def _format_spy_details(opponent: dict, rr: dict) -> str:
    """Formatiert die detaillierte Analyse des Gegner-Clans."""
    clan_data = opponent["clan_data"]
    participants = clan_data.get("participants", [])
    
    # Top Spieler nach Fame sortieren
    top_players = sorted(
        [p for p in participants if int(p.get("fame", 0)) > 0],
        key=lambda x: int(x.get("fame", 0)),
        reverse=True
    )[:10]  # Top 10
    
    # Deck-Nutzung Statistiken
    deck_usage_stats = []
    for p in participants:
        used = int(p.get("decksUsed", 0))
        used_today = int(p.get("decksUsedToday", 0))
        if used > 0 or used_today > 0:
            deck_usage_stats.append((p.get("name", "?"), used, used_today))
    
    deck_usage_stats.sort(key=lambda x: x[1], reverse=True)
    
    lines = [
        f"<b>Detailanalyse: {opponent['name']}</b>",
        f"",
        f"<b>Top Spieler (nach Gesamtpunkten):</b>"
    ]
    
    for i, player in enumerate(top_players[:5], 1):
        name = player.get("name", "?")
        fame = int(player.get("fame", 0))
        decks_used = int(player.get("decksUsed", 0))
        boat_attacks = int(player.get("boatAttacks", 0))
        lines.append(f"{i}. {name} - {fame:,} Punkte ({decks_used}D, {boat_attacks}B)")
    
    if not top_players:
        lines.append("- Keine aktiven Spieler gefunden")
    
    lines.extend([
        f"",
        f"<b>Aktivste Spieler (nach Deck-Nutzung):</b>"
    ])
    
    for i, (name, used, used_today) in enumerate(deck_usage_stats[:5], 1):
        today_marker = f" (+{used_today} heute)" if used_today > 0 else ""
        lines.append(f"{i}. {name} - {used} Decks{today_marker}")
    
    if not deck_usage_stats:
        lines.append("- Keine Deck-Nutzung gefunden")
    
    # Zusätzliche Statistiken
    total_fame = sum(int(p.get("fame", 0)) for p in participants)
    total_decks = sum(int(p.get("decksUsed", 0)) for p in participants)
    total_boats = sum(int(p.get("boatAttacks", 0)) for p in participants)
    avg_fame_per_player = total_fame / len(participants) if participants else 0
    
    # Berechne Teilnahmequote sicher
    participation_pct = 0
    if opponent['participants'] > 0:
        participation_pct = int(opponent['active_players'] / opponent['participants'] * 100)

    lines.extend([
        f"",
        f"<b>Clan-Statistiken:</b>",
        f"- O Punkte/Spieler: {avg_fame_per_player:.0f}",
        f"- Gesamt Decks: {total_decks}",
        f"- Gesamt Bootangriffe: {total_boats}",
        f"- Teilnahmequote: {opponent['active_players']}/{opponent['participants']} ({participation_pct}%)"
    ])
    
    return "\n".join(lines)[:config.MAX_MESSAGE_LENGTH]

def _analyze_opponent_history(opponent_tag: str, river_log: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    """
    Analysiert die historische Leistung eines Gegnerclans über mehrere River Races.

    Args:
        opponent_tag: Tag des Gegnerclans (mit oder ohne #)
        river_log: River Race Log Daten

    Returns:
        Liste von historischen Leistungsdaten oder None
    """
    if not river_log or 'items' not in river_log:
        return None

    # Normalisiere Tag für Vergleich (ohne #, uppercase)
    opponent_tag_clean = opponent_tag.lstrip('#').upper()

    logger.info(f"_analyze_opponent_history: Suche nach Tag '{opponent_tag_clean}'")
    
    historical_data = []
    
    for race in river_log['items']:
        if 'standings' not in race:
            continue
            
        # Suche den Gegnerclan in den standings
        for standing in race['standings']:
            clan_info = standing.get('clan', {})
            clan_tag_clean = (clan_info.get('tag') or '').lstrip('#').upper()
            if clan_tag_clean == opponent_tag_clean:
                # Berechne Statistiken für diese Woche
                participants = clan_info.get('participants', [])
                total_participants = len(participants)
                active_participants = sum(1 for p in participants if int(p.get('decksUsed', 0)) > 0)
                total_decks_used = sum(int(p.get('decksUsed', 0)) for p in participants)
                total_fame = clan_info.get('fame', 0)
                
                participation_rate = active_participants / total_participants if total_participants > 0 else 0
                decks_per_active = total_decks_used / active_participants if active_participants > 0 else 0
                
                race_data = {
                    'season_id': race.get('seasonId'),
                    'section_index': race.get('sectionIndex'),
                    'created_date': race.get('createdDate'),
                    'rank': standing.get('rank'),
                    'trophy_change': standing.get('trophyChange'),
                    'fame': total_fame,
                    'finish_time': clan_info.get('finishTime'),
                    'total_participants': total_participants,
                    'active_participants': active_participants,
                    'participation_rate': participation_rate,
                    'total_decks_used': total_decks_used,
                    'decks_per_active': decks_per_active
                }
                
                historical_data.append(race_data)
                break
    
    # Sortiere nach Datum (neueste zuerst)
    historical_data.sort(key=lambda x: x.get('created_date', ''), reverse=True)
    
    return historical_data[:20]  # Maximal 20 letzte Wochen

def _format_historical_analysis(opponent: dict, historical_data: List[Dict[str, Any]]) -> str:
    """
    Formatiert die historische Analyse für einen Gegnerclan.
    
    Args:
        opponent: Aktuelle Gegnerclan-Daten
        historical_data: Liste der historischen Daten
        
    Returns:
        Formatierte HTML-Nachricht
    """
    from formatters import _bar
    
    name = opponent["name"]
    tag = opponent["tag"]
    
    lines = [
        f"<b>🕵️ Historische Analyse: {name}</b>",
        f"<code>#{tag}</code>",
        f"",
        f"<b>📊 Leistung der letzten {len(historical_data)} Wochen:</b>",
        f""
    ]
    
    if not historical_data:
        lines.append("⚠️ Keine historischen Daten verfügbar.")
        return '\n'.join(lines)
    
    # Header für Tabelle
    lines.extend([
        f"<code>Woche | Platz | Trophäen | Punkte  | Quote | Decks</code>",
        f"<code>------|-------|----------|---------|-------|------</code>"
    ])
    
    # Zeige maximal 15 Wochen in der Tabelle, aber verwende alle für Durchschnitte
    display_data = historical_data[:15]
    
    # Daten für jede Woche
    for i, race in enumerate(display_data, 1):
        season = race.get('season_id', 'N/A')
        section = race.get('section_index', 0)
        rank = race.get('rank', '?')
        trophy_change = race.get('trophy_change', 0)
        fame = race.get('fame', 0)
        participation = race.get('participation_rate', 0)
        decks_per_active = race.get('decks_per_active', 0)
        
        # Formatiere Zahlen für bessere Lesbarkeit
        trophy_str = f"+{trophy_change}" if trophy_change > 0 else str(trophy_change)
        fame_str = f"{fame:,}".replace(',', '.')
        if len(fame_str) > 6:
            fame_str = f"{fame//1000}k"
        
        participation_str = f"{int(participation*100)}%"
        decks_str = f"{decks_per_active:.1f}"
        
        week_label = f"S{season}.{section}" if season != 'N/A' else f"W-{i}"
        
        lines.append(
            f"<code>{week_label:>5} | {rank:>5} | {trophy_str:>8} | "
            f"{fame_str:>7} | {participation_str:>5} | {decks_str:>5}</code>"
        )
    
    # Notiz wenn mehr Daten verfügbar sind
    if len(historical_data) > len(display_data):
        lines.extend([
            f"",
            f"<i>... und {len(historical_data) - len(display_data)} weitere Wochen</i>"
        ])
    
    # Durchschnittliche Statistiken
    if historical_data:
        avg_rank = sum(race.get('rank', 0) for race in historical_data) / len(historical_data)
        avg_fame = sum(race.get('fame', 0) for race in historical_data) / len(historical_data)
        avg_participation = sum(race.get('participation_rate', 0) for race in historical_data) / len(historical_data)
        avg_decks = sum(race.get('decks_per_active', 0) for race in historical_data) / len(historical_data)
        
        participation_bar = _bar(avg_participation)
        
        lines.extend([
            f"",
            f"<b>📈 Durchschnittswerte:</b>",
            f"• Platzierung: <b>{avg_rank:.1f}</b>",
            f"• Punkte/Woche: <b>{avg_fame:,.0f}</b>".replace(',', '.'),
            f"• Teilnahmequote: <b>{int(avg_participation*100)}%</b>",
            f"• Quote: <code>{participation_bar}</code>",
            f"• Decks/Aktiver: <b>{avg_decks:.1f}</b>"
        ])
    
    return '\n'.join(lines)[:config.MAX_MESSAGE_LENGTH]