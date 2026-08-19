"""Recompete Radar: contracts in a niche expiring soon (the PAID deliverable).

Joins the free keyless USAspending awards API to a profile's niche: every
active contract in the profile's NAICS codes (optionally states) whose period
of performance ends within the horizon — with incumbent, value, agency, and
time-to-expiry. This is the intelligence SAM.gov's free alerts cannot send.

Deterministic; no model judgment in the money path.
"""
import html
import os
import time
from datetime import date, timedelta

import requests

from . import filters
from .digest import OUT_DIR

API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
UA = {"User-Agent": "bidbeacon/0.1", "Content-Type": "application/json"}
FIELDS = ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency",
          "Awarding Sub Agency", "Start Date", "End Date", "Description",
          "Place of Performance State Code"]


def parse_date(s):
    try:
        y, m, d = str(s).split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def fetch_awards(naics_codes, states=None, lookback_years=5, max_pages=8,
                 page_size=100, pause=1.0):
    """Pull recent awards for the niche; caller filters by expiry window."""
    start = (date.today() - timedelta(days=365 * lookback_years)).isoformat()
    fl = {
        "time_period": [{"start_date": start, "end_date": date.today().isoformat()}],
        "award_type_codes": ["A", "B", "C", "D"],
        "naics_codes": [c for c in naics_codes if len(c) == 6],
    }
    if states:
        fl["place_of_performance_locations"] = [
            {"country": "USA", "state": s} for s in states]
    rows = []
    for page in range(1, max_pages + 1):
        r = requests.post(API, json={
            "filters": fl, "fields": FIELDS,
            "sort": "End Date", "order": "desc",
            "limit": page_size, "page": page,
        }, headers=UA, timeout=60)
        r.raise_for_status()
        d = r.json()
        batch = d.get("results", [])
        rows.extend(batch)
        # once a whole page's end dates are in the past, later pages are too
        ends = [parse_date(x.get("End Date")) for x in batch]
        ends = [e for e in ends if e]
        if ends and max(ends) < date.today():
            break
        if not d.get("page_metadata", {}).get("hasNext"):
            break
        time.sleep(pause)
    return rows


def expiring_window(rows, months_ahead=12, today=None, min_value=0,
                    keywords=None, max_items=None):
    """Filter to the expiry window; optionally require min award value and a
    niche-keyword hit in the description (cuts one-off purchase-order noise —
    a $4k boiler-valve repair is not a recompete opportunity)."""
    today = today or date.today()
    horizon = today + timedelta(days=int(30.44 * months_ahead))
    kws = [k.lower() for k in (keywords or [])]
    out, seen = [], set()
    for x in rows:
        end = parse_date(x.get("End Date"))
        if not end or not (today <= end <= horizon):
            continue
        aid = (x.get("Award ID") or "").strip()
        if aid and aid in seen:
            continue
        amt = x.get("Award Amount")
        if min_value and not (isinstance(amt, (int, float)) and amt >= min_value):
            continue
        if kws:
            desc = (x.get("Description") or "").lower()
            if not any(k in desc for k in kws):
                continue
        seen.add(aid)
        x["_end"] = end
        x["_days_left"] = (end - today).days
        out.append(x)
    out.sort(key=lambda x: x["_end"])
    dropped = 0
    if max_items and len(out) > max_items:
        dropped = len(out) - max_items
        out = out[:max_items]
    return out, dropped


def bucket(days_left):
    if days_left <= 92:
        return "Next 90 days"
    if days_left <= 183:
        return "3-6 months out"
    return "6-12 months out"


def render_markdown(profile, rows, day):
    name = profile.get("display_name", "Recompete Radar")
    lines = [f"# Recompete Radar — {name}", "",
             f"Contracts in your niche ending soon. Report date: {day}.",
             "When a contract ends, the work gets re-competed — the incumbent"
             " is named below, and the agency's need does not go away.", ""]
    if not rows:
        lines.append("_No qualifying expirations in the window._")
    current = None
    for r in rows:
        b = bucket(r["_days_left"])
        if b != current:
            lines += [f"## {b}", ""]
            current = b
        amt = r.get("Award Amount")
        amt_s = f"${amt:,.0f}" if isinstance(amt, (int, float)) else "n/a"
        lines += [
            f"### {(r.get('Description') or '(no description)').strip()[:110]}",
            f"- **Ends:** {r.get('End Date')} ({r['_days_left']} days)",
            f"- **Incumbent:** {r.get('Recipient Name','?')}",
            f"- **Value:** {amt_s} · **Agency:** {r.get('Awarding Agency','?')}"
            f" / {r.get('Awarding Sub Agency','')}",
            f"- **State:** {r.get('Place of Performance State Code','?')}"
            f" · **Award ID:** {r.get('Award ID','?')}",
            "",
        ]
    lines += ["---",
              "Source: USAspending.gov public award data (public domain)."
              " Expiration = current period-of-performance end date; options"
              " may extend some awards. Not bidding advice."]
    return "\n".join(lines)


def build_radar(profile_name, months_ahead=12, max_pages=15, day=None):
    day = day or date.today().isoformat()
    profile = filters.load_profile(profile_name)
    naics = [p for p in profile["naics_prefixes"] if len(p) == 6]
    if not naics:
        raise ValueError("profile needs 6-digit NAICS codes for radar")
    rows = fetch_awards(naics, states=profile.get("states") or None,
                        max_pages=max_pages)
    exp, dropped = expiring_window(
        rows, months_ahead=months_ahead,
        min_value=profile.get("radar_min_value", 25000),
        keywords=profile.get("keywords") if profile.get("radar_require_keyword", True) else None,
        max_items=profile.get("radar_max_items", 120))
    out_dir = os.path.join(OUT_DIR, profile_name)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"radar-{day}.md")
    md = render_markdown(profile, exp, day)
    if dropped:
        md += f"\n\n_{dropped} additional smaller expirations not shown._"
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    return path, len(exp)


if __name__ == "__main__":
    import sys
    p, n = build_radar(sys.argv[1])
    print(f"{n} expiring contracts -> {p}")
