"""Render a niche digest (markdown + self-contained HTML email/page).

Output goes to 04_build/out/<profile>/<date>/digest.{md,html}.
Deterministic rendering — no model calls in the money path.
"""
import html
import os
from datetime import date

from . import filters

OUT_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "out"))

SAM_URL = "https://sam.gov/opp/{nid}/view"


def _link(row):
    return (row.get("link") or "").strip() or SAM_URL.format(nid=row["notice_id"])


def _fmt_deadline(s):
    """'2026-08-31T09:00:00-04:00' -> '2026-08-31 09:00 (UTC-4)'; passthrough otherwise."""
    if not s:
        return "no deadline listed"
    s = s.strip()
    if "T" in s:
        d, _, t = s.partition("T")
        hhmm = t[:5]
        tz = ""
        for sep in ("+", "-"):
            i = t.rfind(sep)
            if i > 4:
                off = t[i:].replace(":", "")
                tz = f" (UTC{sep}{int(off[1:3])})" if len(off) >= 3 else ""
                break
        return f"{d} {hhmm}{tz}"
    return s


def render_markdown(profile, rows, day):
    name = profile.get("display_name", profile.get("name", "digest"))
    lines = [f"# {name} — new federal opportunities, {day}", ""]
    if not rows:
        lines.append("_No qualifying new opportunities today._")
    for r in rows:
        dl = _fmt_deadline(r.get("deadline"))
        sa = r.get("set_aside") or "no set-aside"
        lines += [
            f"## {r.get('title','(untitled)').strip()}",
            f"- **Agency:** {r.get('agency','?')} / {r.get('sub_tier','')}",
            f"- **Type:** {r.get('notice_type','?')} · **NAICS:** {r.get('naics','?')}"
            f" · **Set-aside:** {sa}",
            f"- **Place:** {r.get('pop_city','')}, {r.get('pop_state','')}"
            f" · **Respond by:** {dl}",
            f"- **Link:** {_link(r)}",
            "",
        ]
    lines += ["---",
              "Source: SAM.gov public data (public domain). "
              "This digest lists opportunities; it is not bidding advice."]
    return "\n".join(lines)


HTML_SHELL = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;color:#1a1a2e;background:#f6f7f9;margin:0;padding:24px}}
 .wrap{{max-width:680px;margin:0 auto}}
 .card{{background:#fff;border:1px solid #e3e6ea;border-radius:10px;padding:16px 20px;margin:12px 0}}
 h1{{font-size:20px}} h2{{font-size:15px;margin:0 0 6px}}
 .meta{{font-size:13px;color:#555;line-height:1.5}}
 .badge{{display:inline-block;font-size:11px;background:#eef4ff;color:#2456a6;border-radius:4px;padding:1px 7px;margin-right:6px}}
 a{{color:#2456a6}} .foot{{font-size:11px;color:#888;margin-top:18px}}
</style></head><body><div class="wrap">
<h1>{title}</h1><div class="meta">{count} qualifying new opportunities · {day}</div>
{cards}
<div class="foot">Source: SAM.gov public data (public domain). This digest lists
opportunities; it is not bidding advice.</div>
</div></body></html>"""

CARD = """<div class="card"><h2><a href="{url}">{title}</a></h2>
<div class="meta">
<span class="badge">{ntype}</span><span class="badge">NAICS {naics}</span>{sa_badge}
<br>{agency}{subtier}
<br>Place: {place} &nbsp;·&nbsp; <b>Respond by: {deadline}</b>
</div></div>"""


def render_html(profile, rows, day):
    name = profile.get("display_name", profile.get("name", "digest"))
    cards = []
    for r in rows:
        sa = (r.get("set_aside") or "").strip()
        cards.append(CARD.format(
            url=html.escape(_link(r)),
            title=html.escape((r.get("title") or "(untitled)").strip()),
            ntype=html.escape(r.get("notice_type") or "?"),
            naics=html.escape(r.get("naics") or "?"),
            sa_badge=(f'<span class="badge">{html.escape(sa)}</span>' if sa and sa != "No Set aside used" else ""),
            agency=html.escape(r.get("agency") or "?"),
            subtier=(" / " + html.escape(r["sub_tier"])) if r.get("sub_tier") else "",
            place=html.escape(f"{r.get('pop_city','')}, {r.get('pop_state','')}".strip(", ")),
            deadline=html.escape(_fmt_deadline(r.get("deadline"))),
        ))
    return HTML_SHELL.format(title=html.escape(f"{name} — {day}"),
                             count=len(rows), day=day, cards="\n".join(cards))


def build_digest(con, profile_name, since=None, day=None):
    day = day or date.today().isoformat()
    profile = filters.load_profile(profile_name)
    profile["name"] = profile_name
    rows = filters.select_for_digest(con, profile, since=since)
    out = os.path.join(OUT_DIR, profile_name, day)
    os.makedirs(out, exist_ok=True)
    md = render_markdown(profile, rows, day)
    ht = render_html(profile, rows, day)
    with open(os.path.join(out, "digest.md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(out, "digest.html"), "w", encoding="utf-8") as f:
        f.write(ht)
    return out, len(rows)
