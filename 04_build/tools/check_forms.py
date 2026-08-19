"""Sanity-check that the signup form is inert in preview and wired when live."""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from engine import config, filters
from engine.landing import render_landing

prof = filters.load_profile("janitorial-southeast")
prof["name"] = "janitorial-southeast"
cfg = config.load()

h = render_landing(prof, [], "2026-08-19", cfg=cfg)
print("PREVIEW inert button :", "Sign-up opens at launch" in h)
print("PREVIEW no form       :", "<form" not in h)
print("PREVIEW no stripe     :", "buy.stripe.com" not in h)

cfg2 = dict(cfg)
cfg2["signup_url"] = "https://leasuredigital.com/bidbeacon/join.php"
cfg2["support_email"] = "bids@leasuredigital.com"
cfg2["postal_line"] = "123 Example St, FL"
h2 = render_landing(prof, [], "2026-08-19", cfg=cfg2)
print("LIVE form action      :", 'action="https://leasuredigital.com/bidbeacon/join.php"' in h2)
print("LIVE list field       :", 'value="janitorial-southeast"' in h2)
print("LIVE honeypot         :", 'name="company"' in h2)
print("LIVE stripe wired     :", "buy.stripe.com" in h2)
print("LIVE banner gone      :", "Preview build" not in h2)
print("LIVE operator shown   :", "Leasure Digital" in h2)
