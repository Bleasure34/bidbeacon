"""Opt-in subscriber store + delivery (double-opt-in; outbox until G-3).

Consent rules are structural, not aspirational:
- Only addresses that signed up themselves enter the store (no imports).
- Nothing is delivered until the address confirms (double-opt-in).
- Every delivery carries an unsubscribe link; unsubscribe is immediate and
  permanent (suppression survives re-signup attempts).
- Until gate G-3 provides a real delivery account, "sending" writes .eml-style
  files to 04_build/outbox/ — same interface, zero external effect.
"""
import os
import secrets
import sqlite3
from datetime import datetime

BUILD_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BUILD_DIR, "data", "subscribers.sqlite")
OUTBOX = os.path.join(BUILD_DIR, "outbox")

FOOTER = """--
You requested this digest at signup and confirmed by email.
Unsubscribe instantly: {unsub_url}
{postal_line}"""

CONFIRM_BODY = """Confirm your subscription to {list_name}.

Click to confirm: {confirm_url}

If you didn't request this, ignore this message — you will not be emailed
again."""


def ensure_db(path=DB_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            email TEXT NOT NULL,
            profile TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            token TEXT NOT NULL,
            created TEXT NOT NULL,
            confirmed_at TEXT,
            unsubscribed_at TEXT,
            PRIMARY KEY (email, profile)
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS suppression (
            email TEXT PRIMARY KEY,
            reason TEXT,
            at TEXT
        )""")
    return con


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _outbox_write(to_addr, subject, body):
    os.makedirs(OUTBOX, exist_ok=True)
    safe = to_addr.replace("@", "_at_").replace("/", "_")
    # random suffix: Windows' clock is too coarse to keep rapid writes unique
    fn = f"{datetime.now().strftime('%Y%m%dT%H%M%S%f')}_{secrets.token_hex(4)}_{safe}.eml"
    path = os.path.join(OUTBOX, fn)
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"To: {to_addr}\nSubject: {subject}\n\n{body}")
    return path


def signup(con, email, profile, base_url="https://BASE_URL_PLACEHOLDER"):
    """Register a signup and emit the confirmation message. Returns status."""
    email = email.strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return "invalid"
    if con.execute("SELECT 1 FROM suppression WHERE email=?", (email,)).fetchone():
        return "suppressed"  # unsubscribed addresses stay gone, silently
    row = con.execute(
        "SELECT status, token FROM subscribers WHERE email=? AND profile=?",
        (email, profile)).fetchone()
    if row and row[0] == "confirmed":
        return "already-confirmed"
    token = row[1] if row else secrets.token_urlsafe(24)
    if not row:
        con.execute(
            "INSERT INTO subscribers (email, profile, status, token, created) "
            "VALUES (?,?,?,?,?)", (email, profile, "pending", token, _now()))
        con.commit()
    _outbox_write(email, "Confirm your subscription",
                  CONFIRM_BODY.format(list_name=profile,
                                      confirm_url=f"{base_url}/confirm/{token}"))
    return "pending"


def confirm(con, token):
    cur = con.execute(
        "UPDATE subscribers SET status='confirmed', confirmed_at=? "
        "WHERE token=? AND status='pending'", (_now(), token))
    con.commit()
    return cur.rowcount == 1


def unsubscribe(con, token):
    row = con.execute("SELECT email FROM subscribers WHERE token=?",
                      (token,)).fetchone()
    if not row:
        return False
    con.execute("UPDATE subscribers SET status='unsubscribed', unsubscribed_at=? "
                "WHERE token=?", (_now(), token))
    con.execute("INSERT OR IGNORE INTO suppression VALUES (?,?,?)",
                (row[0], "unsubscribe", _now()))
    con.commit()
    return True


def confirmed(con, profile):
    return [(e, t) for e, t in con.execute(
        "SELECT email, token FROM subscribers "
        "WHERE profile=? AND status='confirmed'", (profile,))]


def deliver_digest(con, profile, subject, body_md,
                   base_url="https://BASE_URL_PLACEHOLDER",
                   postal_line="[postal address required before real sending — gate G-3]"):
    """Deliver to every confirmed subscriber of the profile. Returns count."""
    n = 0
    for email, token in confirmed(con, profile):
        footer = FOOTER.format(unsub_url=f"{base_url}/unsubscribe/{token}",
                               postal_line=postal_line)
        _outbox_write(email, subject, f"{body_md}\n\n{footer}")
        n += 1
    return n
