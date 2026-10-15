"""Dental clinic site + admin CMS.

    python app.py            run the dev server
    python app.py seed       apply the schema and load the demo clinic
    python app.py reset      delete the database, then seed
    python app.py user       add or update an admin account

Nothing on the public page is hard-coded; every heading, image, service and
colour is a row in SQLite that the admin panel edits.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path

from flask import Flask, g, render_template, request

from core import auth, db, media, settings, util

ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = {
    "secret_key": "",           # blank means: generate one and keep it in db/secret.key
    "host": "127.0.0.1",
    "port": 8120,
    "debug": False,             # the Werkzeug debugger is a remote shell; opt in, never default
    "db_path": "db/clinic.db",
    "upload_dir": "static/uploads",
    "max_upload_mb": 12,
    "owner_email": "owner@anvayadental.in",
    "owner_password": "",       # blank means: generate one and print it once
    "owner_name": "Practice Owner",
    "google_verify_tls": True,
    "https_only": False,        # set true behind TLS so the session cookie is Secure
    "trusted_proxies": 0,       # hops of X-Forwarded-For we put there ourselves
}


def _secret_key() -> str:
    """A per-installation key, generated on first boot and kept out of git.

    Held in a file rather than the database so sessions survive a reset, and
    generated rather than shipped so no two installations share a key that would
    let anyone forge an admin cookie.
    """
    path = ROOT / "db" / "secret.key"
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    generated = secrets.token_urlsafe(48)
    path.write_text(generated, encoding="utf-8")
    print(f"[config] generated a new secret key in {path.relative_to(ROOT)}")
    return generated


def load_config() -> dict:
    """Defaults, overridden by config.json, overridden by CLINIC_* in the env.

    config.example.json is deliberately not read: a placeholder secret key should
    never become the live one just because nobody copied the file.
    """
    data = dict(DEFAULT_CONFIG)
    path = ROOT / "config.json"
    if path.exists():
        try:
            data.update(json.loads(path.read_text(encoding="utf-8")))
        except ValueError as exc:
            print(f"[config] ignoring config.json: {exc}")
    for key in list(data):
        env = os.environ.get("CLINIC_" + key.upper())
        if env is not None:
            data[key] = env
    return data


def create_app() -> Flask:
    cfg = load_config()
    app = Flask(__name__, static_folder="static", template_folder="templates")

    app.secret_key = str(cfg["secret_key"]) or _secret_key()
    https_only = util.parse_bool(cfg["https_only"])
    app.config.update(
        DB_PATH=cfg["db_path"],
        UPLOAD_DIR=cfg["upload_dir"],
        OWNER_EMAIL=cfg["owner_email"],
        OWNER_PASSWORD=cfg["owner_password"],
        OWNER_NAME=cfg["owner_name"],
        HOST=cfg["host"],
        PORT=int(cfg["port"]),
        GOOGLE_VERIFY_TLS=util.parse_bool(cfg["google_verify_tls"]),
        TRUSTED_PROXIES=int(cfg["trusted_proxies"] or 0),
        HTTPS_ONLY=https_only,
        MAX_CONTENT_LENGTH=int(cfg["max_upload_mb"]) * 1024 * 1024,
        PERMANENT_SESSION_LIFETIME=timedelta(days=14),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=https_only,
        # a template edit should show on the next reload while working locally;
        # the debugger stays off, since that is a different and far riskier switch
        TEMPLATES_AUTO_RELOAD=(util.parse_bool(cfg["debug"])
                               or str(cfg["host"]) in ("127.0.0.1", "localhost")),
        JSON_SORT_KEYS=False,
    )

    if util.parse_bool(cfg["debug"]) and str(cfg["host"]) not in ("127.0.0.1", "localhost"):
        print(f"[config] refusing to expose the debugger on {cfg['host']}: debug forced off. "
              "The Werkzeug console executes code for anyone who can reach it.")
        cfg["debug"] = False

    db.init_app(app)
    with app.app_context():
        settings.ensure_defaults()
    auth.bootstrap_owner(app)

    register_jinja(app)
    register_blueprints(app)
    register_headers(app)
    register_errors(app)
    return app


# ── template helpers ────────────────────────────────────────────────────────
def register_jinja(app: Flask) -> None:
    from blueprints.public import form_stamp
    from core import crud
    from core import sections as sections_mod

    app.jinja_env.trim_blocks = True
    app.jinja_env.lstrip_blocks = True

    app.add_template_filter(util.money, "money")
    app.add_template_filter(util.inr, "inr")
    app.add_template_filter(util.pretty_date, "date_fmt")
    app.add_template_filter(util.pretty_datetime, "datetime_fmt")
    app.add_template_filter(util.time_ago, "ago")
    app.add_template_filter(util.truncate, "shorten")
    app.add_template_filter(util.initials, "initials")
    app.add_template_filter(util.split_list, "as_list")
    app.add_template_filter(util.load_json, "from_json")
    app.add_template_filter(util.slugify, "slugify")

    @app.template_filter("paragraphs")
    def paragraphs(value):
        blocks = [b.strip() for b in str(value or "").split("\n\n") if b.strip()]
        return [b.replace("\n", " ") for b in blocks]

    # Helpers go in globals rather than a context processor, because a macro
    # imported without "with context" cannot see context values, and every admin
    # form is built out of macros.
    app.jinja_env.globals.update(
        S=settings.get,
        csrf_token=auth.csrf_token,
        form_stamp=form_stamp,
        current_user=auth.current_user,
        can=auth.can,
        media_url=media.media_url,
        media_alt=media.media_alt,
        media_row=media.get,
        field_value=crud.form_value,
        SECTION_TYPES=sections_mod.SECTION_TYPES,
        section_fields=sections_mod.fields_for,
        type_label=sections_mod.type_label,
        ROLE_LABELS=auth.ROLE_LABELS,
    )

    @app.context_processor
    def inject():
        theme = settings.group("theme")
        for key in ("primary", "primary_dark", "accent", "ink", "muted", "surface", "canvas"):
            theme[key] = settings.colour(f"theme.{key}")
        return {
            "brand": settings.group("brand"),
            "contact": settings.group("contact"),
            "theme": theme,
            "social": settings.group("social"),
        }

    @app.before_request
    def _touch():
        g.request_path = request.path
        g.csp_nonce = secrets.token_urlsafe(16)

    app.jinja_env.globals["csp_nonce"] = lambda: getattr(g, "csp_nonce", "")


def register_headers(app: Flask) -> None:
    """Headers every response carries.

    Styles stay 'unsafe-inline' because the theme colours are database rows written
    into a <style> block; scripts do not, so the handful of inline blocks in the
    admin templates carry a per-request nonce instead.
    """
    def policy(nonce: str) -> str:
        return (
            "default-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https:; "
            "connect-src 'self'"
        )

    @app.after_request
    def _headers(response):
        response.headers.setdefault("Content-Security-Policy",
                                    policy(getattr(g, "csp_nonce", "")))
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy",
                                    "geolocation=(), microphone=(), camera=()")
        if app.config.get("HTTPS_ONLY"):
            response.headers.setdefault("Strict-Transport-Security",
                                        "max-age=31536000; includeSubDomains")
        if request.path.startswith("/admin"):
            response.headers["Cache-Control"] = "no-store"
        return response


def register_blueprints(app: Flask) -> None:
    from blueprints.admin import bp as admin_bp
    from blueprints.public import bp as public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")


def register_errors(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(exc):
        return render_template("errors/error.html", code=400, title="That request looked wrong",
                               message=getattr(exc, "description", "")), 400

    @app.errorhandler(403)
    def forbidden(exc):
        return render_template("errors/error.html", code=403, title="Not your door",
                               message="Your account does not have access to that page."), 403

    @app.errorhandler(404)
    def not_found(exc):
        if request.path.startswith("/admin"):
            return render_template("errors/error.html", code=404, title="Nothing here",
                                   message="That admin page does not exist."), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(413)
    def too_large(exc):
        limit = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return render_template("errors/error.html", code=413, title="That file is too big",
                               message=f"Uploads are capped at {limit} MB per file."), 413

    @app.errorhandler(500)
    def server_error(exc):
        app.logger.exception("Unhandled error")
        return render_template("errors/error.html", code=500, title="Something broke",
                               message="The error has been logged. Try again."), 500


# ── CLI ─────────────────────────────────────────────────────────────────────
def _cli(argv: list[str]) -> int:
    command = argv[0] if argv else "serve"
    app = None

    if command == "reset":
        cfg = load_config()
        target = ROOT / cfg["db_path"]
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(target) + suffix)
            if candidate.exists():
                candidate.unlink()
                print(f"[reset] removed {candidate.name}")
        command = "seed"

    if command == "seed":
        app = create_app()
        from db.seed import run as seed_run
        with app.app_context():
            seed_run(force="--force" in argv)
        return 0

    if command == "user":
        app = create_app()
        if len(argv) < 4:
            print("usage: python app.py user <email> <name> <password> [role]")
            return 1
        email, name, password = argv[1], argv[2], argv[3]
        role = argv[4] if len(argv) > 4 else "admin"
        with app.app_context():
            existing = auth.find_user(email)
            if existing:
                db.update("users", existing["id"],
                          {"password_hash": auth.hash_password(password), "role": role,
                           "name": name, "is_active": 1})
                print(f"[user] updated {email} ({role})")
            else:
                auth.create_user(email, name, password, role)
                print(f"[user] created {email} ({role})")
        return 0

    app = create_app()
    host, port = app.config["HOST"], app.config["PORT"]
    debug = load_config()["debug"]
    print(f"  Public site   http://{host}:{port}/")
    print(f"  Admin panel   http://{host}:{port}/admin")
    print(f"  First login   {app.config['OWNER_EMAIL']}")
    app.run(host=host, port=port, debug=debug, threaded=True,
            use_reloader=debug and "--no-reload" not in argv)
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
