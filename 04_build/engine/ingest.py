"""Ingest the SAM.gov public contract-opportunities extract into SQLite.

The extract is a full snapshot of active notices (~84k rows, ~250MB CSV,
refreshed daily, anonymous access). We keep a persistent notices table plus
a first_seen date per NoticeId so "new since yesterday" is a cheap diff.
"""
import csv
import io
import os
import sqlite3
import sys
from datetime import date, datetime

import requests

CSV_URL = ("https://falextracts.s3.amazonaws.com/Contract%20Opportunities/datagov/"
           "ContractOpportunitiesFullCSV.csv")

BUILD_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
RAW_CSV = os.path.join(BUILD_DIR, "data", "raw", "ContractOpportunitiesFullCSV.csv")
DB_PATH = os.path.join(BUILD_DIR, "data", "notices.sqlite")

# extract column -> db column
COLMAP = {
    "NoticeId": "notice_id",
    "Title": "title",
    "Sol#": "solicitation_no",
    "Department/Ind.Agency": "agency",
    "Sub-Tier": "sub_tier",
    "Office": "office",
    "PostedDate": "posted",
    "Type": "notice_type",
    "SetASide": "set_aside",
    "ResponseDeadLine": "deadline",
    "NaicsCode": "naics",
    "ClassificationCode": "psc",
    "PopCity": "pop_city",
    "PopState": "pop_state",
    "PopZip": "pop_zip",
    "Active": "active",
    "Description": "description",
    "Link": "link",
    "PrimaryContactFullname": "contact_name",
    "PrimaryContactEmail": "contact_email",
}

BIDDABLE_TYPES = {
    "Solicitation",
    "Combined Synopsis/Solicitation",
    "Presolicitation",
    "Sources Sought",
    "Special Notice",
}


def ensure_db(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS notices (
            notice_id TEXT PRIMARY KEY,
            title TEXT, solicitation_no TEXT, agency TEXT, sub_tier TEXT,
            office TEXT, posted TEXT, notice_type TEXT, set_aside TEXT,
            deadline TEXT, naics TEXT, psc TEXT, pop_city TEXT, pop_state TEXT,
            pop_zip TEXT, active TEXT, description TEXT, link TEXT,
            contact_name TEXT, contact_email TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL
        )""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_naics ON notices(naics)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_posted ON notices(posted)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_first_seen ON notices(first_seen)")
    con.execute("""
        CREATE TABLE IF NOT EXISTS ingest_runs (
            run_at TEXT, rows_seen INTEGER, rows_new INTEGER, source TEXT
        )""")
    return con


def download(dest=RAW_CSV, url=CSV_URL, quiet=False):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".part"
    with requests.get(url, stream=True, timeout=180,
                      headers={"User-Agent": "bidbeacon/0.1"}) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    os.replace(tmp, dest)
    if not quiet:
        print(f"downloaded {os.path.getsize(dest)/1e6:.1f} MB")
    return dest


def load_csv(con, src=RAW_CSV, today=None):
    """Upsert the snapshot. Returns (rows_seen, rows_new)."""
    today = today or date.today().isoformat()
    seen = new = 0
    cur = con.cursor()
    cols = list(COLMAP.values())
    placeholders = ",".join("?" * (len(cols) + 2))
    insert_sql = (
        f"INSERT INTO notices ({','.join(cols)}, first_seen, last_seen) "
        f"VALUES ({placeholders}) "
        "ON CONFLICT(notice_id) DO UPDATE SET "
        + ",".join(f"{c}=excluded.{c}" for c in cols if c != "notice_id")
        + ", last_seen=excluded.last_seen"
    )
    with io.open(src, encoding="latin-1", newline="") as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            seen += 1
            vals = [(row.get(k) or "").strip() for k in COLMAP]
            batch.append(vals + [today, today])
            if len(batch) >= 5000:
                new += _flush(cur, insert_sql, batch)
                batch = []
        if batch:
            new += _flush(cur, insert_sql, batch)
    cur.execute("INSERT INTO ingest_runs VALUES (?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), seen, new, src))
    con.commit()
    return seen, new


def _flush(cur, insert_sql, batch):
    before = cur.connection.total_changes
    # count new by pre-checking existing ids in this batch
    ids = [b[0] for b in batch]
    q = ",".join("?" * len(ids))
    existing = {r[0] for r in cur.execute(
        f"SELECT notice_id FROM notices WHERE notice_id IN ({q})", ids)}
    cur.executemany(insert_sql, batch)
    return len([i for i in ids if i not in existing])


def main(argv=None):
    argv = argv or sys.argv[1:]
    con = ensure_db()
    if "--download" in argv or not os.path.exists(RAW_CSV):
        download()
    seen, new = load_csv(con)
    print(f"ingested snapshot: {seen} rows, {new} new notice ids")


if __name__ == "__main__":
    main()
