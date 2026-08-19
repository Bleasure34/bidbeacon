"""Publish step of the daily cycle: radars, landing pages, search pages, sitemap.

Runs after engine.runner. Safe to run locally (preview mode) or in CI (live).
Sends the daily digest through the email provider only when both an API key
and a live config are present; otherwise it writes to the local outbox.
"""
import glob
import os
import sys
from datetime import date

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from engine import config, filters, ingest, recompete
from engine.digest import OUT_DIR
from engine.landing import build_landing
from engine.pages import build_site, write_cname, write_sitemap


def main():
    day = date.today().isoformat()
    cfg = config.load()
    con = ingest.ensure_db()
    all_pages = []

    for name in filters.list_profiles():
        prof = filters.load_profile(name)
        naics = [p for p in prof["naics_prefixes"] if len(p) == 6]
        radar_rows = []
        if naics:
            try:
                raw = recompete.fetch_awards(
                    naics, states=prof.get("states") or None, max_pages=8)
                radar_rows, dropped = recompete.expiring_window(
                    raw, min_value=prof.get("radar_min_value", 25000),
                    keywords=prof.get("keywords"),
                    max_items=prof.get("radar_max_items", 120))
                md = recompete.render_markdown(prof, radar_rows, day)
                if dropped:
                    md += f"\n\n_{dropped} additional smaller expirations not shown._"
                out_dir = os.path.join(OUT_DIR, name)
                os.makedirs(out_dir, exist_ok=True)
                with open(os.path.join(out_dir, f"radar-{day}.md"), "w",
                          encoding="utf-8") as f:
                    f.write(md)
                # keep the last 14 radars, drop older ones
                old = sorted(glob.glob(os.path.join(out_dir, "radar-*.md")))[:-14]
                for p in old:
                    os.remove(p)
            except Exception as e:                      # a niche must not kill the run
                print(f"[warn] radar failed for {name}: {type(e).__name__}: {e}")

        build_landing(con, name, day=day, radar_rows=radar_rows)
        all_pages.extend(build_site(name, radar_rows, day=day))
        print(f"[ok] {name}: {len(radar_rows)} expiring contracts")

    write_sitemap(all_pages, day=day)
    cname = write_cname(cfg)
    print(f"[ok] {len(all_pages)} search pages, sitemap written "
          f"({'LIVE' if config.is_live(cfg) else 'PREVIEW'} mode)"
          + (f"; CNAME -> {open(cname).read().strip()}" if cname else ""))


if __name__ == "__main__":
    main()
