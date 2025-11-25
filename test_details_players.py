#!/usr/bin/env python3
"""
Schnelltest für /details mit verschiedenen Spielern
"""
import asyncio
from test_cli import TerminalTestCLI

async def test_details_players():
    """Testet /details mit verschiedenen Spielern"""
    
    cli = TerminalTestCLI()
    cli.initialize_client()
    
    players = ["JayJay", "sali", "Novo"]
    
    for player in players:
        print(f"\n{'='*60}")
        print(f"TEST: /details {player}")
        print('='*60)
        
        try:
            # Daten laden
            members = await cli.clash.get_members()
            river_race = await cli.clash.get_current_river_fresh()
            river_log = await cli.clash.get_river_log(limit=20)
            
            # Details formatieren
            from formatters import fmt_player_details
            result = fmt_player_details(player, members, river_race, river_log)
            
            # HTML-Tags entfernen für Terminal-Anzeige
            clean_result = result.replace('<b>', '').replace('</b>', '')
            clean_result = clean_result.replace('<code>', '').replace('</code>', '')
            clean_result = clean_result.replace('<i>', '').replace('</i>', '')
            
            print(clean_result)
            
        except Exception as e:
            print(f"❌ Fehler bei {player}: {e}")
    
    print(f"\n{'='*60}")
    print("Tests abgeschlossen!")

if __name__ == "__main__":
    asyncio.run(test_details_players())