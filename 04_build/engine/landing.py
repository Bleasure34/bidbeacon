"""Generate a static, self-contained landing page per niche profile.

Local artifact until hosting gate is approved. Honest positioning only:
public-data source named, no fabricated testimonials/counts (charter §3).
CTA is configurable; default is a mailto placeholder until payment (G-1) and
hosting (G-4) gates are satisfied.
"""
import html
import os
from datetime import date

from . import config, filters, ingest
from .digest import OUT_DIR, _fmt_deadline, _link

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
 :root{{--ink:#16213a;--mut:#5b6474;--brand:#1f5eff;--bg:#fafbfd;--line:#e4e8ef}}
 *{{box-sizing:border-box}} body{{font-family:Segoe UI,Arial,sans-serif;color:var(--ink);
 background:var(--bg);margin:0;line-height:1.55}}
 .wrap{{max-width:760px;margin:0 auto;padding:40px 20px}}
 h1{{font-size:30px;line-height:1.2;margin:0 0 10px}}
 .sub{{font-size:17px;color:var(--mut);margin-bottom:26px}}
 .cta{{display:inline-block;background:var(--brand);color:#fff;text-decoration:none;
 padding:12px 22px;border-radius:8px;font-weight:600}}
 .cta.secondary{{background:#eef2fb;color:var(--brand)}}
 .band{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:20px 24px;margin:26px 0}}
 .item{{border-bottom:1px solid var(--line);padding:12px 0}} .item:last-child{{border:none}}
 .item h3{{font-size:15px;margin:0 0 4px}}
 .meta{{font-size:13px;color:var(--mut)}}
 .price{{font-size:34px;font-weight:700}}
 .fine{{font-size:12px;color:var(--mut);margin-top:30px}}
 ul{{padding-left:20px}} li{{margin:6px 0}}
</style></head><body><div class="wrap">
{preview_banner}
<h1>{headline}</h1>
<div class="sub">{subhead}</div>
<a class="cta" href="{cta_href}">{cta_label}</a>

<div class="band">
<h2>What you get every morning</h2>
<ul>
<li>Every new opportunity in your trade posted to SAM.gov in the last day — filtered to your NAICS codes{region_phrase}</li>
<li>Set-aside flags (Small Business, SDVOSB, 8(a), HUBZone, WOSB) so you see the contracts you can actually win</li>
<li>Response deadlines up front — no expired notices, no duplicates</li>
<li>One email. No portal to log into. Unsubscribe anytime.</li>
</ul>
</div>

<div class="band">
<h2>Today's sample — {day}</h2>
{sample_items}
<div class="meta" style="margin-top:10px">…plus {more_count} more in today's full digest.</div>
</div>

<div class="band">
<h2>Paid tier: Recompete Radar</h2>
<p class="meta">The free digest shows what posted yesterday. The Radar shows
what's coming: <b>every contract in your trade ending in the next 12
months</b> — with the incumbent's name, the award value, and the buying
agency. When a contract ends, the work gets re-competed. Incumbents win most
recompetes against nobody; they lose them to the contractor who showed up
prepared.</p>
{radar_items}
</div>

<div class="band">
<h2>Pricing</h2>
<table style="width:100%;border-collapse:collapse">
<tr>
<td style="vertical-align:top;padding-right:18px;width:50%">
  <div class="price">$0</div>
  <div class="meta"><b>Daily digest</b> — every new opportunity in your
  trade, filtered. No card, no trial clock, unsubscribe anytime.</div>
</td>
<td style="vertical-align:top;width:50%">
  <div class="price">${price}/mo</div>
  <div class="meta"><b>Recompete Radar</b> — the 12-month expiration
  pipeline with incumbents and values, updated weekly, plus the daily
  digest. ${price_annual}/yr paid annually. Cancel anytime; no-questions
  refunds.</div>
</td>
</tr>
</table>
<p><a class="cta" href="{checkout_href}">{checkout_label}</a>
&nbsp;<a class="cta secondary" href="{cta_href}">{cta_label}</a></p>
</div>

<div class="fine">Data source: SAM.gov public contract-opportunity data (public
domain, refreshed daily). {brand} is an independent alerting service and is not
affiliated with any government agency. Listings are provided for information
only and are not bidding advice.{identity_line}</div>
</div></body></html>"""

ITEM = """<div class="item"><h3><a href="{url}">{title}</a></h3>
<div class="meta">{agency} · NAICS {naics} · {sa} · Respond by {deadline}</div></div>"""

RADAR_ITEM = """<div class="item"><h3>{desc}</h3>
<div class="meta">Ends <b>{end}</b> ({days} days) · Incumbent: <b>{incumbent}</b>
 · {value} · {agency} · {state}</div></div>"""


def render_radar_items(radar_rows, limit=4):
    if not radar_rows:
        return "<div class='meta'>Sample available on request.</div>"
    out = []
    for r in radar_rows[:limit]:
        amt = r.get("Award Amount")
        out.append(RADAR_ITEM.format(
            desc=html.escape((r.get("Description") or "(no description)").strip()[:100].title()),
            end=html.escape(str(r.get("End Date"))),
            days=r.get("_days_left", "?"),
            incumbent=html.escape(r.get("Recipient Name") or "?"),
            value=(f"${amt:,.0f}" if isinstance(amt, (int, float)) else "n/a"),
            agency=html.escape(r.get("Awarding Agency") or "?"),
            state=html.escape(r.get("Place of Performance State Code") or "?"),
        ))
    return "\n".join(out)


PREVIEW_BANNER = """<div style="background:#fff4d6;border:1px solid #e8cf8a;
border-radius:8px;padding:10px 14px;margin-bottom:20px;font-size:13px;color:#6b5410">
<b>Preview build.</b> This page is not live: sign-up and checkout are switched
off until the site is deployed and configured. Nothing here collects data.</div>"""


def render_landing(profile, rows, day, brand=None, radar_rows=None, cfg=None):
    cfg = cfg or config.load()
    brand = brand or cfg.get("brand") or "BidBeacon"
    live = config.is_live(cfg)
    name = profile.get("display_name", "Federal Bid Alerts")
    states = profile.get("states") or []
    region_phrase = f" and your states ({', '.join(states)})" if states else ", nationwide"
    sample = rows[:5]
    items = "\n".join(ITEM.format(
        url=html.escape(_link(r)),
        title=html.escape((r.get("title") or "").strip()[:110]),
        agency=html.escape(r.get("agency") or "?"),
        naics=html.escape(r.get("naics") or "?"),
        sa=html.escape((r.get("set_aside") or "open competition").replace(" Set Aside - Total", "")),
        deadline=html.escape(_fmt_deadline(r.get("deadline"))),
    ) for r in sample) or "<div class='meta'>No qualifying new items today.</div>"
    identity = ""
    if live:
        who = cfg.get("operator_name") or ""
        mail = cfg.get("support_email") or ""
        bits = [b for b in (who, mail, cfg.get("postal_line") or "") if b]
        if bits:
            identity = " Operated by " + " · ".join(html.escape(b) for b in bits) + "."

    return PAGE.format(
        title=html.escape(f"{name} — {brand}"),
        preview_banner="" if live else PREVIEW_BANNER,
        headline=html.escape(name),
        subhead=html.escape(profile.get(
            "subhead",
            "Stop refreshing SAM.gov. Get every new federal opportunity in your "
            "trade, filtered and delivered by 7am.")),
        cta_href=html.escape(cfg.get("signup_url") or "#"),
        cta_label=html.escape("Get the free digest" if live else "Sign-up opens at launch"),
        identity_line=identity,
        # Never expose a live checkout before delivery works: taking $29 for a
        # digest we cannot yet send is the one failure with a real victim.
        checkout_href=html.escape(
            cfg.get("checkout_url_monthly") if (live and config.can_charge(cfg)) else "#"),
        checkout_label=html.escape(
            "Subscribe to the Radar" if (live and config.can_charge(cfg))
            else "Radar opens at launch"),
        region_phrase=html.escape(region_phrase),
        day=day, sample_items=items,
        more_count=max(0, len(rows) - len(sample)),
        radar_items=render_radar_items(radar_rows or []),
        price=html.escape(str(profile.get("price_monthly", 29))),
        price_annual=html.escape(str(profile.get("price_annual", 199))),
        brand=html.escape(brand),
    )


def build_landing(con, profile_name, since=None, day=None, radar_rows=None):
    day = day or date.today().isoformat()
    profile = filters.load_profile(profile_name)
    rows = filters.select_for_digest(con, profile, since=since)
    out_dir = os.path.join(OUT_DIR, profile_name)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "landing.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(render_landing(profile, rows, day, radar_rows=radar_rows))
    return path


if __name__ == "__main__":
    import sys
    from . import recompete
    con = ingest.ensure_db()
    prof = filters.load_profile(sys.argv[1])
    naics = [p for p in prof["naics_prefixes"] if len(p) == 6]
    radar_rows = []
    if naics:
        raw = recompete.fetch_awards(naics, states=prof.get("states") or None,
                                     max_pages=4)
        radar_rows, _ = recompete.expiring_window(
            raw, min_value=prof.get("radar_min_value", 25000),
            keywords=prof.get("keywords"))
    print(build_landing(con, sys.argv[1],
                        since=sys.argv[2] if len(sys.argv) > 2 else None,
                        radar_rows=radar_rows))
