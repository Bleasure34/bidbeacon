"""Single source of deploy-time settings.

Empty values = preview mode: the site renders, but calls-to-action are inert
and clearly labelled as not live. This prevents a half-deployed site from
collecting an email address it cannot honour or taking money it cannot serve.
"""
import json
import os

BUILD_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
PATH = os.path.join(BUILD_DIR, "site_config.json")

_DEFAULTS = {
    "brand": "BidBeacon",
    "base_url": "",
    "signup_url": "",
    "checkout_url_monthly": "",
    "checkout_url_annual": "",
    "support_email": "",
    "postal_line": "",
    "operator_name": "",
}


def load(path=PATH):
    cfg = dict(_DEFAULTS)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        cfg.update({k: v for k, v in data.items() if not k.startswith("_")})
    return cfg


def is_live(cfg=None):
    """Live means: we can accept a signup AND tell people who we are."""
    cfg = cfg or load()
    return bool(cfg.get("signup_url") and cfg.get("support_email"))


def can_charge(cfg=None):
    cfg = cfg or load()
    return bool(cfg.get("checkout_url_monthly") or cfg.get("checkout_url_annual"))
