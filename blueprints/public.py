"""The public site. Every route renders rows from SQLite; nothing is hard-coded.

A page is an ordered list of typed sections. build_context() gathers whatever a
section type needs (services, doctors, reviews, EMI plans and so on) so the
partials stay dumb and the queries stay in one place.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

from flask import (Blueprint, Response, abort, current_app, jsonify, redirect,
                   render_template, request, url_for)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core import db, emi as emi_core, hours as hours_mod, media, settings
from core.auth import verify_csrf
from core.util import (clean_phone, client_ip, dump_json, load_json, parse_float,
                       parse_int, ref_code, valid_email, valid_phone)
from services import google_places, google_reviews

bp = Blueprint("public", __name__)

MAX_ENQUIRIES_PER_IP_PER_HOUR = 6      # beyond this, stored but flagged for review
HARD_LIMIT_PER_IP_PER_HOUR = 20        # beyond this, refused outright
HARD_LIMIT_PER_HOUR = 120              # whole-site ceiling, so a botnet cannot fill the disk
MIN_FORM_SECONDS = 3
FORM_TOKEN_MAX_AGE = 6 * 60 * 60       # a form left open all day is asked to reload


# ── shared lookups ──────────────────────────────────────────────────────────
def nav(location: str = "header"):
    return db.query(
        "SELECT * FROM nav_items WHERE location = ? AND is_published = 1 ORDER BY sort_order",
        (location,),
    )


def published_branches():
    return db.query("SELECT * FROM branches WHERE is_published = 1 ORDER BY sort_order")


def published_services(limit: int = 100):
    return db.query(
        "SELECT s.*, c.name AS category_name FROM services s "
        "LEFT JOIN service_categories c ON c.id = s.category_id "
        "WHERE s.is_published = 1 ORDER BY s.sort_order, s.name LIMIT ?", (limit,)
    )


@bp.app_context_processor
def site_context():
    return {
        "header_nav": nav("header"),
        "footer_nav": nav("footer"),
        "footer_nav2": nav("footer2"),
        "site_branches": published_branches(),
        "open_state": hours_mod.state(),
        "hours_rows": hours_mod.compact(),
        "hours_full": hours_mod.week(),
        "this_year": date.today().year,
    }


# ── section data ────────────────────────────────────────────────────────────
def section_extras(section) -> dict:
    kind = section["type"]
    data = load_json(section["data"], {})
    extra: dict = {}

    if kind == "services":
        mode = data.get("mode", "featured")
        limit = parse_int(data.get("limit"), 6) or 6
        sql = ("SELECT s.*, c.name AS category_name FROM services s "
               "LEFT JOIN service_categories c ON c.id = s.category_id "
               "WHERE s.is_published = 1")
        args: list = []
        if mode == "featured":
            sql += " AND s.is_featured = 1"
        elif mode == "category" and data.get("category_id"):
            sql += " AND s.category_id = ?"
            args.append(data["category_id"])
        sql += " ORDER BY s.sort_order, s.name LIMIT ?"
        args.append(limit)
        extra["services"] = db.query(sql, args)
        if mode == "all":
            extra["grouped"] = _grouped_services(extra["services"])

    elif kind == "doctors":
        extra["doctors"] = db.query(
            "SELECT * FROM doctors WHERE is_published = 1 ORDER BY sort_order LIMIT ?",
            (parse_int(data.get("limit"), 4) or 4,))

    elif kind == "gallery":
        gallery_id = data.get("gallery_id")
        if gallery_id:
            extra["items"] = db.query(
                "SELECT gi.*, m.* FROM gallery_items gi JOIN media m ON m.id = gi.media_id "
                "WHERE gi.gallery_id = ? ORDER BY gi.sort_order", (gallery_id,))
        else:
            extra["items"] = db.query("SELECT * FROM media ORDER BY id DESC LIMIT 8")

    elif kind == "faq":
        sql = "SELECT * FROM faqs WHERE is_published = 1"
        args = []
        if data.get("category"):
            sql += " AND category = ?"
            args.append(data["category"])
        sql += " ORDER BY sort_order LIMIT ?"
        args.append(parse_int(data.get("limit"), 8) or 8)
        extra["faqs"] = db.query(sql, args)

    elif kind == "reviews":
        bundle = google_reviews.get_bundle(
            data.get("source", "auto"), parse_int(data.get("limit"), 6) or 6)
        extra["bundle"] = bundle

    elif kind == "emi":
        amount = parse_float(data.get("default_amount"), 60000) or 60000
        extra["plans"] = emi_core.plans_payload(amount)
        extra["default_amount"] = amount
        extra["max_amount"] = parse_float(data.get("max_amount"), 400000) or 400000
        extra["services"] = published_services(40)

    elif kind == "branches":
        rows = []
        for branch in published_branches():
            rows.append({
                "row": branch,
                "state": hours_mod.state(branch["hours"]),
                "hours": hours_mod.compact(branch["hours"]),
            })
        extra["branches"] = rows

    elif kind == "enquiry":
        extra["services"] = published_services(40)
        extra["branches"] = published_branches()
        extra["slots"] = settings.get("enquiry.slots", [])

    return extra


def _grouped_services(rows):
    groups: dict = {}
    for row in rows:
        key = row["category_name"] or "Other treatments"
        groups.setdefault(key, []).append(row)
    return groups


def build_sections(page_id: int) -> list[dict]:
    rows = db.query(
        "SELECT * FROM sections WHERE page_id = ? AND is_published = 1 ORDER BY sort_order",
        (page_id,),
    )
    built = []
    for row in rows:
        built.append({
            "row": row,
            "type": row["type"],
            "data": load_json(row["data"], {}),
            "extra": section_extras(row),
        })
    return built


# ── pages ───────────────────────────────────────────────────────────────────
def _render_page(page):
    return render_template(
        "public/page.html",
        page=page,
        sections=build_sections(page["id"]),
        meta_title=page["meta_title"] or f"{page['title']} | {settings.get('seo.title_suffix')}",
        meta_description=page["meta_description"] or settings.get("seo.default_description"),
        og_url=media.media_url(page["og_media_id"], "medium") if page["og_media_id"] else "",
    )


@bp.route("/")
def home():
    page = db.one("SELECT * FROM pages WHERE is_home = 1 AND is_published = 1 ORDER BY id LIMIT 1")
    if not page:
        page = db.one("SELECT * FROM pages WHERE is_published = 1 ORDER BY sort_order LIMIT 1")
    if not page:
        return render_template("public/empty.html")
    return _render_page(page)


@bp.route("/treatments/<slug>")
def service(slug):
    row = db.one(
        "SELECT s.*, c.name AS category_name, c.slug AS category_slug FROM services s "
        "LEFT JOIN service_categories c ON c.id = s.category_id "
        "WHERE s.slug = ? AND s.is_published = 1", (slug,))
    if not row:
        abort(404)
    related = db.query(
        "SELECT * FROM services WHERE is_published = 1 AND id != ? AND "
        "(category_id = ? OR is_featured = 1) ORDER BY sort_order LIMIT 3",
        (row["id"], row["category_id"]))
    plans = emi_core.plans_payload(float(row["price_from"] or 0) or 40000)
    return render_template(
        "public/service.html", s=row, related=related, plans=plans,
        services=published_services(40), branches=published_branches(),
        slots=settings.get("enquiry.slots", []),
        faqs=db.query("SELECT * FROM faqs WHERE is_published = 1 ORDER BY sort_order LIMIT 5"),
        meta_title=f"{row['name']} in Pune | {settings.get('seo.title_suffix')}",
        meta_description=row["summary"] or settings.get("seo.default_description"),
        og_url=media.media_url(row["media_id"], "medium"),
    )


@bp.route("/thank-you")
def thanks():
    return render_template(
        "public/thanks.html",
        ref=request.args.get("ref", ""),
        kind=request.args.get("kind", "enquiry"),
        title=settings.get("enquiry.success_title"),
        body=settings.get("enquiry.success_body"),
        meta_title=f"Thank you | {settings.get('seo.title_suffix')}",
        meta_description="",
    )


@bp.route("/<slug>")
def page(slug):
    row = db.one("SELECT * FROM pages WHERE slug = ? AND is_published = 1", (slug,))
    if not row:
        abort(404)
    if row["is_home"]:
        return redirect(url_for("public.home"))
    return _render_page(row)


# ── enquiry form ────────────────────────────────────────────────────────────
def _recent_from(ip: str) -> int:
    return int(db.scalar(
        "SELECT COUNT(*) FROM enquiries WHERE ip = ? AND created_at > datetime('now', '-1 hour')",
        (ip,), 0))


def _too_many() -> str | None:
    """A refusal reason when we should not write another row at all.

    The soft flag below keeps genuine-but-noisy submissions; this is the stop that
    keeps an automated flood from filling the table.
    """
    if _recent_from(client_ip()) >= HARD_LIMIT_PER_IP_PER_HOUR:
        return "Too many submissions from your connection in the last hour. Please phone us instead."
    site_total = int(db.scalar(
        "SELECT COUNT(*) FROM enquiries WHERE created_at > datetime('now', '-1 hour')", (), 0))
    if site_total >= HARD_LIMIT_PER_HOUR:
        return "We are getting an unusual number of submissions. Please phone us instead."
    return None


def form_stamp() -> str:
    """A signed 'this form was served at' token, rendered into every public form.

    Signed rather than kept in the session so it survives a visitor with no
    JavaScript, and cannot be omitted: a post without a valid stamp is treated as
    automated instead of skipping the check.
    """
    return URLSafeTimedSerializer(current_app.secret_key, salt="public-form").dumps("f")


def _stamp_problem(raw: str) -> str | None:
    if not raw:
        return "no form token"
    reader = URLSafeTimedSerializer(current_app.secret_key, salt="public-form")
    try:
        _, issued = reader.loads(raw, max_age=FORM_TOKEN_MAX_AGE, return_timestamp=True)
    except SignatureExpired:
        return "form left open too long"
    except BadSignature:
        return "form token did not verify"
    if (datetime.now(timezone.utc) - issued).total_seconds() < MIN_FORM_SECONDS:
        return "submitted too fast"
    return None


def _spam_check(form) -> str | None:
    """Returns a reason string when the submission looks automated. The enquiry is
    still stored either way, flagged rather than silently dropped."""
    if form.get("website"):  # honeypot field, hidden from people
        return "honeypot"

    stamp = _stamp_problem(form.get("form_token") or "")
    if stamp:
        return stamp

    if _recent_from(client_ip()) >= MAX_ENQUIRIES_PER_IP_PER_HOUR:
        return "rate limit"
    return None


@bp.route("/enquiry", methods=["POST"])
def enquiry():
    verify_csrf()
    form = request.form
    name = (form.get("name") or "").strip()
    phone = (form.get("phone") or "").strip()
    email = (form.get("email") or "").strip()

    errors = []
    if len(name) < 2:
        errors.append("Please give us a name.")
    if not valid_phone(phone):
        errors.append("Please give a phone number we can call you back on.")
    if email and not valid_email(email):
        errors.append("That email address does not look right.")

    if errors:
        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify({"ok": False, "errors": errors}), 400
        return redirect((form.get("source_page") or "/") + "#enquiry")

    refuse = _too_many()
    if refuse:
        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify({"ok": False, "errors": [refuse]}), 429
        return redirect((form.get("source_page") or "/") + "#enquiry")

    spam = _spam_check(form)
    ip = client_ip()
    ref = ref_code("ENQ")

    utm = {k: v for k, v in request.args.items() if k.startswith("utm_")}
    utm.update({k[4:]: v for k, v in form.items() if k.startswith("utm_")})

    with db.transaction():
        enquiry_id = db.insert("enquiries", {
            "ref": ref,
            "name": name[:120],
            "phone": clean_phone(phone)[:20],
            "email": email[:160],
            "service_id": parse_int(form.get("service_id"), 0) or None,
            "branch_id": parse_int(form.get("branch_id"), 0) or None,
            "preferred_date": (form.get("preferred_date") or "")[:20],
            "preferred_time": (form.get("preferred_time") or "")[:60],
            "message": (form.get("message") or "")[:2000],
            "status": "new",
            "priority": "high" if form.get("urgent") else "normal",
            "source_page": (form.get("source_page") or request.referrer or "/")[:200],
            "utm": dump_json(utm),
            "ip": ip[:60],
            "user_agent": (request.headers.get("User-Agent") or "")[:250],
            "is_spam": 1 if spam else 0,
        })
        db.insert("enquiry_events", {
            "enquiry_id": enquiry_id, "type": "created",
            "note": f"Submitted from {form.get('source_page') or '/'}"
                    + (f" (flagged: {spam})" if spam else ""),
        })

    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True, "ref": ref,
                        "title": settings.get("enquiry.success_title"),
                        "body": settings.get("enquiry.success_body")})
    return redirect(url_for("public.thanks", ref=ref, kind="enquiry"))


# ── EMI ─────────────────────────────────────────────────────────────────────
@bp.route("/api/rating")
def api_rating():
    """Rating summary for the hero. Uses the cache, so it costs nothing per view."""
    bundle = google_reviews.get_bundle("auto", 5)
    return jsonify({
        "rating": bundle.rating,
        "total": bundle.total,
        "source": bundle.source,
        "maps_url": bundle.maps_url,
    })


@bp.route("/emi/quote")
def emi_quote():
    amount = parse_float(request.args.get("amount"), 0)
    return jsonify({
        "amount": amount,
        "plans": emi_core.plans_payload(amount),
        "note": settings.get("emi.note"),
    })


@bp.route("/emi/apply", methods=["POST"])
def emi_apply():
    verify_csrf()
    form = request.form
    name = (form.get("applicant_name") or "").strip()
    phone = (form.get("phone") or "").strip()
    amount = parse_float(form.get("treatment_amount"), 0)
    plan_id = parse_int(form.get("plan_id"), 0)

    plan = db.one("SELECT * FROM emi_plans WHERE id = ? AND is_active = 1", (plan_id,))
    errors = []
    if len(name) < 2:
        errors.append("Please give us a name.")
    if not valid_phone(phone):
        errors.append("Please give a phone number we can call you back on.")
    if amount <= 0:
        errors.append("Tell us the treatment amount.")
    if not plan:
        errors.append("Pick one of the plans.")
    elif not emi_core.plan_eligible(plan, amount):
        errors.append(f"{plan['name']} does not cover that amount.")

    if errors:
        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify({"ok": False, "errors": errors}), 400
        return redirect("/emi-and-payment#calculator")

    refuse = _too_many()
    if refuse:
        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify({"ok": False, "errors": [refuse]}), 429
        return redirect("/emi-and-payment#calculator")

    spam = _spam_check(form)
    q = emi_core.quote_for_plan(amount, plan)
    service_id = parse_int(form.get("service_id"), 0) or None
    service_row = db.one("SELECT name FROM services WHERE id = ?", (service_id,)) if service_id else None
    ref = emi_core.new_application_ref()

    with db.transaction():
        app_id = db.insert("emi_applications", {
            "ref": ref, "applicant_name": name[:120], "phone": clean_phone(phone)[:20],
            "email": ((form.get("email") or "").strip())[:160], "service_id": service_id,
            "treatment_label": service_row["name"] if service_row else (form.get("treatment_label") or "")[:120],
            "treatment_amount": amount, "plan_id": plan["id"], "plan_label": plan["name"],
            "tenure_months": plan["tenure_months"], "interest_rate": plan["interest_rate"],
            "processing_fee": q["processing_fee"], "downpayment": q["downpayment"],
            "financed": q["financed"], "monthly_emi": q["monthly_emi"],
            "total_payable": q["total_payable"], "status": "submitted",
            "start_date": date.today().isoformat(),
            "notes": (form.get("message") or "")[:1000],
        })

        # a matching enquiry so the front desk sees it in one list
        enq_id = db.insert("enquiries", {
            "ref": ref_code("ENQ"), "name": name[:120], "phone": clean_phone(phone)[:20],
            "email": ((form.get("email") or "").strip())[:160], "service_id": service_id,
            "message": f"EMI application {ref}: {plan['name']} on "
                       f"{int(amount)} rupees, {int(q['monthly_emi'])} a month.",
            "status": "new", "priority": "high", "source_page": "/emi-and-payment",
            "utm": dump_json({}), "ip": client_ip()[:60],
            "user_agent": (request.headers.get("User-Agent") or "")[:250],
            "is_spam": 1 if spam else 0,
        })
        db.insert("enquiry_events", {
            "enquiry_id": enq_id, "type": "emi",
            "note": f"EMI application {ref} submitted from the website."
                    + (f" (flagged: {spam})" if spam else ""),
        })
        db.update("emi_applications", app_id, {"enquiry_id": enq_id})

    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True, "ref": ref, "quote": q})
    return redirect(url_for("public.thanks", ref=ref, kind="emi"))


# ── google photo proxy ──────────────────────────────────────────────────────
PHOTO_NAME = re.compile(r"^places/[A-Za-z0-9_\-]+/photos/[A-Za-z0-9_\-]+$")


@bp.route("/media/google-photo/<path:photo_name>")
def google_photo(photo_name):
    """Serves a Place photo without exposing the API key and without storing the
    image, which is what Google's terms ask for.

    Only photos already imported into the media library are served. The key on the
    far end is billable, so an open proxy would let anyone spend it, and a free-form
    path would let them reach other endpoints on that host with our key attached.
    """
    api_key = settings.get("google.api_key", "")
    if not api_key or not settings.get("google.photos_enabled", False):
        abort(404)
    if not PHOTO_NAME.match(photo_name):
        abort(404)
    known = db.one("SELECT 1 FROM media WHERE url = ? AND source = 'google'",
                   (url_for("public.google_photo", photo_name=photo_name),))
    if not known:
        abort(404)
    ok, payload, mime = google_places.fetch_photo_bytes(api_key, photo_name)
    if not ok:
        abort(502)
    return Response(payload, mimetype=mime or "image/jpeg",
                    headers={"Cache-Control": "public, max-age=3600"})


# ── SEO ─────────────────────────────────────────────────────────────────────
@bp.route("/sitemap.xml")
def sitemap():
    urls = [request.url_root.rstrip("/") + "/"]
    for row in db.query("SELECT slug, is_home FROM pages WHERE is_published = 1 ORDER BY sort_order"):
        if not row["is_home"]:
            urls.append(request.url_root.rstrip("/") + "/" + row["slug"])
    for row in db.query("SELECT slug FROM services WHERE is_published = 1"):
        urls.append(request.url_root.rstrip("/") + "/treatments/" + row["slug"])

    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in urls:
        body.append(f"  <url><loc>{url}</loc></url>")
    body.append("</urlset>")
    return Response("\n".join(body), mimetype="application/xml")


@bp.route("/robots.txt")
def robots():
    if not settings.get("seo.indexable", True):
        return Response("User-agent: *\nDisallow: /\n", mimetype="text/plain")
    lines = ["User-agent: *", "Disallow: /admin", "Allow: /",
             f"Sitemap: {request.url_root.rstrip('/')}/sitemap.xml"]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")
