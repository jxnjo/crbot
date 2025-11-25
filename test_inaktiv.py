"""
Test-Skript für die /inaktiv Funktion.
Lädt die Beispiel-Daten und testet die Formatierung.
"""
import json
from formatters import fmt_inactive_players

# Lade Beispieldaten
with open('api-examples/members.json', 'r', encoding='utf-8') as f:
    members_data = json.load(f)

with open('api-examples/currentriverrace.json', 'r', encoding='utf-8') as f:
    river_data = json.load(f)

print("=" * 60)
print("TEST: /inaktiv (Standard - Gesamt)")
print("=" * 60)
result = fmt_inactive_players(members_data, river_data, sort_by="gesamt", limit=10)
print(result)
print()

print("=" * 60)
print("TEST: /inaktiv spenden")
print("=" * 60)
result = fmt_inactive_players(members_data, river_data, sort_by="spenden", limit=10)
print(result)
print()

print("=" * 60)
print("TEST: /inaktiv kriegsangriffe")
print("=" * 60)
result = fmt_inactive_players(members_data, river_data, sort_by="kriegsangriffe", limit=10)
print(result)
print()

print("=" * 60)
print("TEST: /inaktiv kriegspunkte")
print("=" * 60)
result = fmt_inactive_players(members_data, river_data, sort_by="kriegspunkte", limit=10)
print(result)
print()

print("=" * 60)
print("TEST: /inaktiv trophäenpfad")
print("=" * 60)
result = fmt_inactive_players(members_data, river_data, sort_by="trophäenpfad", limit=10)
print(result)
