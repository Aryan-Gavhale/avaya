"""Reviews provider.

Two implementations behind one call, chosen in Settings:

  PlacesProvider  live from Google, held in a short-TTL cache table
  ManualProvider  curated testimonials rows

Compliance notes that shape this file:
  * Places returns at most five reviews. That is a Google limit, not ours.
  * Review text may not be stored permanently, so the cache row is transient and
    expires on `google.cache_ttl_minutes` (6 hours by default).
  * The only value kept indefinitely is the place_id.
  * Every rendered review keeps the author name, avatar and profile link, and the
    block carries the Google attribution plus the ordering/filtering notice.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from core import db, settings
from core.util import dump_json, load_json
from services import google_places


class Bundle:
    """What a section template receives, whatever the source was."""

    def __init__(self, source: str, reviews: list, rating=None, total=None,
                 maps_url: str = "", place_id: str = "", fetched_at: str = "",
                 stale: bool = False, error: str = ""):
        self.source = source
        self.reviews = reviews
        self.rating = rating
        self.total = total
        self.maps_url = maps_url
        self.place_id = place_id
        self.fetched_at = fetched_at
        self.stale = stale
        self.error = error

    @property
    def is_google(self) -> bool:
        return self.source == "google"

    @property
    def write_url(self) -> str:
        return google_places.write_review_url(self.place_id) if self.place_id else ""

    @property
    def count(self) -> int:
        return len(self.reviews)

    def __bool__(self) -> bool:
        return bool(self.reviews)


# ── normalising ─────────────────────────────────────────────────────────────
def _normalise_google(review: dict) -> dict:
    author = review.get("authorAttribution", {}) or {}
    text_block = review.get("originalText") or review.get("text") or {}
    return {
        "id": review.get("name", ""),
        "author": author.get("displayName", "A Google user"),
        "author_url": author.get("uri", ""),
        "avatar": author.get("photoUri", ""),
        "rating": int(review.get("rating") or 0),
        "body": (text_block.get("text") or "").strip(),
        "when": review.get("relativePublishTimeDescription", ""),
        "published": review.get("publishTime", ""),
        "source": "google",
    }


def _normalise_manual(row) -> dict:
    return {
        "id": f"t{row['id']}",
        "author": row["author"],
        "author_url": "",
        "avatar": "",
        "rating": int(row["rating"] or 5),
        "body": (row["body"] or "").strip(),
        "when": row["author_role"] or row["treatment"] or "",
        "published": row["created_at"],
        "source": "manual",
    }


# ── cache ───────────────────────────────────────────────────────────────────
def cache_row(place_id: str):
    return db.one("SELECT * FROM google_reviews_cache WHERE place_id = ?", (place_id,))


def cache_age_minutes(row) -> float | None:
    if not row:
        return None
    try:
        fetched = datetime.strptime(str(row["fetched_at"])[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None
    return (datetime.utcnow() - fetched).total_seconds() / 60.0


def cache_is_fresh(row) -> bool:
    ttl = float(settings.get("google.cache_ttl_minutes", 360) or 360)
    age = cache_age_minutes(row)
    return age is not None and age < ttl


def store_cache(place_id: str, payload: dict, reviews: list) -> None:
    db.execute(
        "INSERT INTO google_reviews_cache (place_id, payload, rating, total, fetched_at) "
        "VALUES (?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(place_id) DO UPDATE SET payload = excluded.payload, "
        "rating = excluded.rating, total = excluded.total, fetched_at = excluded.fetched_at",
        (
            place_id,
            dump_json({
                "reviews": reviews,
                "maps_url": payload.get("googleMapsUri", ""),
                "name": (payload.get("displayName") or {}).get("text", ""),
                "open_now": (payload.get("currentOpeningHours") or {}).get("openNow"),
            }),
            payload.get("rating"),
            payload.get("userRatingCount"),
        ),
    )


def purge_expired() -> int:
    """Drop cached review text that has outlived its TTL. Called on boot and sync."""
    ttl = int(float(settings.get("google.cache_ttl_minutes", 360) or 360))
    rows = db.query("SELECT place_id, fetched_at FROM google_reviews_cache")
    dropped = 0
    cutoff = datetime.utcnow() - timedelta(minutes=ttl * 4)
    for row in rows:
        try:
            fetched = datetime.strptime(str(row["fetched_at"])[:19], "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            continue
        if fetched < cutoff:
            db.execute("DELETE FROM google_reviews_cache WHERE place_id = ?", (row["place_id"],))
            dropped += 1
    return dropped


def log_sync(place_id: str, ok: bool, status_code, message: str, count: int = 0) -> None:
    db.insert("review_sync_log", {
        "place_id": place_id or "",
        "ok": 1 if ok else 0,
        "status_code": status_code if isinstance(status_code, int) else None,
        "message": (message or "")[:500],
        "count": count,
    })
    db.execute("DELETE FROM review_sync_log WHERE id NOT IN "
               "(SELECT id FROM review_sync_log ORDER BY id DESC LIMIT 100)")


def sync_log(limit: int = 20):
    return db.query("SELECT * FROM review_sync_log ORDER BY id DESC LIMIT ?", (limit,))


# ── providers ───────────────────────────────────────────────────────────────
def fetch_google(force: bool = False) -> Bundle:
    api_key = settings.get("google.api_key", "")
    place_id = settings.get("google.place_id", "")
    if not api_key or not place_id:
        return Bundle("google", [], error="Google is not connected yet.")

    row = cache_row(place_id)
    if row and not force and cache_is_fresh(row):
        cached = load_json(row["payload"], {})
        return Bundle(
            "google", cached.get("reviews", []), row["rating"], row["total"],
            cached.get("maps_url", ""), place_id, str(row["fetched_at"]),
        )

    ok, payload, status = google_places.place_details(api_key, place_id)
    if not ok:
        log_sync(place_id, False, status, str(payload))
        if row:  # serve stale rather than an empty section
            cached = load_json(row["payload"], {})
            return Bundle("google", cached.get("reviews", []), row["rating"], row["total"],
                          cached.get("maps_url", ""), place_id, str(row["fetched_at"]),
                          stale=True, error=str(payload))
        return Bundle("google", [], error=str(payload))

    reviews = [_normalise_google(r) for r in (payload.get("reviews") or [])]
    store_cache(place_id, payload, reviews)
    log_sync(place_id, True, 200, "Fetched place details.", len(reviews))
    return Bundle("google", reviews, payload.get("rating"), payload.get("userRatingCount"),
                  payload.get("googleMapsUri", ""), place_id,
                  db.scalar("SELECT datetime('now')"))


def fetch_manual(limit: int = 6) -> Bundle:
    rows = db.query(
        "SELECT * FROM testimonials WHERE is_published = 1 "
        "ORDER BY is_featured DESC, sort_order, id DESC LIMIT ?", (limit,)
    )
    reviews = [_normalise_manual(r) for r in rows]
    avg = None
    if reviews:
        avg = round(sum(r["rating"] for r in reviews) / len(reviews), 1)
    return Bundle("manual", reviews, avg, len(reviews))


def get_bundle(source: str = "auto", limit: int = 6, force: bool = False) -> Bundle:
    """The one entry point templates and routes use."""
    configured = settings.get("google.reviews_source", "auto")
    if source in ("", "auto", None):
        source = configured

    min_rating = int(settings.get("google.min_rating", 0) or 0)

    if source in ("google", "auto"):
        bundle = fetch_google(force=force)
        if bundle.reviews:
            if min_rating:
                bundle.reviews = [r for r in bundle.reviews if r["rating"] >= min_rating]
            bundle.reviews = bundle.reviews[:limit]
            return bundle
        if source == "google":
            return bundle
        fallback = fetch_manual(limit)
        fallback.error = bundle.error
        return fallback

    return fetch_manual(limit)


def connection_state() -> dict:
    place_id = settings.get("google.place_id", "")
    row = cache_row(place_id) if place_id else None
    return {
        "has_key": bool(settings.get("google.api_key", "")),
        "place_id": place_id,
        "place_name": settings.get("google.place_name", ""),
        "source": settings.get("google.reviews_source", "auto"),
        "ttl": settings.get("google.cache_ttl_minutes", 360),
        "cached": bool(row),
        "cache_fresh": cache_is_fresh(row) if row else False,
        "cache_age": round(cache_age_minutes(row) or 0) if row else None,
        "rating": row["rating"] if row else None,
        "total": row["total"] if row else None,
        "cached_count": len(load_json(row["payload"], {}).get("reviews", [])) if row else 0,
        "manual_count": int(db.scalar(
            "SELECT COUNT(*) FROM testimonials WHERE is_published = 1", (), 0)),
    }
