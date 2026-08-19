"""BidBeacon CLI.

Usage (from 04_build/):
  python -m engine.cli ingest [--download]
  python -m engine.cli digest <profile> [--since YYYY-MM-DD]
  python -m engine.cli prospects <profile> [--months 12] [--pages 4]
  python -m engine.cli run <profile>        # ingest (no download) + digest
  python -m engine.cli profiles
"""
import argparse
from datetime import date, timedelta

from . import ingest as ingest_mod
from . import filters
from .digest import build_digest
from .prospects import build_prospects


def main():
    ap = argparse.ArgumentParser(prog="bidbeacon")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ing = sub.add_parser("ingest")
    p_ing.add_argument("--download", action="store_true")

    p_dig = sub.add_parser("digest")
    p_dig.add_argument("profile")
    p_dig.add_argument("--since", default=None,
                       help="only notices first seen on/after this date (default: today)")

    p_pro = sub.add_parser("prospects")
    p_pro.add_argument("profile")
    p_pro.add_argument("--months", type=int, default=12)
    p_pro.add_argument("--pages", type=int, default=4)

    p_rad = sub.add_parser("radar")
    p_rad.add_argument("profile")
    p_rad.add_argument("--months-ahead", type=int, default=12)
    p_rad.add_argument("--pages", type=int, default=15)

    p_run = sub.add_parser("run")
    p_run.add_argument("profile")

    sub.add_parser("profiles")

    args = ap.parse_args()

    if args.cmd == "ingest":
        con = ingest_mod.ensure_db()
        if args.download:
            ingest_mod.download()
        seen, new = ingest_mod.load_csv(con)
        print(f"ingested {seen} rows, {new} new")
    elif args.cmd == "digest":
        con = ingest_mod.ensure_db()
        since = args.since or date.today().isoformat()
        out, n = build_digest(con, args.profile, since=since)
        print(f"{n} items -> {out}")
    elif args.cmd == "prospects":
        end = date.today()
        start = end - timedelta(days=30 * args.months)
        out, n = build_prospects(args.profile, start.isoformat(), end.isoformat(),
                                 max_pages=args.pages)
        print(f"{n} prospect companies -> {out}")
    elif args.cmd == "radar":
        from .recompete import build_radar
        out, n = build_radar(args.profile, months_ahead=args.months_ahead,
                             max_pages=args.pages)
        print(f"{n} expiring contracts -> {out}")
    elif args.cmd == "run":
        con = ingest_mod.ensure_db()
        seen, new = ingest_mod.load_csv(con)
        out, n = build_digest(con, args.profile)
        print(f"ingested {seen} rows ({new} new); digest: {n} items -> {out}")
    elif args.cmd == "profiles":
        for p in filters.list_profiles():
            print(p)


if __name__ == "__main__":
    main()
