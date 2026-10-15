"""Google reviews: connect a profile, resolve the Place ID, sync, and see what
is cached. The screen states the Places limits plainly so nobody expects more
than five reviews or free calls."""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from core import audit, db, settings
from core.auth import require_role, verify_csrf
from core.util import load_json, parse_int
from services import google_places, google_reviews


def register(bp) -> None:

    @bp.route("/reviews")
    @require_role("reviews")
    def reviews_home():
        state = google_reviews.connection_state()
        cached = None
        row = google_reviews.cache_row(state["place_id"]) if state["place_id"] else None
        if row:
            cached = load_json(row["payload"], {}).get("reviews", [])
        return render_template(
            "admin/reviews.html", title="Google reviews", state=state, cached=cached,
            log=google_reviews.sync_log(15),
            candidates=None,
            write_url=google_places.write_review_url(state["place_id"]) if state["place_id"] else "",
        )

    @bp.route("/reviews/save", methods=["POST"])
    @require_role("reviews")
    def reviews_save():
        verify_csrf()
        before = google_reviews.connection_state()
        key = (request.form.get("api_key") or "").strip()
        if key and key != "********":
            settings.set("google.api_key", key)
        if request.form.get("clear_key"):
            settings.set("google.api_key", "")
        settings.set_many({
            "google.place_id": (request.form.get("place_id") or "").strip(),
            "google.place_name": (request.form.get("place_name") or "").strip(),
            "google.reviews_source": request.form.get("reviews_source") or "auto",
            "google.cache_ttl_minutes": max(15, parse_int(request.form.get("ttl"), 360)),
            "google.min_rating": parse_int(request.form.get("min_rating"), 0),
            "google.max_reviews": max(1, parse_int(request.form.get("max_reviews"), 5)),
            "google.photos_enabled": bool(request.form.get("photos_enabled")),
        })
        audit.log("update", "settings", "google", "Google reviews connection",
                  before={k: v for k, v in before.items() if k != "has_key"})
        flash("Google settings saved.", "ok")
        return redirect(url_for("admin.reviews_home"))

    @bp.route("/reviews/search", methods=["POST"])
    @require_role("reviews")
    def reviews_search():
        verify_csrf()
        api_key = settings.get("google.api_key", "")
        query = (request.form.get("query") or "").strip()
        if not api_key:
            flash("Add the API key first, then search.", "error")
            return redirect(url_for("admin.reviews_home"))
        if not query:
            flash("Type the practice name and city to search for.", "error")
            return redirect(url_for("admin.reviews_home"))

        ok, payload, status = google_places.search_text(api_key, query)
        if not ok:
            google_reviews.log_sync("", False, status, f"searchText: {payload}")
            flash(_explain(str(payload)), "error")
            return redirect(url_for("admin.reviews_home"))

        state = google_reviews.connection_state()
        google_reviews.log_sync("", True, 200, f"searchText for '{query}'", len(payload))
        return render_template(
            "admin/reviews.html", title="Google reviews", state=state, cached=None,
            log=google_reviews.sync_log(15), candidates=payload, query=query,
            write_url="")

    @bp.route("/reviews/sync", methods=["POST"])
    @require_role("reviews")
    def reviews_sync():
        verify_csrf()
        bundle = google_reviews.fetch_google(force=True)
        google_reviews.purge_expired()
        if bundle.error:
            flash(_explain(bundle.error), "error")
        else:
            flash(f"Fetched {bundle.count} review(s). Rating {bundle.rating}, "
                  f"{bundle.total} in total on Google.", "ok")
        audit.log("sync", "reviews", settings.get("google.place_id", ""),
                  f"manual sync, {bundle.count} reviews")
        return redirect(url_for("admin.reviews_home"))

    @bp.route("/reviews/clear", methods=["POST"])
    @require_role("reviews")
    def reviews_clear():
        verify_csrf()
        db.execute("DELETE FROM google_reviews_cache")
        audit.log("delete", "reviews", "", "cleared the review cache")
        flash("Cached review text cleared. The next page view fetches fresh data.", "ok")
        return redirect(url_for("admin.reviews_home"))

    @bp.route("/reviews/keep", methods=["POST"])
    @require_role("reviews")
    def reviews_keep():
        """Copy one cached Google review into the curated quotes, with attribution,
        so it survives the cache expiring."""
        verify_csrf()
        author = (request.form.get("author") or "").strip()
        body = (request.form.get("body") or "").strip()
        rating = parse_int(request.form.get("rating"), 5)
        review_id = (request.form.get("review_id") or "").strip()
        if not author or not body:
            flash("Nothing to copy.", "error")
            return redirect(url_for("admin.reviews_home"))
        if db.one("SELECT 1 FROM testimonials WHERE google_review_id = ?", (review_id,)):
            flash("That review has already been copied.", "error")
            return redirect(url_for("admin.reviews_home"))
        new_id = db.insert("testimonials", {
            "author": author, "author_role": "Google review", "rating": rating,
            "body": body, "source": "google", "google_review_id": review_id,
            "is_published": 1, "sort_order": db.next_sort_order("testimonials"),
        })
        audit.log("create", "testimonials", new_id, f"kept Google review by {author}")
        flash("Copied into the curated quotes. Make sure the patient is happy for it to be "
              "reproduced outside Google.", "ok")
        return redirect(url_for("admin.testimonials_edit", row_id=new_id))


def _explain(message: str) -> str:
    """Turn the common Google and network failures into something actionable."""
    low = message.lower()
    if "certificate" in low or "ssl" in low:
        return ("The request was blocked by TLS interception on this network: " + message +
                " Point the app at your corporate CA bundle, or try from an unfiltered network.")
    if "api key not valid" in low or "api_key_invalid" in low:
        return "Google rejected the API key. Check it and that Places API (New) is enabled."
    if "permission" in low or "403" in low:
        return ("Google accepted the key but refused the call. Enable Places API (New) on the "
                "project and check the key restrictions. " + message)
    if "not found" in low or "404" in low:
        return "Google does not recognise that Place ID. Search for the practice again."
    if "quota" in low or "429" in low:
        return "The project is over its Places quota. Reviews fall back to curated quotes."
    return message
