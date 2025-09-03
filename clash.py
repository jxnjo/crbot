import os
import time
import httpx
from typing import Dict, Any, List, Tuple
from datetime import datetime, timezone

# zoneinfo + Fallback
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except Exception:
    ZoneInfo = None
    class ZoneInfoNotFoundError(Exception): pass  # type: ignore[misc]

def get_local_tz():
    name = os.getenv("BOT_TZ", "Europe/Zurich")
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return timezone.utc

LOCAL_TZ = get_local_tz()

class ClashClient:
    BASE = "https://api.clashroyale.com/v1"

    def __init__(self, token: str, clan_tag: str, timeout: int = 15):
        self.token = token
        self.clan_tag = clan_tag.lstrip("#").upper()
        self.timeout = timeout
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def _clan_path(self, suffix: str = "") -> str:
        tag = f"%23{self.clan_tag}"
        return f"{self.BASE}/clans/{tag}{suffix}"

    async def _get(self, url: str, cache_bust: bool = False) -> Dict[str, Any]:
        headers = {
            **self.headers,
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
        }
        params = {"ts": int(time.time() * 1000)} if cache_bust else None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, headers=headers, params=params)
            r.raise_for_status()
            return r.json()

    # --- API calls ---
    async def get_clan(self) -> Dict[str, Any]:
        return await self._get(self._clan_path(""), cache_bust=False)

    async def get_current_river(self, force: bool = True) -> Dict[str, Any]:
        return await self._get(self._clan_path("/currentriverrace"), cache_bust=True or force)

    async def get_members(self) -> Dict[str, Any]:
        return await self._get(self._clan_path("/members"), cache_bust=False)

    async def get_river_log(self, limit: int = 50) -> Dict[str, Any]:
        """
        Historie vergangener River Races. limit=Anzahl Einträge (Wochen/Abschnitte).
        """
        url = self._clan_path("/riverracelog")
        headers = {
            **self.headers,
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
        }
        params = {"limit": limit, "ts": int(time.time() * 1000)}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            r = await client.get(url, headers=headers, params=params)
            r.raise_for_status()
            return r.json()

    # ---------- Fresh-Strategy für /currentriverrace ----------
    async def get_current_river_fresh(self, attempts: int = 2, max_decks: int = 4) -> Dict[str, Any]:
        rr = await self.get_current_river(force=True)
        if attempts <= 1:
            return rr
        if self._looks_stale(rr, max_decks=max_decks):
            rr = await self.get_current_river(force=True)
            if attempts >= 3 and self._looks_stale(rr, max_decks=max_decks):
                rr = await self.get_current_river(force=True)
        return rr

    # --------- Heuristik: ist die Liste vermutlich "alt"? ----------
    def _looks_stale(self, rr: Dict[str, Any], max_decks: int = 4) -> bool:
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

# ---------- Helpers & Formatters ----------
def parse_sc_time(s: str):
    if not s:
        return None
    # Supercell Zeitformat: 20200101T000000.000Z
    for fmt in ("%Y%m%dT%H%M%S.%fZ", "%Y%m%dT%H%M%SZ"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except Exception:
            pass
    return None

def ago_str(dt):
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

def fmt_clan(c: Dict[str, Any], fallback_tag: str) -> str:
    name = c.get("name", "Unbekannt")
    tag = c.get("tag", f"#{fallback_tag}")
    members = c.get("members", "?")
    score = c.get("clanScore", "?")
    req = c.get("requiredTrophies", "?")
    desc = (c.get("description") or "").strip()
    if len(desc) > 400:
        desc = desc[:400] + "…"
    return (f"<b>{name}</b> ({tag})\n"
            f"👥 Mitglieder: <b>{members}/50</b>\n"
            f"🏆 Clan-Trophäen: <b>{score}</b>\n"
            f"🔑 Mindest-Trophäen: <b>{req}</b>\n—\n{desc}")

def fmt_open_decks_overview(rr: Dict[str, Any], my_tag_nohash: str, max_decks: int = 4) -> str:
    """
    Übersicht: eigener Clan mit allen Mitgliedern (offene Decks), Gegner kompakt (noch X/Y offen).
    """
    my_tag = my_tag_nohash.upper().lstrip("#")

    # --- eigenen Clan robust finden ---
    my = rr.get("clan") or {}
    if (my.get("tag") or "").upper().lstrip("#") != my_tag:
        for c in (rr.get("clans") or []):
            if (c.get("tag") or "").upper().lstrip("#") == my_tag:
                my = c
                break

    my_name = my.get("name", "Unser Clan")
    participants = my.get("participants") or []

    # --- Mitgliederliste bauen ---
    rows: List[Tuple[int, int, str]] = []  # (remaining, used_today, name)
    for p in participants:
        name = p.get("name", "Unbekannt")
        used_today = int(p.get("decksUsedToday") or 0)
        remaining = max(max_decks - used_today, 0)
        rows.append((remaining, used_today, name))

    rows_open  = sorted([r for r in rows if r[0] > 0], key=lambda x: (-x[0], x[1], x[2].lower()))
    rows_done  = sorted([r for r in rows if r[0] == 0], key=lambda x: x[2].lower())
    ordered    = rows_open + rows_done

    lines: List[str] = []
    lines.append(f"📋 {my_name} – Offene Angriffe (heute)\n")

    for i, (rem, used, name) in enumerate(ordered, start=1):
        done = " ✅" if rem == 0 and used >= max_decks else ""
        lines.append(f"{i:>2}. {name} — {rem} offen ({used}/{max_decks}){done}")

    total_remaining = sum(rem for rem, _, _ in rows)

    # --- Gegner kompakt ---
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

    return "\n".join(lines)[:4096]

# ---- River-Race Scoreboard (Mein Clan vs. Gegner) ----
def fmt_river_scoreboard(rr: dict, my_tag_nohash: str, mode: str = "auto") -> str:
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
        name   = c.get("name") or "Unbekannt"
        fame   = int(c.get("fame") or c.get("points") or 0)
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

    return "\n".join(lines)[:4096]

def fmt_donations_leaderboard(members_payload: dict, limit: int = 10, include_received: bool = False) -> str:
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
    return "\n".join(lines)[:4096]

def fmt_activity_list(members_payload: Dict[str, Any]) -> str:
    """
    Listet alle Clan-Mitglieder sortiert: oben am längsten offline, unten: zuletzt online.
    Nutzt 'lastSeen' aus /v1/clans/%23TAG/members.
    """
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
    return "\n".join(lines)[:4096]

# ---------- Kriegshistorie: Aggregation & Format ----------
def _aggregate_war_history(rlog: Dict[str, Any], my_tag_nohash: str):
    """
    Aggregiert alle Teilnehmer unseres Clans über das RiverRace-Log.
    Rückgabe: dict[tag] = {name, fame, repair, decks, boats, wars, first_seen (dt), last_seen (dt)}
    """
    my_tag = my_tag_nohash.upper().lstrip("#")
    items = rlog.get("items") or []
    acc: Dict[str, Dict[str, Any]] = {}

    for it in items:
        # Zeitstempel der Woche/Section (best effort)
        at = parse_sc_time(it.get("createdDate") or it.get("endTime") or it.get("finishedTime") or it.get("updatedTime"))

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
                entry["wars"]  += 1
                if at:
                    if not entry["first_seen"] or (entry["first_seen"] and at < entry["first_seen"]):
                        entry["first_seen"] = at
                    if not entry["last_seen"] or (entry["last_seen"] and at > entry["last_seen"]):
                        entry["last_seen"] = at
    return acc

def _fmt_date(dt: datetime) -> str:
    if not dt:
        return "unbekannt"
    try:
        return dt.astimezone(LOCAL_TZ).strftime("%d.%m.%Y")
    except Exception:
        return dt.strftime("%d.%m.%Y")

def fmt_war_history_summary(rlog: Dict[str, Any], my_tag_nohash: str) -> str:
    acc = _aggregate_war_history(rlog, my_tag_nohash)
    if not acc:
        return "Keine Kriegshistorie verfügbar."

    rows = []
    for tag, e in acc.items():
        total_pts = e["fame"] + e["repair"]
        rows.append((
            -total_pts, - (e["decks"] + e["boats"]), e["name"].lower(),  # Sortierschlüssel
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
    return "\n".join(lines)[:4096]

def fmt_war_history_player(rlog: Dict[str, Any], my_tag_nohash: str, query: str) -> str:
    acc = _aggregate_war_history(rlog, my_tag_nohash)
    if not acc:
        return "Keine Kriegshistorie verfügbar."

    q = query.strip().lower()
    # Erst exakte Namens-Treffer, dann enthält, dann Tag-Match
    exact = [(t,e) for t,e in acc.items() if e["name"].lower() == q]
    part  = [(t,e) for t,e in acc.items() if q in e["name"].lower()]
    tagm  = [(t,e) for t,e in acc.items() if q.replace("#","") == t.lower()]

    cand = exact or part or tagm
    if not cand:
        # kleine Vorschlagsliste
        suggestions = ", ".join(sorted({e["name"] for _,e in list(acc.items())[:10]}))
        return f"Kein Treffer für „{query}“. Vorschläge: {suggestions}"

    tag, e = cand[0]
    total_pts = e["fame"] + e["repair"]
    since = _fmt_date(e["first_seen"])
    last  = _fmt_date(e["last_seen"]) if e["last_seen"] else "unbekannt"

    lines = [
        f"📖 <b>Kriegshistorie – {e['name']}</b>",
        f"Tag: #{tag}",
        f"Seit: {since}  |  Letzte Teilnahme: {last}",
        f"Teilgenommene Kriege: {e['wars']}",
        f"Punkte gesamt: <b>{total_pts}</b> (Fame: {e['fame']}, Repair: {e['repair']})",
        f"Angriffe gesamt: Decks {e['decks']}  |  Boot {e['boats']}",
    ]
    return "\n".join(lines)[:4096]

def fmt_war_history_player_multi(rlog: Dict[str, Any], my_tag_nohash: str, query: str) -> List[str]:
    acc = _aggregate_war_history(rlog, my_tag_nohash)
    if not acc:
        return ["Keine Kriegshistorie verfügbar."]

    q = query.strip().lower()
    # Erst exakte Namens-Treffer, dann enthält, dann Tag-Match
    exact = [(t,e) for t,e in acc.items() if e["name"].lower() == q]
    part  = [(t,e) for t,e in acc.items() if q in e["name"].lower()]
    tagm  = [(t,e) for t,e in acc.items() if q.replace("#","") == t.lower()]

    cand = exact or part or tagm
    if not cand:
        suggestions = ", ".join(sorted({e["name"] for _,e in list(acc.items())[:10]}))
        return [f"Kein Treffer für „{query}“. Vorschläge: {suggestions}"]

    results = []
    for tag, e in cand:
        total_pts = e["fame"] + e["repair"]
        since = _fmt_date(e["first_seen"])
        last  = _fmt_date(e["last_seen"]) if e["last_seen"] else "unbekannt"
        lines = [
            f"📖 <b>Kriegshistorie – {e['name']}</b>",
            f"Tag: #{tag}",
            f"Seit: {since}  |  Letzte Teilnahme: {last}",
            f"Teilgenommene Kriege: {e['wars']}",
            f"Punkte gesamt: <b>{total_pts}</b> (Fame: {e['fame']}, Repair: {e['repair']})",
            f"Angriffe gesamt: Decks {e['decks']}  |  Boot {e['boats']}",
        ]
        results.append("\n".join(lines)[:4096])
    return results

# ==========================
# Gegner-Analyse / Spionage
# ==========================

# --- Zusätzliche API-Calls für beliebige Clans ---
async def get_river_log_for(client: ClashClient, clan_tag: str, limit: int = 10) -> Dict[str, Any]:
    tag = clan_tag.lstrip("#").upper()
    url = f"{client.BASE}/clans/%23{tag}/riverracelog"
    headers = {
        **client.headers,
        "Cache-Control": "no-store, max-age=0",
        "Pragma": "no-cache",
    }
    params = {"limit": limit, "ts": int(time.time() * 1000)}
    async with httpx.AsyncClient(timeout=client.timeout) as http:
        r = await http.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()

async def get_clan_members_for(client: ClashClient, clan_tag: str) -> Dict[str, Any]:
    tag = clan_tag.lstrip("#").upper()
    url = f"{client.BASE}/clans/%23{tag}/members"
    async with httpx.AsyncClient(timeout=client.timeout) as http:
        r = await http.get(url, headers=client.headers)
        r.raise_for_status()
        return r.json()

# --- interne Helfer ---
def _find_standing_for_tag(item: Dict[str, Any], clan_tag_nohash: str) -> Dict[str, Any] | None:
    tag = clan_tag_nohash.upper().lstrip("#")
    for st in (item.get("standings") or []):
        c = st.get("clan") or {}
        if (c.get("tag") or "").upper().lstrip("#") == tag:
            return st
    return None

def extract_daily_points_from_log(rlog: Dict[str, Any], clan_tag_nohash: str, max_days: int = 20) -> List[int]:
    """
    Versucht, Punkte pro Kriegstag aus dem RiverRace-Log zu extrahieren (ohne Trainingstage).
    Fällt robust zurück (liefert ggf. leere Liste), falls die API-Struktur keine Tagespunkte enthält.
    """
    days: List[int] = []
    for it in (rlog.get("items") or []):
        st = _find_standing_for_tag(it, clan_tag_nohash)
        if not st:
            continue
        # Suche nach möglichen 'period'-Listen (API variiert je Saison)
        for key, val in st.items():
            if isinstance(val, list) and val and isinstance(val[0], dict):
                for d in val:
                    typ = (d.get("type") or d.get("periodType") or "").lower()
                    if "train" in typ:
                        continue
                    pts = int(d.get("points") or d.get("periodPoints") or d.get("fame") or 0)
                    if pts > 0:
                        days.append(pts)
                        if len(days) >= max_days:
                            return days[:max_days]
        if len(days) >= max_days:
            break
    return days[:max_days]

def compute_attack_usage_percent(rlog: Dict[str, Any], clan_tag_nohash: str, default_days: int = 4) -> float:
    """
    Ø pro Kriegstag genutzte Angriffe (über die letzten Logs).
    Prozent = genutzte Decks / (Teilnehmer * 4 * Kriegstage) – pro Log, dann Ø.
    Kriegstage werden aus Perioden (ohne Training) erkannt; falls nicht vorhanden -> default_days.
    """
    percents: List[float] = []
    for it in (rlog.get("items") or []):
        st = _find_standing_for_tag(it, clan_tag_nohash)
        if not st:
            continue
        plist = st.get("clan", {}).get("participants") or st.get("participants") or []
        num = len(plist)
        total_decks = sum(int(p.get("decksUsed") or 0) for p in plist)

        # Kriegstage zählen (ohne Training), falls möglich
        day_count = 0
        for key, val in st.items():
            if isinstance(val, list) and val and isinstance(val[0], dict):
                day_count = sum(
                    1 for d in val
                    if "train" not in ((d.get("type") or d.get("periodType") or "").lower())
                )
                if day_count:
                    break
        if day_count <= 0:
            day_count = default_days

        capacity = num * 4 * day_count
        if capacity > 0:
            percents.append(min(1.0, total_decks / capacity))
    return (sum(percents) / len(percents)) if percents else 0.0

def compare_last_war_vs_current_names(rlog: Dict[str, Any], members_payload: Dict[str, Any], clan_tag_nohash: str):
    """
    Vergleicht Teilnehmer des letzten Kriegs (aus Log) mit aktuellen Clan-Mitgliedern (names only).
    """
    items = rlog.get("items") or []
    if not items:
        return 0, 0, [], []

    st = _find_standing_for_tag(items[0], clan_tag_nohash)
    if not st:
        return 0, 0, [], []

    last_participants = (st.get("clan", {}).get("participants") or st.get("participants") or [])
    last_names = sorted({p.get("name", "?") for p in last_participants})

    cur_items = members_payload.get("items") or []
    cur_names = sorted({m.get("name", "?") for m in cur_items})

    last_set, cur_set = set(last_names), set(cur_names)
    left   = sorted(last_set - cur_set)
    joined = sorted(cur_set - last_set)
    overlap = len(last_set & cur_set)

    return len(last_names), overlap, left, joined

def _bar(p: float, width: int = 10) -> str:
    p = max(0.0, min(1.0, p))
    n = int(round(p * width))
    return "█" * n + "░" * (width - n)

def fmt_spy_report(clan_name: str, clan_tag_nohash: str,
                   daily_points: List[int],
                   usage_avg: float,
                   last_count: int, overlap: int,
                   left: List[str], joined: List[str]) -> str:
    lines: List[str] = []
    lines.append(f"🕵️ <b>Gegner-Spionage</b>")
    lines.append(f"Clan: <b>{clan_name}</b> (#{clan_tag_nohash})")
    lines.append(f"Ø Angriffs-Auslastung/Tag: <b>{int(usage_avg*100)}%</b>  [{_bar(usage_avg)}]")

    if daily_points:
        mx = max(daily_points) or 1
        lines.append("\n📈 Punkte je Kriegstag (zuletzt):")
        # skaliere auf 10 Blöcke je Zeile
        for pts in daily_points[:20]:
            frac = pts / mx
            lines.append(f"<code>{pts:>4} | {_bar(frac)}</code>")
    else:
        lines.append("\n📈 Keine expliziten Tagespunkte im Log gefunden.")

    lines.append(f"\n👥 Teilnehmer im letzten Krieg: <b>{last_count}</b>  |  davon aktuell noch da: <b>{overlap}</b>")
    if left:
        lines.append(f"⬇️ Weg: {', '.join(left[:10])}{' …' if len(left) > 10 else ''}")
    if joined:
        lines.append(f"⬆️ Neu: {', '.join(joined[:10])}{' …' if len(joined) > 10 else ''}")

    return "\n".join(lines)[:4096]
