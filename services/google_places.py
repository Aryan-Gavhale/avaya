"""Thin client for the Google Places API (New).

Only three calls are needed: find the clinic's Place ID by name, read the place
details (rating, count, up to five reviews) and proxy a place photo. Everything
returns (ok, payload_or_error) so callers never have to catch requests errors.
"""

from __future__ import annotations

import requests
from flask import current_app, has_app_context

BASE = "https://places.googleapis.com/v1"
TIMEOUT = 12

DETAIL_FIELDS = (
    "id,displayName,formattedAddress,rating,userRatingCount,googleMapsUri,"
    "reviews,currentOpeningHours.openNow"
)
SEARCH_FIELDS = (
    "places.id,places.displayName,places.formattedAddress,places.rating,"
    "places.userRatingCount"
)
PHOTO_FIELDS = "id,photos"


def _headers(api_key: str, field_mask: str) -> dict:
    return {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": field_mask,
        "Content-Type": "application/json",
    }


def _verify() -> bool:
    """False lets requests through a TLS-inspecting corporate proxy, which is the one
    situation where an office network cannot reach Google at all. Opt in per install
    with "google_verify_tls": false in config.json."""
    if has_app_context():
        return bool(current_app.config.get("GOOGLE_VERIFY_TLS", True))
    return True


def _error_text(response) -> str:
    try:
        data = response.json()
        return (data.get("error", {}) or {}).get("message") or response.text[:300]
    except ValueError:
        return response.text[:300]


def place_details(api_key: str, place_id: str, field_mask: str = DETAIL_FIELDS):
    if not api_key or not place_id:
        return False, "Missing API key or Place ID.", None
    url = f"{BASE}/places/{place_id}"
    try:
        response = requests.get(url, headers=_headers(api_key, field_mask),
                                timeout=TIMEOUT, verify=_verify())
    except requests.RequestException as exc:
        return False, f"Could not reach Google: {exc}", None
    if response.status_code != 200:
        return False, _error_text(response), response.status_code
    return True, response.json(), 200


def search_text(api_key: str, text_query: str, max_results: int = 6):
    if not api_key or not text_query:
        return False, "Missing API key or search text.", None
    url = f"{BASE}/places:searchText"
    body = {"textQuery": text_query, "maxResultCount": max(1, min(20, max_results))}
    try:
        response = requests.post(url, json=body, headers=_headers(api_key, SEARCH_FIELDS),
                                 timeout=TIMEOUT, verify=_verify())
    except requests.RequestException as exc:
        return False, f"Could not reach Google: {exc}", None
    if response.status_code != 200:
        return False, _error_text(response), response.status_code
    return True, response.json().get("places", []), 200


def place_photo_names(api_key: str, place_id: str, limit: int = 10):
    ok, payload, status = place_details(api_key, place_id, PHOTO_FIELDS)
    if not ok:
        return False, payload, status
    photos = (payload or {}).get("photos", [])[:limit]
    return True, [p.get("name") for p in photos if p.get("name")], 200


def photo_url(api_key: str, photo_name: str, max_width: int = 1200) -> str:
    """Media endpoint URL. Returned to the browser through our own proxy route so
    the key is never exposed in page source."""
    return f"{BASE}/{photo_name}/media?maxWidthPx={max_width}&key={api_key}"


def fetch_photo_bytes(api_key: str, photo_name: str, max_width: int = 1200):
    try:
        response = requests.get(photo_url(api_key, photo_name, max_width),
                                timeout=TIMEOUT, allow_redirects=True, verify=_verify())
    except requests.RequestException as exc:
        return False, f"Could not reach Google: {exc}", None
    if response.status_code != 200:
        return False, _error_text(response), response.status_code
    return True, response.content, response.headers.get("Content-Type", "image/jpeg")


def write_review_url(place_id: str) -> str:
    return f"https://search.google.com/local/writereview?placeid={place_id}"
