"""Engine unit tests. Run from 04_build/:  python -m unittest discover -s tests -v"""
import csv
import io
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from engine import filters, ingest, qa, recompete
from engine.digest import render_html, render_markdown, _fmt_deadline


def profile(**kw):
    base = {
        "naics_prefixes": ["561720"], "psc_prefixes": [], "keywords": ["janitorial"],
        "exclude_keywords": ["snow removal"], "states": [], "set_asides": ["Small Business"],
        "notice_types": list(filters.BIDDABLE_TYPES), "min_score": 3, "max_items": 40,
    }
    base.update(kw)
    return base


def row(**kw):
    base = {
        "notice_id": "N1", "title": "Janitorial services", "solicitation_no": "SOL-1",
        "agency": "GSA", "sub_tier": "", "office": "", "posted": "2026-08-18",
        "notice_type": "Solicitation", "set_aside": "Small Business Set Aside - Total",
        "deadline": "2026-09-10", "naics": "561720", "psc": "S201",
        "pop_city": "Tampa", "pop_state": "FL", "pop_zip": "", "active": "Yes",
        "description": "", "link": "", "contact_name": "", "contact_email": "",
    }
    base.update(kw)
    return base


TODAY = date(2026, 8, 19)


class TestParseDeadline(unittest.TestCase):
    def test_iso_with_tz(self):
        self.assertEqual(filters.parse_deadline("2026-08-31T09:00:00-04:00"),
                         date(2026, 8, 31))

    def test_plain_date(self):
        self.assertEqual(filters.parse_deadline("2026-09-14"), date(2026, 9, 14))

    def test_us_format(self):
        self.assertEqual(filters.parse_deadline("09/14/2026"), date(2026, 9, 14))

    def test_garbage(self):
        self.assertIsNone(filters.parse_deadline("TBD"))
        self.assertIsNone(filters.parse_deadline(""))


class TestScore(unittest.TestCase):
    def test_positive_match(self):
        pts, why = filters.score(row(), profile(), today=TODAY)
        # naics exact +3, kw title +2, set-aside +2, deadline 22d +1
        self.assertEqual(pts, 8)

    def test_exclude_keyword_kills(self):
        pts, _ = filters.score(row(title="Snow removal and janitorial"),
                               profile(), today=TODAY)
        self.assertEqual(pts, -99)

    def test_expired_deadline_kills(self):
        pts, why = filters.score(row(deadline="2026-08-01"), profile(), today=TODAY)
        self.assertEqual(pts, -99)

    def test_out_of_region_strict_kills(self):
        pts, _ = filters.score(row(pop_state="NM"),
                               profile(states=["FL", "GA"]), today=TODAY)
        self.assertEqual(pts, -99)

    def test_out_of_region_lenient_penalizes(self):
        pts, _ = filters.score(row(pop_state="NM"),
                               profile(states=["FL", "GA"], states_strict=False),
                               today=TODAY)
        self.assertEqual(pts, 7)  # 8 - 1

    def test_blank_state_survives_strict(self):
        pts, _ = filters.score(row(pop_state=""),
                               profile(states=["FL", "GA"]), today=TODAY)
        self.assertEqual(pts, 7)  # no +1, -1 for unknown state

    def test_naics_prefix_scores_two(self):
        pts, _ = filters.score(row(naics="561790"),
                               profile(naics_prefixes=["5617"]), today=TODAY)
        self.assertEqual(pts, 7)  # prefix +2 instead of exact +3


class TestDedupe(unittest.TestCase):
    def test_same_solicitation_keeps_latest(self):
        a = row(notice_id="A", posted="2026-08-01")
        b = row(notice_id="B", posted="2026-08-15")
        out = filters.dedupe([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["notice_id"], "B")

    def test_no_solnum_falls_back_to_title_agency(self):
        a = row(notice_id="A", solicitation_no="", posted="2026-08-01")
        b = row(notice_id="B", solicitation_no="", posted="2026-08-15")
        c = row(notice_id="C", solicitation_no="", title="Different job",
                posted="2026-08-02")
        out = filters.dedupe([a, b, c])
        self.assertEqual({r["notice_id"] for r in out}, {"B", "C"})


class TestRender(unittest.TestCase):
    def test_html_escapes(self):
        r = row(title='Janitorial <script>alert(1)</script> & more')
        h = render_html({"display_name": "T"}, [r], "2026-08-19")
        self.assertNotIn("<script>alert", h)
        self.assertIn("&lt;script&gt;", h)

    def test_empty_digest(self):
        md = render_markdown({"display_name": "T"}, [], "2026-08-19")
        self.assertIn("No qualifying", md)

    def test_deadline_format(self):
        self.assertEqual(_fmt_deadline("2026-08-31T09:00:00-04:00"),
                         "2026-08-31 09:00 (UTC-4)")
        self.assertEqual(_fmt_deadline(""), "no deadline listed")
        self.assertEqual(_fmt_deadline("2026-09-14"), "2026-09-14")


def award(**kw):
    base = {"Award ID": "W1", "Recipient Name": "ACME LLC", "Award Amount": 500000.0,
            "Awarding Agency": "GSA", "Awarding Sub Agency": "PBS",
            "Start Date": "2024-01-01", "End Date": "2026-12-01",
            "Description": "Janitorial services for federal building",
            "Place of Performance State Code": "FL"}
    base.update(kw)
    return base


class TestRecompete(unittest.TestCase):
    T = date(2026, 8, 19)

    def _win(self, rows, **kw):
        return recompete.expiring_window(rows, months_ahead=12, today=self.T, **kw)

    def test_in_window_kept(self):
        out, dropped = self._win([award()])
        self.assertEqual(len(out), 1)
        self.assertEqual(dropped, 0)
        self.assertEqual(out[0]["_days_left"], 104)

    def test_past_and_far_future_excluded(self):
        out, _ = self._win([award(**{"End Date": "2026-08-01"}),
                            award(**{"Award ID": "W2", "End Date": "2028-01-01"})])
        self.assertEqual(out, [])

    def test_min_value_filter(self):
        out, _ = self._win([award(**{"Award Amount": 5000.0})], min_value=25000)
        self.assertEqual(out, [])

    def test_keyword_filter(self):
        out, _ = self._win([award(Description="Boiler valve replacement")],
                           keywords=["janitorial", "custodial"])
        self.assertEqual(out, [])
        out, _ = self._win([award()], keywords=["janitorial"])
        self.assertEqual(len(out), 1)

    def test_dedupe_by_award_id(self):
        out, _ = self._win([award(), award()])
        self.assertEqual(len(out), 1)

    def test_max_items_and_dropped_count(self):
        rows = [award(**{"Award ID": f"W{i}"}) for i in range(10)]
        out, dropped = self._win(rows, max_items=4)
        self.assertEqual((len(out), dropped), (4, 6))

    def test_sorted_by_end_date(self):
        rows = [award(**{"Award ID": "L", "End Date": "2027-06-01"}),
                award(**{"Award ID": "E", "End Date": "2026-09-01"})]
        out, _ = self._win(rows)
        self.assertEqual([r["Award ID"] for r in out], ["E", "L"])

    def test_bucket_labels(self):
        self.assertEqual(recompete.bucket(30), "Next 90 days")
        self.assertEqual(recompete.bucket(150), "3-6 months out")
        self.assertEqual(recompete.bucket(300), "6-12 months out")


class TestSubscribers(unittest.TestCase):
    def setUp(self):
        from engine import subscribers as subs
        self.subs = subs
        self.td = tempfile.TemporaryDirectory()
        self.con = subs.ensure_db(os.path.join(self.td.name, "s.sqlite"))
        # redirect outbox into the tempdir
        self._old_outbox = subs.OUTBOX
        subs.OUTBOX = os.path.join(self.td.name, "outbox")

    def tearDown(self):
        self.subs.OUTBOX = self._old_outbox
        self.con.close()
        self.td.cleanup()

    def _token(self, email, profile="p1"):
        return self.con.execute(
            "SELECT token FROM subscribers WHERE email=? AND profile=?",
            (email, profile)).fetchone()[0]

    def test_signup_confirm_deliver(self):
        self.assertEqual(self.subs.signup(self.con, "A@x.com", "p1"), "pending")
        # not delivered while pending
        self.assertEqual(self.subs.deliver_digest(self.con, "p1", "s", "b"), 0)
        self.assertTrue(self.subs.confirm(self.con, self._token("a@x.com")))
        self.assertEqual(self.subs.deliver_digest(self.con, "p1", "s", "b"), 1)
        sent = os.listdir(self.subs.OUTBOX)
        self.assertEqual(len(sent), 2)  # confirmation + digest
        body = io.open(os.path.join(self.subs.OUTBOX, sorted(sent)[-1]),
                       encoding="utf-8").read()
        self.assertIn("Unsubscribe instantly", body)

    def test_invalid_email_rejected(self):
        self.assertEqual(self.subs.signup(self.con, "nope", "p1"), "invalid")

    def test_unsubscribe_is_permanent(self):
        self.subs.signup(self.con, "b@x.com", "p1")
        tok = self._token("b@x.com")
        self.subs.confirm(self.con, tok)
        self.assertTrue(self.subs.unsubscribe(self.con, tok))
        self.assertEqual(self.subs.deliver_digest(self.con, "p1", "s", "b"), 0)
        # re-signup is silently suppressed
        self.assertEqual(self.subs.signup(self.con, "b@x.com", "p1"), "suppressed")

    def test_double_signup_no_dup(self):
        self.subs.signup(self.con, "c@x.com", "p1")
        self.subs.signup(self.con, "c@x.com", "p1")
        n = self.con.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]
        self.assertEqual(n, 1)

    def test_bad_token_confirm_fails(self):
        self.assertFalse(self.subs.confirm(self.con, "bogus"))


class TestPages(unittest.TestCase):
    def test_render_page_escapes_and_carries_data(self):
        from engine import pages
        prof = profile()
        prof["display_name"] = "Test Niche"
        prof["trade_name"] = "Test <Trade>"
        opps = [row(title='Janitorial <img src=x onerror=alert(1)>')]
        radar = [award(**{"Recipient Name": "ACME & <SONS>"})]
        h = pages.render_page(prof, opps, radar, "2026-08-19", state="FL",
                              states_index=["FL", "GA"])
        self.assertNotIn("<img", h)          # no live tag survives
        self.assertIn("&lt;img", h)          # it renders as inert escaped text
        self.assertIn("ACME &amp; &lt;SONS&gt;", h)
        self.assertIn("Florida", h)
        self.assertIn("ga.html", h)  # cross-links to sibling state

    def test_render_page_empty_tables(self):
        from engine import pages
        h = pages.render_page(profile(), [], [], "2026-08-19")
        self.assertIn("None currently", h)
        self.assertIn("Sample available", h)


class TestQA(unittest.TestCase):
    def test_clean_rows_pass(self):
        ok, issues = qa.check_rows([row()], profile(), today=TODAY)
        self.assertTrue(ok, issues)

    def test_expired_deadline_caught(self):
        ok, issues = qa.check_rows([row(deadline="2026-08-01")], profile(), today=TODAY)
        self.assertFalse(ok)
        self.assertIn("expired", issues[0])

    def test_duplicate_caught(self):
        ok, issues = qa.check_rows([row(notice_id="A"), row(notice_id="B")],
                                   profile(), today=TODAY)
        self.assertFalse(ok)
        self.assertIn("duplicate", issues[0])

    def test_out_of_region_caught(self):
        ok, issues = qa.check_rows([row(pop_state="NM")],
                                   profile(states=["FL"]), today=TODAY)
        self.assertFalse(ok)
        self.assertIn("out-of-region", issues[0])

    def test_bad_link_caught(self):
        ok, issues = qa.check_rows([row(link="http://evil.example.com/x")],
                                   profile(), today=TODAY)
        self.assertFalse(ok)
        self.assertIn("non-sam.gov", issues[0])

    def test_script_in_html_caught(self):
        ok, issues = qa.check_html("<div><script>x</script></div>")
        self.assertFalse(ok)


class TestIngest(unittest.TestCase):
    def _csv(self, path, rows):
        headers = list(ingest.COLMAP.keys())
        with io.open(path, "w", encoding="latin-1", newline="") as f:
            w = csv.DictWriter(f, fieldnames=headers)
            w.writeheader()
            for r in rows:
                w.writerow(r)

    def test_upsert_and_new_count(self):
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "t.sqlite")
            src = os.path.join(td, "t.csv")
            con = ingest.ensure_db(db)
            self._csv(src, [{"NoticeId": "X1", "Title": "First"},
                            {"NoticeId": "X2", "Title": "Second"}])
            seen, new = ingest.load_csv(con, src=src, today="2026-08-19")
            self.assertEqual((seen, new), (2, 2))
            # re-ingest with one update and one addition
            self._csv(src, [{"NoticeId": "X1", "Title": "First updated"},
                            {"NoticeId": "X3", "Title": "Third"}])
            seen, new = ingest.load_csv(con, src=src, today="2026-08-20")
            self.assertEqual((seen, new), (2, 1))
            got = dict(con.execute("SELECT notice_id, title FROM notices").fetchall())
            self.assertEqual(got["X1"], "First updated")
            first_seen = dict(con.execute(
                "SELECT notice_id, first_seen FROM notices").fetchall())
            self.assertEqual(first_seen["X1"], "2026-08-19")  # preserved on update
            self.assertEqual(first_seen["X3"], "2026-08-20")
            con.close()  # Windows: unlock the db file before tempdir cleanup


if __name__ == "__main__":
    unittest.main()
