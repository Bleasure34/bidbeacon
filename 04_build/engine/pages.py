"""Programmatic SEO pages: per-niche and per-niche-per-state pages with LIVE data.

Anti-thin-content by construction (the scaled-content-abuse defense): every
page carries real, current records unique to its filter — a table of open
opportunities and a teaser of expiring contracts — not generated prose.

Output: 04_build/site/<profile>/index.html
        04_build/site/<profile>/<state>.html
        04_build/site/sitemap.xml   (BASE_URL placeholder until G-3)
Deploy happens after gate G-3; generation is local and $0.
"""
import html
import os
from datetime import date

from . import filters, ingest
from .digest import _fmt_deadline, _link

SITE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "site"))
BASE_URL = "https://BASE_URL_PLACEHOLDER"  # set at deploy (G-3)

STATE_NAMES = {
    "AL": "Alabama", "FL": "Florida", "GA": "Georgia", "LA": "Louisiana",
    "MS": "Mississippi", "NC": "North Carolina", "SC": "South Carolina",
    "TN": "Tennessee", "TX": "Texas", "VA": "Virginia", "CA": "California",
    "AZ": "Arizona", "CO": "Colorado", "NY": "New York", "PA": "Pennsylvania",
    "OH": "Ohio", "IL": "Illinois", "MI": "Michigan", "WA": "Washington",
    "OR": "Oregon", "NV": "Nevada", "MO": "Missouri", "OK": "Oklahoma",
    "KY": "Kentucky", "IN": "Indiana", "WI": "Wisconsin", "MN": "Minnesota",
    "MD": "Maryland", "NJ": "New Jersey", "MA": "Massachusetts",
}

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{meta_desc}">
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;color:#16213a;background:#fafbfd;margin:0;line-height:1.55}}
 .wrap{{max-width:860px;margin:0 auto;padding:36px 20px}}
 h1{{font-size:26px;margin:0 0 8px}} h2{{font-size:19px;margin-top:34px}}
 .sub{{color:#5b6474;margin-bottom:20px}}
 table{{width:100%;border-collapse:collapse;font-size:14px}}
 th,td{{text-align:left;padding:8px 10px;border-bottom:1px solid #e4e8ef;vertical-align:top}}
 th{{background:#eef2fb;font-size:12px;text-transform:uppercase;letter-spacing:.03em}}
 .scroll{{overflow-x:auto}}
 a{{color:#1f5eff}} .cta{{display:inline-block;background:#1f5eff;color:#fff;text-decoration:none;padding:11px 20px;border-radius:8px;font-weight:600;margin:8px 0}}
 .fine{{font-size:12px;color:#888;margin-top:34px}}
 .nav{{font-size:13px;margin-bottom:18px}} .nav a{{margin-right:10px}}
</style></head><body><div class="wrap">
<div class="nav">{nav}</div>
<h1>{h1}</h1>
<div class="sub">Updated {day} from public SAM.gov and USAspending data. {count_line}</div>

<h2>Open federal opportunities right now</h2>
<div class="scroll"><table>
<tr><th>Opportunity</th><th>Agency</th><th>Set-aside</th><th>Place</th><th>Respond by</th></tr>
{opp_rows}
</table></div>

<h2>Contracts in this niche ending within 12 months</h2>
<p>When a federal contract ends, the work is typically re-competed. Knowing
the incumbent, the value, and the end date months ahead is how challengers
win. A sample from the current pipeline:</p>
<div class="scroll"><table>
<tr><th>Contract</th><th>Incumbent</th><th>Value</th><th>Ends</th></tr>
{radar_rows}
</table></div>
<p><a class="cta" href="{cta_href}">Get the full Recompete Radar</a></p>

<h2>How this works</h2>
<p>{how_text}</p>

<div class="fine">Data: SAM.gov and USAspending.gov (public domain, refreshed
daily). Independent service; not affiliated with any government agency.
Listings are informational, not bidding advice. Contract end dates reflect
current period of performance; options may extend some awards.</div>
</div></body></html>"""


def _opp_row(r):
    return ("<tr><td><a href=\"{u}\">{t}</a></td><td>{a}</td><td>{s}</td>"
            "<td>{p}</td><td>{d}</td></tr>").format(
        u=html.escape(_link(r)),
        t=html.escape((r.get("title") or "").strip()[:90]),
        a=html.escape((r.get("agency") or "?")[:40]),
        s=html.escape((r.get("set_aside") or "open").replace(" Set Aside - Total", "")[:38]),
        p=html.escape(f"{r.get('pop_city','')}, {r.get('pop_state','')}".strip(", ")[:30]),
        d=html.escape(_fmt_deadline(r.get("deadline"))[:16]),
    )


def _radar_row(r):
    amt = r.get("Award Amount")
    return ("<tr><td>{t}</td><td>{i}</td><td>{v}</td><td>{e}</td></tr>").format(
        t=html.escape((r.get("Description") or "(no description)").strip()[:80].title()),
        i=html.escape((r.get("Recipient Name") or "?")[:40]),
        v=(f"${amt:,.0f}" if isinstance(amt, (int, float)) else "n/a"),
        e=html.escape(str(r.get("End Date"))),
    )


def render_page(profile, opp_rows, radar_rows, day, state=None, states_index=None,
                cta_href="#"):
    trade = profile.get("trade_name") or profile.get("display_name", "Federal Contracts")
    loc = STATE_NAMES.get(state, state) if state else "the US"
    h1 = f"{trade}: open bids and expiring contracts in {loc}"
    title = f"{trade} — {loc} federal bids & recompetes"
    meta = (f"Live list of open federal opportunities and contracts expiring "
            f"within 12 months for {trade.lower()} in {loc}. "
            f"Incumbents, values, deadlines. Updated {day}.")
    nav_links = ['<a href="index.html">All states</a>']
    for st in (states_index or []):
        if st != state:
            nav_links.append(f'<a href="{st.lower()}.html">{html.escape(STATE_NAMES.get(st, st))}</a>')
    count_line = (f"{len(opp_rows)} open opportunities and {len(radar_rows)} "
                  f"expiring contracts shown.")
    how = (f"This page tracks two public federal datasets for one niche. New "
           f"opportunities come from SAM.gov's daily public data file. The "
           f"expiring-contract pipeline comes from USAspending award records: "
           f"period-of-performance end dates within the next 12 months, with "
           f"the incumbent and value. The free daily digest emails the first "
           f"table; the paid Recompete Radar delivers the full second one.")
    return PAGE.format(
        title=html.escape(title), meta_desc=html.escape(meta),
        nav=" · ".join(nav_links[:12]), h1=html.escape(h1), day=day,
        count_line=html.escape(count_line),
        opp_rows="\n".join(_opp_row(r) for r in opp_rows) or "<tr><td colspan=5>None currently — check back tomorrow.</td></tr>",
        radar_rows="\n".join(_radar_row(r) for r in radar_rows) or "<tr><td colspan=4>Sample available in the Radar.</td></tr>",
        cta_href=html.escape(cta_href),
        how_text=html.escape(how),
    )


def build_site(profile_name, radar_rows_all, day=None, max_opps=25,
               max_radar_teaser=6, cta_href=None):
    """Generate index + per-state pages for one profile.

    radar_rows_all: pre-fetched expiring-contract rows (from engine.recompete)
    so page generation makes no API calls itself.
    """
    day = day or date.today().isoformat()
    con = ingest.ensure_db()
    profile = filters.load_profile(profile_name)
    rows = filters.select_for_digest(con, profile, since=None)
    states = profile.get("states") or sorted({
        (r.get("pop_state") or "").strip().upper()
        for r in rows if (r.get("pop_state") or "").strip()})[:10]

    out_dir = os.path.join(SITE_DIR, profile_name)
    os.makedirs(out_dir, exist_ok=True)
    pages = []
    # local-preview default; overridden at deploy (G-3)
    cta_href = cta_href or f"../../out/{profile_name}/landing.html"

    # index page (whole region/nation)
    idx = render_page(profile, rows[:max_opps], radar_rows_all[:max_radar_teaser],
                      day, state=None, states_index=states, cta_href=cta_href)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(idx)
    pages.append(f"{profile_name}/index.html")

    for st in states:
        st_opps = [r for r in rows
                   if (r.get("pop_state") or "").strip().upper() == st][:max_opps]
        st_radar = [r for r in radar_rows_all
                    if (r.get("Place of Performance State Code") or "").upper() == st][:max_radar_teaser]
        pg = render_page(profile, st_opps, st_radar, day, state=st,
                         states_index=states, cta_href=cta_href)
        with open(os.path.join(out_dir, f"{st.lower()}.html"), "w", encoding="utf-8") as f:
            f.write(pg)
        pages.append(f"{profile_name}/{st.lower()}.html")
    return pages


def write_cname(cfg=None):
    """GitHub Pages needs a CNAME file in the published output to serve a
    custom domain. Derived from base_url so there is one place to change it.
    Returns the path written, or None when base_url is a *.github.io default."""
    from . import config
    cfg = cfg or config.load()
    base = (cfg.get("base_url") or "").strip()
    if not base:
        return None
    host = base.split("//", 1)[-1].split("/", 1)[0].strip()
    if not host or host.endswith(".github.io"):
        return None
    os.makedirs(SITE_DIR, exist_ok=True)
    path = os.path.join(SITE_DIR, "CNAME")
    with open(path, "w", encoding="utf-8") as f:
        f.write(host + "\n")
    return path


def write_sitemap(all_pages, day=None, base_url=None):
    from . import config
    day = day or date.today().isoformat()
    base = (base_url or config.load().get("base_url") or BASE_URL).rstrip("/")
    items = "\n".join(
        f"<url><loc>{base}/{p}</loc><lastmod>{day}</lastmod></url>"
        for p in all_pages)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f"{items}\n</urlset>")
    os.makedirs(SITE_DIR, exist_ok=True)
    path = os.path.join(SITE_DIR, "sitemap.xml")
    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    return path


if __name__ == "__main__":
    import sys
    from . import recompete
    prof = filters.load_profile(sys.argv[1])
    naics = [p for p in prof["naics_prefixes"] if len(p) == 6]
    raw = recompete.fetch_awards(naics, states=prof.get("states") or None, max_pages=6)
    radar, _ = recompete.expiring_window(
        raw, min_value=prof.get("radar_min_value", 25000), keywords=prof.get("keywords"))
    pages = build_site(sys.argv[1], radar)
    print(f"{len(pages)} pages")
    print(write_sitemap(pages))
