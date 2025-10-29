"""
Formatierungs-Funktionen für Clash Royale Bot Nachrichten.
Alle Message-Formatter sind hier zentralisiert.
"""
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
from config import config

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

def parse_sc_time(s: str) -> Optional[datetime]:
    """Parst Supercell Zeitformat."""
    if not s:
        return None
    # Supercell Zeitformat: 20200101T000000.000Z
    for fmt in ("%Y%m%dT%H%M%S.%fZ", "%Y%m%dT%H%M%SZ"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None

def ago_str(dt: Optional[datetime]) -> str:
    """Formatiert einen Zeitstempel als 'vor X' String."""
    if not dt:
        return "unbekannt"
    delta = datetime.now(timezone.utc) - dt
    secs = int(delta.total_seconds())
    if secs < 90: return "vor 1 Min"
    mins = secs // 60
    if mins < 90: return f"vor {mins} Min"
    hrs = secs // 3600
    if hrs < 36: return f"vor {hrs} Std"
    days = secs // 86400
    if days < 14: return f"vor {days} T"
    weeks = secs // 604800
    if weeks < 10: return f"vor {weeks} W"
    return dt.strftime("am %d.%m.%Y")

def _fmt_date(dt: Optional[datetime]) -> str:
    """Formatiert ein Datum in deutschem Format."""
    if not dt:
        return "unbekannt"
    try:
        return dt.astimezone(LOCAL_TZ).strftime("%d.%m.%Y")
    except Exception:
        return dt.strftime("%d.%m.%Y")

def _bar(pct: float, width: int = None) -> str:
    """Erstellt eine Fortschrittsbalken-Darstellung."""
    if width is None:
        width = config.PROGRESS_BAR_WIDTH
    pct = max(0.0, min(1.0, float(pct)))
    filled = int(round(width * pct))
    return "█" * filled + "░" * (width - filled)

def fmt_version(version_dict: dict) -> str:
    """Formatiert Bot-Version-Informationen."""
    short = version_dict["sha"][:7]
    note = f"\n📝 {version_dict['msg']}" if version_dict["msg"] else ""
    return (
        f"🔧 <b>Bot-Version</b>\n"
        f"• Commit: <code>{short}</code> ({version_dict['ref']})\n"
        f"• Autor: {version_dict['author']}\n"
        f"• Build: {version_dict['time']}{note}"
    )

def fmt_startup_message(version_dict: dict) -> str:
    """Formatiert die Bot-Start-Nachricht."""
    short = version_dict["sha"][:7]
    return (
        f"🚀 <b>Drablibe-Bot wurde gestartet und/oder geupdatet!!</b>\n"
        f"• Commit: <code>{short}</code> ({version_dict['ref']})\n"
        f"• Author: {version_dict['author']}\n"
        f"• Build: {version_dict['time']}\n"
        f"{'📝 ' + version_dict['msg'] if version_dict['msg'] else ''}"
    )

def fmt_clan(clan_data: Dict[str, Any], fallback_tag: str) -> str:
    """Formatiert Clan-Informationen."""
    name = clan_data.get("name", "Unbekannt")
    tag = clan_data.get("tag", f"#{fallback_tag}")
    members = clan_data.get("members", "?")
    score = clan_data.get("clanScore", "?")
    req = clan_data.get("requiredTrophies", "?")
    desc = (clan_data.get("description") or "").strip()
    
    if len(desc) > 400:
        desc = desc[:400] + "…"
    
    return (
        f"<b>{name}</b> ({tag})\n"
        f"👥 Mitglieder: <b>{members}/{config.MAX_CLAN_MEMBERS}</b>\n"
        f"🏆 Clan-Trophäen: <b>{score}</b>\n"
        f"🔑 Mindest-Trophäen: <b>{req}</b>\n—\n{desc}"
    )

def fmt_open_decks_overview(rr: Dict[str, Any], my_tag_nohash: str, max_decks: int = None) -> str:
    """Formatiert Übersicht der offenen Angriffe."""
    if max_decks is None:
        max_decks = config.MAX_DECKS_PER_DAY
        
    my_tag = my_tag_nohash.upper().lstrip("#")

    # Eigenen Clan robust finden
    my = rr.get("clan") or {}
    if (my.get("tag") or "").upper().lstrip("#") != my_tag:
        for c in (rr.get("clans") or []):
            if (c.get("tag") or "").upper().lstrip("#") == my_tag:
                my = c
                break

    my_name = my.get("name", "Unser Clan")
    participants = my.get("participants") or []

    # Mitgliederliste bauen
    rows: List[Tuple[int, int, str]] = []
    for p in participants:
        name = p.get("name", "Unbekannt")
        used_today = int(p.get("decksUsedToday") or 0)
        remaining = max(max_decks - used_today, 0)
        rows.append((remaining, used_today, name))

    rows_open = sorted([r for r in rows if r[0] > 0], key=lambda x: (-x[0], x[1], x[2].lower()))
    rows_done = sorted([r for r in rows if r[0] == 0], key=lambda x: x[2].lower())
    ordered = rows_open + rows_done

    lines: List[str] = []
    lines.append(f"📋 {my_name} – Offene Angriffe (heute)\n")

    for i, (rem, used, name) in enumerate(ordered, start=1):
        done = " ✅" if rem == 0 and used >= max_decks else ""
        lines.append(f"{i:>2}. {name} — {rem} offen ({used}/{max_decks}){done}")

    total_remaining = sum(rem for rem, _, _ in rows)

    # Gegner kompakt
    opp_lines: List[str] = []
    for c in (rr.get("clans") or []):
        tag = (c.get("tag") or "").upper().lstrip("#")
        if not tag or tag == my_tag:
            continue
        plist = c.get("participants") or []
        total_slots = len(plist) * max_decks
        open_sum = 0
        for p in plist:
            used_t = int(p.get("decksUsedToday") or 0)
            open_sum += max(max_decks - used_t, 0)
        opp_lines.append(f"• {c.get('name','?')} — noch {open_sum}/{total_slots} offen")

    if opp_lines:
        lines.append("\n🆚 Gegner (heute, kompakt)")
        lines.extend(opp_lines)

    # Zeitstempel
    try:
        ts = datetime.now(LOCAL_TZ).strftime("%H:%M:%S %Z")
    except Exception:
        ts = datetime.utcnow().strftime("%H:%M:%S UTC")

    lines.append(f"\nΣ offen heute: {total_remaining}")
    lines.append(f"🕒 Datenstand: {ts}")

    return "\n".join(lines)[:config.MAX_MESSAGE_LENGTH]

def fmt_river_scoreboard(rr: dict, my_tag_nohash: str, mode: str = "auto") -> str:
    """Formatiert River-Race Scoreboard."""
    my_tag = my_tag_nohash.upper().lstrip("#")
    clans_list = []
    seen = set()

    def add_entry(c: dict):
        if not c:
            return
        tag = (c.get("tag") or "").upper().lstrip("#")
        if not tag or tag in seen:
            return
        seen.add(tag)
        name = c.get("name") or "Unbekannt"
        fame = int(c.get("fame") or c.get("points") or 0)
        period = int(c.get("periodPoints") or 0)
        repair = int(c.get("repairPoints") or 0)
        clans_list.append({"tag": tag, "name": name, "fame": fame, "period": period, "repair": repair})

    add_entry(rr.get("clan"))
    for c in (rr.get("clans") or []):
        add_entry(c)

    if not clans_list:
        return "Keine River-Race-Daten verfügbar."

    my = next((c for c in clans_list if c["tag"] == my_tag), None) or clans_list[0]
    use_period = (mode.lower() == "heute") or (mode.lower() == "auto" and any(c["period"] > 0 for c in clans_list))
    metric = "period" if use_period else "fame"

    clans_list.sort(key=lambda x: (-x[metric], x["name"].lower()))
    my_val = my[metric]

    header = "🏁 <b>River-Race Punkte (heute)</b>\n" if use_period else "🏁 <b>River-Race Punkte (gesamt)</b>\n"
    lines = [header]
    
    for i, c in enumerate(clans_list, start=1):
        val = c[metric]
        delta = val - my_val
        sign = "±" if delta == 0 else ("+" if delta > 0 else "−")
        me_mark = " ⭐" if c["tag"] == my["tag"] else ""
        lines.append(
            f"{i:>2}. {c['name']} (#{c['tag']}) — "
            f"Punkte: <b>{val}</b> | Heute: {c['period']} | Gesamt: {c['fame']} | Δ zu uns: {sign}{abs(delta)}{me_mark}"
        )

    return "\n".join(lines)[:config.MAX_MESSAGE_LENGTH]

def fmt_donations_leaderboard(members_payload: dict, limit: int = None, include_received: bool = False) -> str:
    """Formatiert Spenden-Rangliste."""
    if limit is None:
        limit = config.DEFAULT_DONATIONS_LIMIT
        
    items = members_payload.get("items") or []
    rows = []
    total_donated = 0
    total_received = 0

    for m in items:
        name = m.get("name", "Unbekannt")
        donated = int(m.get("donations") or 0)
        received = int(m.get("donationsReceived") or 0)
        total_donated += donated
        total_received += received
        rows.append((donated, received, name))

    rows.sort(key=lambda x: (-x[0], x[2].lower()))
    if isinstance(limit, int) and limit > 0:
        rows = rows[:limit]

    lines = ["🎁 <b>Spenden-Rangliste</b> (diese Woche)\n"]
    for i, (donated, received, name) in enumerate(rows, start=1):
        extra = f" | erhalten: {received}" if include_received else ""
        lines.append(f"{i:>2}. {name} — gespendet: <b>{donated}</b>{extra}")

    lines.append(f"\nΣ gespendet: {total_donated}" + (f" | Σ erhalten: {total_received}" if include_received else ""))
    return "\n".join(lines)[:config.MAX_MESSAGE_LENGTH]

def fmt_activity_list(members_payload: Dict[str, Any], my_tag_nohash: str = None) -> str:
    """Formatiert Aktivitätsliste."""
    items = members_payload.get("items") or []
    rows = []
    
    for m in items:
        name = m.get("name", "Unbekannt")
        role = m.get("role", "")
        dt = parse_sc_time(m.get("lastSeen"))
        rows.append((dt or datetime.min.replace(tzinfo=timezone.utc), name, role))
    
    rows.sort(key=lambda x: x[0])

    lines = ["📊 Aktivität (oben: am längsten offline, unten: zuletzt online)\n"]
    for i, (dt, name, role) in enumerate(rows, start=1):
        lines.append(f"{i:>2}. {name} ({role}) — {ago_str(dt)}")
    
    return "\n".join(lines)[:config.MAX_MESSAGE_LENGTH]

def fmt_war_history_summary(rlog: Dict[str, Any], my_tag_nohash: str, aggregation_func) -> str:
    """Formatiert Kriegshistorie-Übersicht."""
    acc = aggregation_func(rlog, my_tag_nohash)
    if not acc:
        return "Keine Kriegshistorie verfügbar."

    rows = []
    for tag, e in acc.items():
        total_pts = e["fame"] + e["repair"]
        rows.append((
            -total_pts, -(e["decks"] + e["boats"]), e["name"].lower(),
            e, tag
        ))
    rows.sort()

    lines = ["📚 <b>Kriegshistorie – Übersicht</b>\n"]
    for i, (_, __, ___, e, tag) in enumerate(rows, start=1):
        total_pts = e["fame"] + e["repair"]
        since = _fmt_date(e["first_seen"])
        lines.append(
            f"{i:>2}. {e['name']} (#{tag}) — "
            f"Angriffe: {e['decks']}+{e['boats']} "
            f"| Punkte: <b>{total_pts}</b> (F:{e['fame']} / R:{e['repair']}) "
            f"| Kriege: {e['wars']} | seit {since}"
        )
    
    return "\n".join(lines)[:config.MAX_MESSAGE_LENGTH]

def fmt_war_history_player(rlog: Dict[str, Any], my_tag_nohash: str, query: str, aggregation_func) -> str:
    """Formatiert Kriegshistorie für einen einzelnen Spieler."""
    acc = aggregation_func(rlog, my_tag_nohash)
    if not acc:
        return "Keine Kriegshistorie verfügbar."

    q = query.strip().lower()
    # Erst exakte Namens-Treffer, dann enthält, dann Tag-Match
    exact = [(t, e) for t, e in acc.items() if e["name"].lower() == q]
    part = [(t, e) for t, e in acc.items() if q in e["name"].lower()]
    tagm = [(t, e) for t, e in acc.items() if q.replace("#", "") == t.lower()]

    cand = exact or part or tagm
    if not cand:
        suggestions = ", ".join(sorted({e["name"] for _, e in list(acc.items())[:10]}))
        return f"Kein Treffer für \"{query}\". Vorschläge: {suggestions}"

    tag, e = cand[0]
    total_pts = e["fame"] + e["repair"]
    since = _fmt_date(e["first_seen"])
    last = _fmt_date(e["last_seen"]) if e["last_seen"] else "unbekannt"

    lines = [
        f"📖 <b>Kriegshistorie – {e['name']}</b>",
        f"Tag: #{tag}",
        f"Seit: {since}  |  Letzte Teilnahme: {last}",
        f"Teilgenommene Kriege: {e['wars']}",
        f"Punkte gesamt: <b>{total_pts}</b> (Fame: {e['fame']}, Repair: {e['repair']})",
        f"Angriffe gesamt: Decks {e['decks']}  |  Boot {e['boats']}",
    ]
    
    return "\n".join(lines)[:config.MAX_MESSAGE_LENGTH]

def fmt_war_history_player_multi(rlog: Dict[str, Any], my_tag_nohash: str, query: str, aggregation_func) -> List[str]:
    """Formatiert Kriegshistorie für mehrere Spieler mit gleichem Namen."""
    acc = aggregation_func(rlog, my_tag_nohash)
    if not acc:
        return ["Keine Kriegshistorie verfügbar."]

    q = query.strip().lower()
    exact = [(t, e) for t, e in acc.items() if e["name"].lower() == q]
    part = [(t, e) for t, e in acc.items() if q in e["name"].lower()]
    tagm = [(t, e) for t, e in acc.items() if q.replace("#", "") == t.lower()]

    cand = exact or part or tagm
    if not cand:
        suggestions = ", ".join(sorted({e["name"] for _, e in list(acc.items())[:10]}))
        return [f"Kein Treffer für \"{query}\". Vorschläge: {suggestions}"]

    results = []
    for tag, e in cand:
        total_pts = e["fame"] + e["repair"]
        since = _fmt_date(e["first_seen"])
        last = _fmt_date(e["last_seen"]) if e["last_seen"] else "unbekannt"
        lines = [
            f"📖 <b>Kriegshistorie – {e['name']}</b>",
            f"Tag: #{tag}",
            f"Seit: {since}  |  Letzte Teilnahme: {last}",
            f"Teilgenommene Kriege: {e['wars']}",
            f"Punkte gesamt: <b>{total_pts}</b> (Fame: {e['fame']}, Repair: {e['repair']})",
            f"Angriffe gesamt: Decks {e['decks']}  |  Boot {e['boats']}",
        ]
        results.append("\n".join(lines)[:config.MAX_MESSAGE_LENGTH])
    
    return results

def _format_points_rows(rows: list[dict]) -> str:
    """Formatiert Punktereihen für Spionage-Feature."""
    lines = []
    for i, r in enumerate(rows, start=1):
        d = r.get("created")
        when = d.strftime("%d.%m.") if d else f"S{r.get('season')}/P{r.get('section')}"
        n = int(r.get("participants") or 0)
        used = int(r.get("used_decks") or 0)
        fame = int(r.get("fame_day") or 0)
        pct = (used / float(4 * n)) if n > 0 else 0.0
        lines.append(f"{i:>2}. {when} — Punkte: <b>{fame}</b> | Decks: {used}/{4*n} ({int(round(pct*100))}%)")
    
    return "\n".join(lines) if lines else "—"

