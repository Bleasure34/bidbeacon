"""QA gate: deterministic checks a digest must pass before it ships.

Charter rule: no unverified output reaches a customer. Every check returns
(ok, issues). The runner refuses to publish a digest that fails.
"""
import re
from datetime import date

from .filters import parse_deadline

MAX_ITEMS = 60
URL_RE = re.compile(r"^https://(sam\.gov|www\.sam\.gov)/", re.I)


def check_rows(rows, profile, today=None):
    today = today or date.today()
    issues = []

    # 1. duplicates by solicitation/title
    keys = set()
    for r in rows:
        k = (r.get("solicitation_no") or "").strip().lower() \
            or ((r.get("title") or "").strip().lower(),
                (r.get("agency") or "").strip().lower())
        if k in keys:
            issues.append(f"duplicate item: {r.get('title','?')[:60]}")
        keys.add(k)

    for r in rows:
        t = (r.get("title") or "").strip()
        # 2. expired deadlines must never ship
        dl = parse_deadline(r.get("deadline") or "")
        if dl and dl < today:
            issues.append(f"expired deadline shipped: {t[:60]} ({dl})")
        # 3. links must resolve to sam.gov
        link = (r.get("link") or "").strip()
        if link and not URL_RE.match(link):
            issues.append(f"non-sam.gov link: {link[:80]}")
        # 4. region check for state-restricted profiles
        if profile.get("states") and profile.get("states_strict", True):
            st = (r.get("pop_state") or "").strip().upper()
            if st and st not in profile["states"]:
                issues.append(f"out-of-region item shipped: {t[:60]} ({st})")
        # 5. required fields
        if not t:
            issues.append(f"untitled notice: {r.get('notice_id','?')}")
        if not (r.get("naics") or "").strip():
            issues.append(f"missing NAICS: {t[:60]}")

    # 6. sane volume
    if len(rows) > MAX_ITEMS:
        issues.append(f"digest too large: {len(rows)} items")

    return (not issues), issues


def check_html(html_text):
    issues = []
    if "<script" in html_text.lower():
        issues.append("script tag in rendered HTML")
    if len(html_text) > 400_000:
        issues.append(f"HTML too large: {len(html_text)} bytes")
    return (not issues), issues
