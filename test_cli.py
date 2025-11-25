#!/usr/bin/env python3
"""
Terminal Test Interface für CRBot Funktionen
Ermöglicht das Testen aller Bot-Funktionen direkt im Terminal ohne Telegram.
"""
import asyncio
import json
import os
import sys
from typing import Dict, Any

# Import der Bot-Module
from config import config, get_help_text
from clash import ClashClient, _aggregate_war_history, spy_make_messages
from formatters import (
    fmt_clan, fmt_activity_list, fmt_river_scoreboard, fmt_donations_leaderboard,
    fmt_open_decks_overview, fmt_war_history_summary, fmt_war_history_player_multi,
    fmt_inactive_players, fmt_version, fmt_player_details
)
from handlers import APIError

class TerminalTestCLI:
    """Terminal-basiertes Test-Interface für Bot-Funktionen."""
    
    def __init__(self):
        self.clash = None
        self.use_mock_data = False
        
    def initialize_client(self):
        """Initialisiert den Clash Client oder Mock-Daten."""
        try:
            # Versuche echten API-Client zu verwenden
            if config.BOT_TOKEN and config.CLASH_TOKEN and config.CLAN_TAG:
                self.clash = ClashClient(config.CLASH_TOKEN, config.CLAN_TAG)
                print("✅ Echter Clash Royale API Client initialisiert")
            else:
                raise ValueError("API-Token nicht konfiguriert")
        except Exception as e:
            print(f"⚠️  Echter API-Client nicht verfügbar: {e}")
            print("📁 Verwende Mock-Daten aus api-examples/")
            self.use_mock_data = True
    
    def load_mock_data(self, filename: str) -> Dict[str, Any]:
        """Lädt Mock-Daten aus dem api-examples Verzeichnis."""
        try:
            path = os.path.join("api-examples", filename)
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Fehler beim Laden von {filename}: {e}")
            return {}
    
    async def get_members_data(self):
        """Holt oder lädt Mitgliederdaten."""
        if self.use_mock_data:
            return self.load_mock_data("members.json")
        else:
            return await self.clash.get_members()
    
    async def get_river_race_data(self):
        """Holt oder lädt River Race Daten."""
        if self.use_mock_data:
            return self.load_mock_data("currentriverrace.json")
        else:
            return await self.clash.get_current_river_fresh(attempts=2)
    
    async def get_river_log_data(self):
        """Holt oder lädt River Race Log Daten."""
        if self.use_mock_data:
            return self.load_mock_data("riverracelog.json")
        else:
            return await self.clash.get_river_log(limit=50)
    
    async def get_clan_data(self):
        """Holt oder lädt Clan-Daten."""
        if self.use_mock_data:
            return self.load_mock_data("clan.json")
        else:
            return await self.clash.get_clan()
    
    def print_formatted(self, text: str, title: str = None):
        """Formatiert und druckt Text schön formatiert."""
        if title:
            print(f"\n{'='*60}")
            print(f"{title}")
            print('='*60)
        
        # Entferne HTML-Tags für Terminal-Ausgabe
        clean_text = text.replace("<b>", "").replace("</b>", "")
        clean_text = clean_text.replace("<i>", "").replace("</i>", "")
        clean_text = clean_text.replace("<code>", "").replace("</code>", "")
        
        print(clean_text)
        print()
    
    async def test_claninfo(self):
        """Testet /claninfo Funktion."""
        try:
            clan_data = await self.get_clan_data()
            
            # Hole auch Ranking-Information falls echte API verfügbar
            ranking = None
            if not self.use_mock_data:
                try:
                    ranking = await self.clash.get_clan_ranking()
                except Exception as e:
                    print(f"⚠️  Ranking konnte nicht geladen werden: {e}")
            
            result = fmt_clan(clan_data, config.CLAN_TAG, ranking)
            self.print_formatted(result, "TEST: /claninfo")
        except Exception as e:
            print(f"❌ Fehler bei /claninfo: {e}")
    
    async def test_aktivitaet(self):
        """Testet /aktivitaet Funktion."""
        try:
            members_data = await self.get_members_data()
            result = fmt_activity_list(members_data, config.CLAN_TAG)
            self.print_formatted(result, "TEST: /aktivitaet")
        except Exception as e:
            print(f"❌ Fehler bei /aktivitaet: {e}")
    
    async def test_krieginfo(self, mode="auto"):
        """Testet /krieginfo Funktionen."""
        try:
            river_race = await self.get_river_race_data()
            result = fmt_river_scoreboard(river_race, config.CLAN_TAG, mode=mode)
            self.print_formatted(result, f"TEST: /krieginfo {mode}")
        except Exception as e:
            print(f"❌ Fehler bei /krieginfo {mode}: {e}")
    
    async def test_spenden(self, limit=10):
        """Testet /spenden Funktion."""
        try:
            members_data = await self.get_members_data()
            result = fmt_donations_leaderboard(members_data, limit=limit, include_received=True)
            self.print_formatted(result, f"TEST: /spenden (limit={limit})")
        except Exception as e:
            print(f"❌ Fehler bei /spenden: {e}")
    
    async def test_offeneangriffe(self):
        """Testet /offeneangriffe Funktion."""
        try:
            river_race = await self.get_river_race_data()
            result = fmt_open_decks_overview(river_race, config.CLAN_TAG)
            self.print_formatted(result, "TEST: /offeneangriffe")
        except Exception as e:
            print(f"❌ Fehler bei /offeneangriffe: {e}")
    
    async def test_krieghistorie(self, player_name=None):
        """Testet /krieghistorie Funktion."""
        try:
            river_log = await self.get_river_log_data()
            
            if player_name:
                result_msgs = fmt_war_history_player_multi(
                    river_log, config.CLAN_TAG, player_name, _aggregate_war_history
                )
                for i, msg in enumerate(result_msgs):
                    self.print_formatted(msg, f"TEST: /krieghistorie {player_name} (Teil {i+1})")
            else:
                result = fmt_war_history_summary(river_log, config.CLAN_TAG, _aggregate_war_history)
                self.print_formatted(result, "TEST: /krieghistorie")
        except Exception as e:
            print(f"❌ Fehler bei /krieghistorie: {e}")
    
    async def test_inaktiv(self, sort_by="gesamt"):
        """Testet /inaktiv Funktion."""
        try:
            members_data = await self.get_members_data()
            river_race = await self.get_river_race_data()
            river_log = await self.get_river_log_data()
            
            result = fmt_inactive_players(members_data, river_race, river_log, sort_by=sort_by, limit=10)
            self.print_formatted(result, f"TEST: /inaktiv {sort_by}")
        except Exception as e:
            print(f"❌ Fehler bei /inaktiv {sort_by}: {e}")
    
    async def test_spion(self):
        """Testet /spion Funktion."""
        if self.use_mock_data:
            print("⚠️  /spion Funktion benötigt echte API-Daten - überspringe Test")
            return
        
        try:
            messages = await spy_make_messages(self.clash, config.CLAN_TAG, days=config.DEFAULT_SPY_DAYS)
            for i, msg in enumerate(messages):
                self.print_formatted(msg, f"TEST: /spion (Teil {i+1})")
        except Exception as e:
            print(f"❌ Fehler bei /spion: {e}")
    
    async def test_details(self, player_name=None):
        """Testet /details Funktion."""
        try:
            # Spielername bestimmen
            if player_name is None:
                player_name = input("Spielername eingeben (oder Enter für 'sali'): ").strip()
                if not player_name:
                    player_name = "sali"
            
            print(f"📊 Lade Spieler-Details für '{player_name}'...")
            
            # Daten laden
            members = await self.clash.get_members() if not self.use_mock_data else self.load_mock_data('members.json')
            river_race = await self.clash.get_current_river_fresh() if not self.use_mock_data else self.load_mock_data('currentriverrace.json')
            river_log = await self.clash.get_river_log(limit=20) if not self.use_mock_data else self.load_mock_data('riverracelog.json')
            
            result = fmt_player_details(player_name, members, river_race, river_log)
            self.print_formatted(result, f"TEST: /details {player_name}")
        except Exception as e:
            print(f"❌ Fehler bei /details: {e}")
    
    def test_version(self):
        """Testet /version Funktion."""
        try:
            result = fmt_version(config.get_version_dict())
            self.print_formatted(result, "TEST: /version")
        except Exception as e:
            print(f"❌ Fehler bei /version: {e}")
    
    def test_help(self):
        """Testet /hilfe Funktion."""
        try:
            result = get_help_text()
            self.print_formatted(result, "TEST: /hilfe")
        except Exception as e:
            print(f"❌ Fehler bei /hilfe: {e}")
    
    def show_menu(self):
        """Zeigt das Hauptmenü."""
        print("\n" + "="*60)
        print("🤖 CRBot Terminal Test Interface")
        print("="*60)
        print("Wählen Sie eine Funktion zum Testen:")
        print()
        print("1.  /claninfo        - Clan-Informationen")
        print("2.  /aktivitaet      - Aktivität der Mitglieder")
        print("3.  /krieginfo       - Krieg-Informationen (auto)")
        print("4.  /krieginfoheute  - Krieg-Informationen (heute)")
        print("5.  /krieginfogesamt - Krieg-Informationen (gesamt)")
        print("6.  /spenden         - Spenden-Rangliste")
        print("7.  /offeneangriffe  - Offene Deck-Angriffe")
        print("8.  /krieghistorie   - Krieg-Historie")
        print("9.  /inaktiv         - Inaktivste Spieler (gesamt)")
        print("10. /inaktiv spenden - Inaktivste nach Spenden")
        print("11. /inaktiv kriegsangriffe - Inaktivste nach Kriegsangriffen")
        print("12. /spion           - Gegner-Spionage")
        print("13. /details         - Spieler-Details (Beispiel: sali)")
        print("14. /version         - Bot-Version")
        print("15. /hilfe           - Hilfe-Text")
        print()
        print("💡 Direkte Commands: /details [Name] | /inaktiv [Typ]")
        print("0.  Beenden")
        print("="*60)
    
    async def run(self):
        """Hauptschleife des Test-Interfaces."""
        print("🚀 CRBot Terminal Test Interface wird gestartet...")
        
        # Client initialisieren
        self.initialize_client()
        
        while True:
            self.show_menu()
            try:
                user_input = input("Ihre Wahl (0-15 oder /command): ").strip()
                
                # Command-Parser für direkte Commands
                if user_input.startswith('/details '):
                    player_name = user_input[9:].strip()  # Entferne "/details "
                    if player_name:
                        await self.test_details(player_name)
                        input("\nDrücken Sie Enter um fortzufahren...")
                        continue
                    else:
                        print("❌ Bitte Spielername nach /details angeben")
                        input("\nDrücken Sie Enter um fortzufahren...")
                        continue
                elif user_input.startswith('/inaktiv '):
                    sort_by = user_input[9:].strip()  # Entferne "/inaktiv "
                    valid_sorts = ["spenden", "kriegsangriffe", "kriegspunkte", "trophäenpfad", "gesamt"]
                    if sort_by in valid_sorts:
                        await self.test_inaktiv(sort_by)
                        input("\nDrücken Sie Enter um fortzufahren...")
                        continue
                    else:
                        print(f"❌ Ungültiger Sortierparameter: {sort_by}")
                        input("\nDrücken Sie Enter um fortzufahren...")
                        continue
                
                # Normale Menü-Auswahl
                choice = user_input
                
                if choice == "0":
                    print("👋 Auf Wiedersehen!")
                    break
                elif choice == "1":
                    await self.test_claninfo()
                elif choice == "2":
                    await self.test_aktivitaet()
                elif choice == "3":
                    await self.test_krieginfo("auto")
                elif choice == "4":
                    await self.test_krieginfo("heute")
                elif choice == "5":
                    await self.test_krieginfo("gesamt")
                elif choice == "6":
                    await self.test_spenden()
                elif choice == "7":
                    await self.test_offeneangriffe()
                elif choice == "8":
                    player = input("Spielername (leer für Übersicht): ").strip()
                    await self.test_krieghistorie(player if player else None)
                elif choice == "9":
                    await self.test_inaktiv("gesamt")
                elif choice == "10":
                    await self.test_inaktiv("spenden")
                elif choice == "11":
                    await self.test_inaktiv("kriegsangriffe")
                elif choice == "12":
                    await self.test_spion()
                elif choice == "13":
                    await self.test_details()
                elif choice == "14":
                    self.test_version()
                elif choice == "15":
                    self.test_help()
                else:
                    print("❌ Ungültige Eingabe! Bitte wählen Sie 0-15.")
                
                input("\nDrücken Sie Enter um fortzufahren...")
                
            except KeyboardInterrupt:
                print("\n👋 Auf Wiedersehen!")
                break
            except Exception as e:
                print(f"❌ Unerwarteter Fehler: {e}")
                input("Drücken Sie Enter um fortzufahren...")

async def main():
    """Hauptfunktion."""
    cli = TerminalTestCLI()
    await cli.run()

if __name__ == "__main__":
    asyncio.run(main())