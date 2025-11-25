#!/usr/bin/env python3
"""
API Data Fetcher - Aktualisiert alle Beispieldateien mit aktuellen API-Daten
"""
import asyncio
import json
import os
import sys
from clash import ClashClient
from config import config

async def fetch_all_api_data():
    """Holt alle aktuellen API-Daten und speichert sie in api-examples/"""
    
    print("🚀 Starte API-Daten-Aktualisierung...")
    
    # Konfiguration prüfen
    if not config.CLASH_TOKEN or not config.CLAN_TAG:
        print("❌ Fehlende API-Konfiguration! CLASH_TOKEN oder CLAN_TAG nicht gesetzt.")
        return False
    
    print(f"🔧 Verwende Clan-Tag: {config.CLAN_TAG}")
    
    # Client initialisieren
    client = ClashClient(config.CLASH_TOKEN, config.CLAN_TAG)
    
    # Erstelle api-examples Verzeichnis falls es nicht existiert
    os.makedirs("api-examples", exist_ok=True)
    
    try:
        # 1. Clan-Informationen
        print("📊 Hole Clan-Informationen...")
        clan_data = await client.get_clan()
        with open("api-examples/clan.json", "w", encoding="utf-8") as f:
            json.dump(clan_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Clan-Info gespeichert: {clan_data.get('name')} ({clan_data.get('members')} Mitglieder)")
        
        # 2. Mitglieder-Liste
        print("👥 Hole Mitglieder-Liste...")
        members_data = await client.get_members()
        with open("api-examples/members.json", "w", encoding="utf-8") as f:
            json.dump(members_data, f, indent=2, ensure_ascii=False)
        print(f"✅ Mitglieder gespeichert: {len(members_data.get('items', []))} Mitglieder")
        
        # 3. Aktuelle River Race
        print("⚔️ Hole aktuelle River Race Daten...")
        river_race = await client.get_current_river_fresh(attempts=2)
        with open("api-examples/currentriverrace.json", "w", encoding="utf-8") as f:
            json.dump(river_race, f, indent=2, ensure_ascii=False)
        
        clan_participants = river_race.get('clan', {}).get('participants', [])
        print(f"✅ River Race gespeichert: {len(clan_participants)} Teilnehmer")
        
        # 4. River Race Log (Historie)
        print("📜 Hole River Race Historie...")
        river_log = await client.get_river_log(limit=50)
        with open("api-examples/riverracelog.json", "w", encoding="utf-8") as f:
            json.dump(river_log, f, indent=2, ensure_ascii=False)
        
        log_items = river_log.get('items', [])
        print(f"✅ River Race Log gespeichert: {len(log_items)} historische River Races")
        
        # 5. Clan Rankings (falls verfügbar)
        print("🏆 Hole Clan Rankings...")
        try:
            ranking = await client.get_clan_ranking()
            ranking_data = {"rank": ranking} if ranking else {"rank": None}
            with open("api-examples/ranking.json", "w", encoding="utf-8") as f:
                json.dump(ranking_data, f, indent=2, ensure_ascii=False)
            
            if ranking:
                print(f"✅ Ranking gespeichert: Platz #{ranking}")
            else:
                print("✅ Ranking gespeichert: Nicht in Top 200")
        except Exception as e:
            print(f"⚠️  Ranking konnte nicht geladen werden: {e}")
            with open("api-examples/ranking.json", "w", encoding="utf-8") as f:
                json.dump({"rank": None, "error": str(e)}, f, indent=2, ensure_ascii=False)
        
        print("\n🎉 Alle API-Daten erfolgreich aktualisiert!")
        
        # Zeige einige Statistiken zur Überprüfung
        print("\n📊 Daten-Überprüfung:")
        
        # Prüfe River Race Teilnehmer auf Aktivität
        active_count = 0
        inactive_count = 0
        for participant in clan_participants:
            decks_used = int(participant.get('decksUsed', 0))
            fame = int(participant.get('fame', 0))
            if decks_used > 0 or fame > 0:
                active_count += 1
            else:
                inactive_count += 1
        
        print(f"• River Race Aktivität: {active_count} aktive, {inactive_count} inaktive Spieler")
        
        # Prüfe Spenden-Aktivität
        total_donations = 0
        donation_count = 0
        for member in members_data.get('items', []):
            donations = int(member.get('donations', 0))
            total_donations += donations
            if donations > 0:
                donation_count += 1
        
        print(f"• Spenden-Aktivität: {donation_count} Spieler haben gespendet, Summe: {total_donations}")
        
        # Prüfe letzte Aktivität
        import datetime
        from formatters import parse_sc_time
        
        recent_activity = 0
        for member in members_data.get('items', []):
            last_seen = parse_sc_time(member.get('lastSeen', ''))
            if last_seen:
                days_ago = (datetime.datetime.now(datetime.timezone.utc) - last_seen).days
                if days_ago <= 7:
                    recent_activity += 1
        
        print(f"• Letzte Woche aktiv: {recent_activity} Spieler")
        
        # Spezielle Prüfung für "sali"
        sali_found = False
        for participant in clan_participants:
            if participant.get('name') == 'sali':
                sali_found = True
                print(f"• Spieler 'sali': {participant.get('fame', 0)} Fame, {participant.get('decksUsed', 0)} Decks verwendet")
                break
        
        if not sali_found:
            print("• Spieler 'sali' nicht in aktueller River Race gefunden")
            
    except Exception as e:
        print(f"❌ Fehler beim Laden der API-Daten: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(fetch_all_api_data())
    if success:
        print("\n✅ API-Beispieldateien wurden erfolgreich aktualisiert!")
        print("📁 Gespeichert in: api-examples/")
    else:
        print("\n❌ Fehler beim Aktualisieren der API-Daten")