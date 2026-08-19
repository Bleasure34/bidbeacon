"""Prospect discovery: companies that already win contracts in a niche.

Uses the USAspending API (free, keyless, public domain). For a profile's
NAICS codes, pulls recent awardees — these firms demonstrably bid in the
niche and are the natural buyers of a bid-alert digest.

Output: 04_build/out/<profile>/prospects.csv (name, awards, total $, agencies,
states). No personal contact data is collected — company names and public
award facts only; outreach contact discovery is a separate, gated step (G-3).
"""
import csv
import os
import time
from collections import defaultdict

import requests

from . import filters
from .digest import OUT_DIR

API = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
UA = {"User-Agent": "bidbeacon/0.1", "Content-Type": "application/json"}


def fetch_awardees(naics_codes, start_date, end_date, max_pages=4, page_size=100):
    rows = []
    for page in range(1, max_pages + 1):
        payload = {
            "filters": {
                "time_period": [{"start_date": start_date, "end_date": end_date}],
                "award_type_codes": ["A", "B", "C", "D"],
                "naics_codes": [c for c in naics_codes if len(c) == 6],
            },
            "fields": ["Award ID", "Recipient Name", "Award Amount",
                        "Awarding Agency", "Place of Performance State Code"],
            "limit": page_size,
            "page": page,
        }
        r = requests.post(API, json=payload, headers=UA, timeout=60)
        r.raise_for_status()
        d = r.json()
        rows.extend(d.get("results", []))
        if not d.get("page_metadata", {}).get("hasNext"):
            break
        time.sleep(1)  # polite pacing on a free public API
    return rows


def build_prospects(profile_name, start_date, end_date, max_pages=4):
    profile = filters.load_profile(profile_name)
    naics = [p for p in profile["naics_prefixes"] if len(p) == 6]
    if not naics:
        raise ValueError("profile needs at least one 6-digit NAICS for prospect search")
    raw = fetch_awardees(naics, start_date, end_date, max_pages=max_pages)
    agg = defaultdict(lambda: {"awards": 0, "total": 0.0, "agencies": set(), "states": set()})
    for r in raw:
        name = (r.get("Recipient Name") or "").strip()
        if not name:
            continue
        a = agg[name]
        a["awards"] += 1
        a["total"] += float(r.get("Award Amount") or 0)
        if r.get("Awarding Agency"):
            a["agencies"].add(r["Awarding Agency"])
        if r.get("Place of Performance State Code"):
            a["states"].add(r["Place of Performance State Code"])
    out_dir = os.path.join(OUT_DIR, profile_name)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "prospects.csv")
    ranked = sorted(agg.items(), key=lambda kv: -kv[1]["total"])
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["company", "awards_in_period", "total_awarded_usd",
                    "agencies", "states"])
        for name, a in ranked:
            w.writerow([name, a["awards"], round(a["total"], 2),
                        "; ".join(sorted(a["agencies"])), "; ".join(sorted(a["states"]))])
    return out, len(ranked)
