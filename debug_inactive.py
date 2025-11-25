#!/usr/bin/env python3
"""
Detaillierte Analyse der /inaktiv Funktion für Debugging
"""
import asyncio
import json
from clash import ClashClient
from config import config
from formatters import fmt_inactive_players

async def debug_inactive_analysis():
    """Analysiert die Inaktivitäts-Bewertung detailliert"""
    
    print("🔍 Detaillierte /inaktiv Analyse...")
    
    # Client initialisieren
    client = ClashClient(config.CLASH_TOKEN, config.CLAN_TAG)
    
    try:
        # Mitglieder und River Race Daten laden
        print("📊 Lade Clan-Daten...")
        members = await client.get_members()
        river_race = await client.get_current_river_fresh()
        river_log = await client.get_river_log(limit=50)
        
        # Suche nach "sali" in den Daten
        sali_data = None
        for member in members.get('items', []):
            if member.get('name') == 'sali':
                sali_data = member
                break
        
        if not sali_data:
            print("❌ Spieler 'sali' nicht in Clan-Mitgliedern gefunden")
            return
        
        print(f"\n👤 Spieler: {sali_data.get('name')} ({sali_data.get('tag')})")
        print(f"🏆 Trophäen: {sali_data.get('trophies', 0)}")
        print(f"💰 Spenden: {sali_data.get('donations', 0)}")
        print(f"📅 Zuletzt gesehen: {sali_data.get('lastSeen', 'Unbekannt')}")
        print(f"⭐ Rolle: {sali_data.get('role', 'member')}")
        
        # River Race Aktivität
        sali_participant = None
        for participant in river_race.get('clan', {}).get('participants', []):
            if participant.get('name') == 'sali':
                sali_participant = participant
                break
        
        if sali_participant:
            print(f"\n⚔️ Aktuelle River Race:")
            print(f"   Fame: {sali_participant.get('fame', 0)}")
            print(f"   Decks verwendet: {sali_participant.get('decksUsed', 0)}")
            print(f"   Boot-Angriffe: {sali_participant.get('boatAttacks', 0)}")
        
        # Historische Analyse
        print(f"\n📜 River Race Historie (letzten 10 Races):")
        sali_history = []
        
        for i, race in enumerate(river_log.get('items', [])[:10]):
            found_in_race = False
            for clan_data in race.get('standings', []):
                if clan_data.get('clan', {}).get('tag') == '#RLPR02L0':  # Unser Clan
                    for participant in clan_data.get('clan', {}).get('participants', []):
                        if participant.get('name') == 'sali':
                            fame = participant.get('fame', 0)
                            decks = participant.get('decksUsed', 0)
                            boats = participant.get('boatAttacks', 0)
                            
                            sali_history.append({
                                'race': i + 1,
                                'fame': fame,
                                'decks': decks,
                                'boats': boats,
                                'seasonId': race.get('seasonId', 'N/A'),
                                'section': race.get('sectionIndex', 'N/A')
                            })
                            
                            print(f"   Race {i+1} (S{race.get('seasonId')}-{race.get('sectionIndex')}): {fame} Fame, {decks} Decks, {boats} Boote")
                            found_in_race = True
                            break
                    break
            
            if not found_in_race:
                print(f"   Race {i+1}: Nicht teilgenommen")
        
        # Berechnete Inaktivitäts-Scores
        print(f"\n🧮 Score-Berechnung für 'sali':")
        
        # Simuliere die Score-Berechnung aus fmt_inactive_players
        total_fame = sum(h['fame'] for h in sali_history)
        total_decks = sum(h['decks'] for h in sali_history)
        total_boats = sum(h['boats'] for h in sali_history)
        donations = sali_data.get('donations', 0)
        
        print(f"   Gesamt Fame (historisch): {total_fame}")
        print(f"   Gesamt Decks (historisch): {total_decks}")
        print(f"   Gesamt Boot-Angriffe (historisch): {total_boats}")
        print(f"   Spenden (aktuell): {donations}")
        
        # Gewichteter Inaktivitäts-Score (aus formatters.py)
        war_attacks_weight = 0.35
        war_points_weight = 0.30
        donations_weight = 0.20
        last_seen_weight = 0.15
        
        # Normalisierte Scores (je niedriger, desto inaktiver)
        war_attacks_score = total_decks  # Vereinfacht
        war_points_score = total_fame  # Vereinfacht
        donations_score = donations
        
        total_score = (war_attacks_score * war_attacks_weight + 
                      war_points_score * war_points_weight + 
                      donations_score * donations_weight)
        
        print(f"   Inaktivitäts-Score: {total_score:.2f}")
        print(f"   (Je niedriger = inaktiver)")
        
        print(f"\n🎯 Fazit:")
        if total_fame > 0 or total_decks > 0:
            print(f"   ✅ 'sali' zeigt historische Aktivität")
            print(f"   📊 Sollte nicht als komplett inaktiv gewertet werden")
        else:
            print(f"   ❌ 'sali' zeigt keine messbare Aktivität")
        
    except Exception as e:
        print(f"❌ Fehler bei der Analyse: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_inactive_analysis())