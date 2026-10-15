"""Typed key/value settings, cached for the life of a request.

Every value is stored as JSON so a setting can be a string, a number, a list of
opening hours or a whole nested block. DEFAULTS below is the single source of
truth for what the site expects to find.
"""

from __future__ import annotations

import json
import re

from flask import g

from core import db

DEFAULTS: dict = {
    # brand
    "brand.name": "Anvaya Dental Care",
    "brand.tagline": "Dentistry that explains itself",
    "brand.short": "Anvaya",
    "brand.logo_media_id": None,
    "brand.city": "Pune",
    "brand.established": "2011",
    # contact
    "contact.phone": "+91 20 4120 8800",
    "contact.phone_display": "020 4120 8800",
    "contact.whatsapp": "919000012345",
    "contact.email": "hello@anvayadental.in",
    "contact.emergency": "+91 90000 12345",
    "contact.address": "1st Floor, Sahyadri House, Law College Road, Pune 411004",
    "contact.map_url": "https://maps.google.com/?q=Law+College+Road+Pune",
    # socials
    "social.instagram": "https://instagram.com/",
    "social.facebook": "https://facebook.com/",
    "social.youtube": "",
    "social.google": "",
    # theme
    "theme.primary": "#0F766E",
    "theme.primary_dark": "#0B5B55",
    "theme.accent": "#E8A33D",
    "theme.ink": "#12211F",
    "theme.muted": "#5C6B69",
    "theme.surface": "#FFFFFF",
    "theme.canvas": "#F5F7F6",
    "theme.radius": "18",
    "theme.font_display": "Fraunces",
    "theme.font_body": "Manrope",
    "theme.font_url": (
        "https://fonts.googleapis.com/css2?"
        "family=Fraunces:ital,opsz,wght@0,9..144,400..700;1,9..144,400&"
        "family=Manrope:wght@300..800&display=swap"
    ),
    "theme.animations": True,
    # admin panel colours; every tint, hover and ring is mixed from the accent
    "admin.accent": "#22C57E",
    "admin.canvas": "#F5F5F7",
    "admin.sidebar": "#FAFAFA",
    "admin.ink": "#1D1D1F",
    # seo
    "seo.title_suffix": "Anvaya Dental Care, Pune",
    "seo.default_description": (
        "A Pune dental practice that quotes in writing, explains every step and "
        "offers no-cost EMI on longer treatments."
    ),
    "seo.og_media_id": None,
    "seo.indexable": True,
    # google reviews
    "google.api_key": "",
    "google.place_id": "",
    "google.place_name": "",
    "google.reviews_source": "auto",  # auto | google | manual
    "google.cache_ttl_minutes": 360,
    "google.min_rating": 4,
    "google.max_reviews": 5,
    "google.photos_enabled": False,
    # enquiries
    "enquiry.success_title": "Thank you, we have your request",
    "enquiry.success_body": (
        "Reception will call you on the number you gave us, usually within the "
        "same working day. Your reference is below, quote it if you ring us first."
    ),
    "enquiry.notify_email": "",
    "enquiry.slots": ["Morning (9am - 1pm)", "Afternoon (2pm - 5pm)", "Evening (5pm - 9pm)"],
    # emi
    "emi.enabled": True,
    "emi.note": (
        "No-cost EMI is offered on treatments above Rs 15,000. Approval is at the "
        "practice's discretion and needs a PAN and one address proof."
    ),
    "emi.currency": "INR",
    "emi.receipt_prefix": "ANV",
    # hours (0 = Sunday)
    "hours.week": {
        "mon": ["09:30", "20:00"],
        "tue": ["09:30", "20:00"],
        "wed": ["09:30", "20:00"],
        "thu": ["09:30", "20:00"],
        "fri": ["09:30", "20:00"],
        "sat": ["09:30", "18:00"],
        "sun": [],
    },
    "hours.note": "Sunday by appointment for emergencies only.",
    "hours.holidays": [],
}


def _cache() -> dict:
    if not hasattr(g, "_settings_cache"):
        rows = db.query("SELECT key, value FROM settings")
        store = {}
        for row in rows:
            try:
                store[row["key"]] = json.loads(row["value"]) if row["value"] is not None else None
            except (ValueError, TypeError):
                store[row["key"]] = row["value"]
        g._settings_cache = store
    return g._settings_cache


def get(key: str, default=None):
    store = _cache()
    if key in store:
        return store[key]
    if key in DEFAULTS:
        return DEFAULTS[key]
    return default


def set(key: str, value) -> None:  # noqa: A001 - deliberate settings API
    payload = json.dumps(value)
    db.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now')",
        (key, payload),
    )
    _cache()[key] = value


def set_many(items: dict) -> None:
    for key, value in items.items():
        set(key, value)


def all_settings() -> dict:
    merged = dict(DEFAULTS)
    merged.update(_cache())
    return merged


HEX_COLOUR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def colour(key: str) -> str:
    """A colour setting that is safe to write into a <style> block.

    Anything that is not a plain hex value falls back to the shipped default, so
    a bad value can never break the stylesheet or smuggle CSS into the page."""
    value = get(key)
    if isinstance(value, str) and HEX_COLOUR.match(value.strip()):
        return value.strip()
    return DEFAULTS.get(key) or "#000000"


def group(prefix: str) -> dict:
    """All settings under a prefix, with the prefix stripped from the keys."""
    out = {}
    for key, value in all_settings().items():
        if key.startswith(prefix + "."):
            out[key[len(prefix) + 1:]] = value
    return out


def ensure_defaults() -> None:
    """Write any missing default into the table so the admin can see every knob."""
    existing = {r["key"] for r in db.query("SELECT key FROM settings")}
    for key, value in DEFAULTS.items():
        if key not in existing:
            db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )
    if hasattr(g, "_settings_cache"):
        del g._settings_cache
