"""Daily run loop: ingest -> per-profile digest -> QA gate -> run report.

This is the autonomous value-production cycle. It is deterministic and
self-checking; a QA failure quarantines the digest instead of publishing it.

Usage (from 04_build/):
  python -m engine.runner [--download] [--since YYYY-MM-DD]

Exit code 0 = all profiles produced QA-clean digests (or cleanly empty ones);
1 = at least one profile quarantined or errored.
"""
import argparse
import json
import os
import sys
from datetime import date, datetime

from . import filters, ingest, qa, subscribers
from .digest import OUT_DIR, build_digest, render_html, render_markdown


def run(download=False, since=None, day=None):
    day = day or date.today().isoformat()
    since = since or day
    report = {
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "day": day, "since": since, "profiles": {}, "ok": True,
    }
    con = ingest.ensure_db()
    if download:
        ingest.download(quiet=True)
    seen, new = ingest.load_csv(con, today=day)
    report["ingest"] = {"rows": seen, "new": new}

    for name in filters.list_profiles():
        entry = {"status": "ok"}
        try:
            profile = filters.load_profile(name)
            profile["name"] = name
            rows = filters.select_for_digest(con, profile, since=since)
            ok_rows, issues = qa.check_rows(rows, profile)
            html_text = render_html(profile, rows, day)
            ok_html, html_issues = qa.check_html(html_text)
            issues += html_issues
            if ok_rows and ok_html:
                out = os.path.join(OUT_DIR, name, day)
                os.makedirs(out, exist_ok=True)
                md = render_markdown(profile, rows, day)
                with open(os.path.join(out, "digest.md"), "w", encoding="utf-8") as f:
                    f.write(md)
                with open(os.path.join(out, "digest.html"), "w", encoding="utf-8") as f:
                    f.write(html_text)
                scon = subscribers.ensure_db()
                sent = subscribers.deliver_digest(
                    scon, name,
                    f"{profile.get('display_name', name)} — {day}", md)
                scon.close()
                entry.update(items=len(rows), out=out, delivered=sent)
            else:
                qdir = os.path.join(OUT_DIR, name, day + ".quarantine")
                os.makedirs(qdir, exist_ok=True)
                with open(os.path.join(qdir, "issues.json"), "w", encoding="utf-8") as f:
                    json.dump(issues, f, indent=1)
                entry.update(status="quarantined", items=len(rows), issues=issues)
                report["ok"] = False
        except Exception as e:  # a profile failure must not kill the run
            entry.update(status="error", error=f"{type(e).__name__}: {e}")
            report["ok"] = False
        report["profiles"][name] = entry

    os.makedirs(OUT_DIR, exist_ok=True)
    log_path = os.path.join(OUT_DIR, "run_reports.jsonl")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(report) + "\n")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--since", default=None)
    args = ap.parse_args()
    report = run(download=args.download, since=args.since)
    print(json.dumps(report, indent=1))
    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
