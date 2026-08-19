"""Niche profiles and notice filtering/scoring.

A profile defines one sellable niche digest: NAICS prefixes, optional PSC
prefixes, keywords, states, set-aside preferences, notice types. Profiles are
plain JSON files in 04_build/profiles/ so the operator (agent) can mint new
niches without code changes.

Scoring is deterministic (no model judgment in the money path):
  +3 NAICS exact match, +2 NAICS prefix match
  +2 keyword in title, +1 keyword in description
  +2 preferred set-aside
  +1 deadline 7-30 days out (biddable window), -2 deadline passed/missing for
     solicitation types
  +1 preferred state (or profile has no state restriction)
"""
import json
import os
import re
import sqlite3
from datetime import date, datetime, timedelta

PROFILE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "profiles"))

BIDDABLE_TYPES = (
    "Solicitation", "Combined Synopsis/Solicitation", "Presolicitation",
    "Sources Sought",
)


def load_profile(name):
    path = name if name.endswith(".json") else os.path.join(PROFILE_DIR, name + ".json")
    with open(path, encoding="utf-8") as f:
        p = json.load(f)
    p.setdefault("naics_prefixes", [])
    p.setdefault("psc_prefixes", [])
    p.setdefault("keywords", [])
    p.setdefault("exclude_keywords", [])
    p.setdefault("states", [])            # empty = nationwide
    p.setdefault("set_asides", [])         # substrings, e.g. "Small Business"
    p.setdefault("notice_types", list(BIDDABLE_TYPES))
    p.setdefault("min_score", 3)
    p.setdefault("max_items", 40)
    return p


def list_profiles():
    if not os.path.isdir(PROFILE_DIR):
        return []
    return sorted(f[:-5] for f in os.listdir(PROFILE_DIR) if f.endswith(".json"))


def parse_deadline(s):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(s[:len("2026-01-01T00:00:00-0000") if "T" in s else len(s)], fmt).date()
        except ValueError:
            continue
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return date(int(m[1]), int(m[2]), int(m[3]))
    return None


def score(row, profile, today=None):
    """row: dict of notice fields. Returns (score:int, reasons:list[str])."""
    today = today or date.today()
    pts, why = 0, []
    naics = (row.get("naics") or "").strip()
    for pref in profile["naics_prefixes"]:
        if naics == pref:
            pts += 3; why.append(f"NAICS {naics} exact"); break
        if naics.startswith(pref):
            pts += 2; why.append(f"NAICS {naics}~{pref}"); break
    psc = (row.get("psc") or "").strip()
    for pref in profile["psc_prefixes"]:
        if psc.startswith(pref):
            pts += 2; why.append(f"PSC {psc}"); break
    hay_title = (row.get("title") or "").lower()
    hay_desc = (row.get("description") or "").lower()
    for kw in profile["exclude_keywords"]:
        if kw.lower() in hay_title:
            return (-99, [f"excluded: {kw}"])
    for kw in profile["keywords"]:
        k = kw.lower()
        if k in hay_title:
            pts += 2; why.append(f"title:{kw}")
        elif k in hay_desc:
            pts += 1; why.append(f"desc:{kw}")
    sa = (row.get("set_aside") or "")
    for want in profile["set_asides"]:
        if want.lower() in sa.lower():
            pts += 2; why.append("set-aside match"); break
    dl = parse_deadline(row.get("deadline") or "")
    if dl:
        days = (dl - today).days
        if days < 0:
            return (-99, ["deadline passed"])
        if 7 <= days <= 30:
            pts += 1; why.append(f"{days}d to deadline")
    if profile["states"]:
        st = (row.get("pop_state") or "").strip().upper()
        if st in profile["states"]:
            pts += 1; why.append("state match")
        elif profile.get("states_strict", True) and st:
            return (-99, [f"out of region: {st}"])
        else:
            pts -= 1
    return pts, why


def query_candidates(con, profile, since=None, until=None):
    """Pull candidate rows cheaply via SQL, then score in Python."""
    clauses, params = [], []
    if profile["naics_prefixes"]:
        ors = []
        for pref in profile["naics_prefixes"]:
            ors.append("naics LIKE ?")
            params.append(pref + "%")
        clauses.append("(" + " OR ".join(ors) + ")")
    if profile["notice_types"]:
        q = ",".join("?" * len(profile["notice_types"]))
        clauses.append(f"notice_type IN ({q})")
        params.extend(profile["notice_types"])
    if since:
        clauses.append("first_seen >= ?")
        params.append(since)
    if until:
        clauses.append("first_seen <= ?")
        params.append(until)
    where = " AND ".join(clauses) or "1=1"
    cur = con.execute(f"SELECT * FROM notices WHERE {where}", params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def dedupe(rows):
    """Amendments repost the same solicitation under new NoticeIds. Keep one
    row per (solicitation_no or title+agency) key, preferring latest posted."""
    best = {}
    for r in rows:
        key = (r.get("solicitation_no") or "").strip().lower() \
            or ((r.get("title") or "").strip().lower(),
                (r.get("agency") or "").strip().lower())
        cur = best.get(key)
        if cur is None or (r.get("posted") or "") > (cur.get("posted") or ""):
            best[key] = r
    return list(best.values())


def select_for_digest(con, profile, since=None, today=None):
    rows = dedupe(query_candidates(con, profile, since=since))
    scored = []
    for r in rows:
        pts, why = score(r, profile, today=today)
        if pts >= profile["min_score"]:
            r["_score"], r["_why"] = pts, why
            scored.append(r)
    scored.sort(key=lambda r: (-r["_score"], r.get("deadline") or "9999"))
    return scored[: profile["max_items"]]
