# BidBeacon

Federal contract intelligence for small trade contractors, built entirely from
public-domain government data.

Two things are produced for each trade niche:

- **Daily digest (free)** — every new federal opportunity matching a trade,
  region, and set-aside filter, deduplicated, with expired notices removed.
- **Recompete Radar (paid)** — every contract in that niche whose period of
  performance ends within 12 months, with the incumbent, award value, and
  agency. When a contract ends the work is re-competed; this is the pipeline
  of those chances.

## Data sources

| Source | Access | Licence |
|---|---|---|
| [SAM.gov contract opportunities](https://sam.gov) daily extract | anonymous, no key | public domain |
| [USAspending.gov](https://api.usaspending.gov) award API | keyless | public domain |

No scraping of protected or logged-in resources; both feeds are official
bulk/API endpoints intended for public reuse.

## Running it

```bash
cd 04_build && python -m engine.runner --download
```

```bash
cd 04_build && python tools/publish.py
```

The first command ingests the day's opportunity file, filters it per niche,
runs a QA gate (duplicates, expired deadlines, out-of-region items and unsafe
links are quarantined rather than published), and renders the digests. The
second refreshes the radars, landing pages, and search pages.

In production both run on a schedule via `.github/workflows/daily.yml`; no
local machine is involved.

## Tests

```bash
cd 04_build && python -m unittest discover -s tests
```

## Configuration

`04_build/site_config.json` holds deploy-time values (public URLs only; no
secrets). While it is unfilled the site builds in preview mode with inert
calls-to-action, so a partially-configured deployment cannot collect an email
address it is unable to honour. API keys live in repository secrets.

## Adding a niche

Drop a JSON file in `04_build/profiles/` describing NAICS codes, keywords,
states, and set-aside preferences. It is picked up automatically on the next
run.

## Note

Independent service. Not affiliated with any government agency. Listings are
informational and are not bidding advice; contract end dates reflect the
current period of performance and options may extend some awards.
