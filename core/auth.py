"""Authentication, roles, CSRF and login throttling — no third-party auth libs.

Roles
  owner  full access, including users, settings and the danger zone
  admin  everything content, reviews, enquiries and EMI
  staff  enquiries and EMI day-to-day work, no content or settings
"""

from __future__ import annotations

import hmac
import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from core import db

ROLES = ("owner", "admin", "staff")
ROLE_LABELS = {
    "owner": "Owner",
    "admin": "Administrator",
    "staff": "Front desk",
}

# What each role may reach; checked by require_role.
#
# "emi" is the day-to-day work: raise an application, take a payment, print a
# receipt. "emi_admin" is the money policy on top of it - plan terms, approving or
# rejecting an application, voiding a receipt, deleting a record - so the front
# desk cannot both set the terms and sign them off.
PERMISSIONS = {
    "owner": {"content", "media", "reviews", "enquiries", "emi", "emi_admin",
              "settings", "users", "audit"},
    "admin": {"content", "media", "reviews", "enquiries", "emi", "emi_admin",
              "settings", "audit"},
    "staff": {"enquiries", "emi"},
}

MAX_ATTEMPTS = 8            # per address
MAX_ATTEMPTS_EMAIL = 12     # per account, across addresses
ATTEMPT_WINDOW_MIN = 15

# Compared against when the email is unknown, so a missing account costs the same
# time as a wrong password and cannot be told apart by a stopwatch.
_DUMMY_HASH = generate_password_hash("not-a-real-password", method="pbkdf2:sha256:260000")


# ── users ───────────────────────────────────────────────────────────────────
def hash_password(raw: str) -> str:
    return generate_password_hash(raw, method="pbkdf2:sha256:260000")


def create_user(email: str, name: str, password: str, role: str = "staff") -> int:
    return db.insert(
        "users",
        {
            "email": email.strip().lower(),
            "name": name.strip(),
            "password_hash": hash_password(password),
            "role": role if role in ROLES else "staff",
            "is_active": 1,
        },
    )


def find_user(email: str):
    return db.one("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))


def current_user():
    if "user" not in g:
        g.user = None
        uid = session.get("uid")
        if uid:
            row = db.one("SELECT * FROM users WHERE id = ? AND is_active = 1", (uid,))
            g.user = row
    return g.user


def can(area: str) -> bool:
    user = current_user()
    if not user:
        return False
    return area in PERMISSIONS.get(user["role"], set())


# ── throttling ──────────────────────────────────────────────────────────────
def recent_failures(ip: str) -> int:
    return int(
        db.scalar(
            "SELECT COUNT(*) FROM login_attempts WHERE ip = ? AND ok = 0 "
            f"AND created_at > datetime('now', '-{ATTEMPT_WINDOW_MIN} minutes')",
            (ip,),
            0,
        )
    )


def recent_failures_for(email: str) -> int:
    """Counted separately so a distributed attempt on one account still trips."""
    return int(
        db.scalar(
            "SELECT COUNT(*) FROM login_attempts WHERE email = ? AND ok = 0 "
            f"AND created_at > datetime('now', '-{ATTEMPT_WINDOW_MIN} minutes')",
            (email.strip().lower()[:120],),
            0,
        )
    )


def record_attempt(ip: str, email: str, ok: bool) -> None:
    db.insert("login_attempts", {"ip": ip, "email": email[:120], "ok": 1 if ok else 0})
    db.execute("DELETE FROM login_attempts WHERE created_at < datetime('now', '-2 days')")


def attempt_login(email: str, password: str, ip: str):
    """Returns (user_row, error_message)."""
    if recent_failures(ip) >= MAX_ATTEMPTS:
        return None, "Too many attempts from this address. Try again in 15 minutes."
    if recent_failures_for(email) >= MAX_ATTEMPTS_EMAIL:
        return None, "Too many attempts on that account. Try again in 15 minutes."

    user = find_user(email)
    if not user or not user["is_active"]:
        check_password_hash(_DUMMY_HASH, password)   # keep the timing flat
        record_attempt(ip, email, False)
        return None, "Those details do not match an active account."
    if not check_password_hash(user["password_hash"], password):
        record_attempt(ip, email, False)
        return None, "Those details do not match an active account."

    record_attempt(ip, email, True)
    session.clear()
    session["uid"] = user["id"]
    session["csrf"] = secrets.token_urlsafe(32)
    session.permanent = True
    db.update("users", user["id"], {"last_login_at": db.scalar("SELECT datetime('now')")})
    return user, None


def logout() -> None:
    session.clear()


# ── CSRF ────────────────────────────────────────────────────────────────────
def csrf_token() -> str:
    token = session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf"] = token
    return token


def csrf_ok() -> bool:
    sent = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token", "")
    return bool(sent) and hmac.compare_digest(sent, session.get("csrf", ""))


def verify_csrf() -> None:
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and not csrf_ok():
        abort(400, "The form expired or the security token did not match. Please try again.")


# ── decorators ──────────────────────────────────────────────────────────────
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("admin.login", next=request.full_path))
        return view(*args, **kwargs)

    return wrapper


def require_role(*areas: str):
    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if not current_user():
                return redirect(url_for("admin.login", next=request.full_path))
            if areas and not any(can(a) for a in areas):
                flash("Your account does not have access to that area.", "error")
                return redirect(url_for("admin.dashboard"))
            return view(*args, **kwargs)

        return wrapper

    return decorator


def bootstrap_owner(app) -> None:
    """Create the first owner account if the table is empty.

    With no password configured one is generated and written to db/first-login.txt
    rather than falling back to a default that is the same in every copy of this
    codebase, which anyone reading the source could use.
    """
    from pathlib import Path

    with app.app_context():
        count = int(db.scalar("SELECT COUNT(*) FROM users", (), 0))
        if count:
            return
        email = app.config.get("OWNER_EMAIL") or "owner@example.com"
        name = app.config.get("OWNER_NAME") or "Practice Owner"
        password = app.config.get("OWNER_PASSWORD") or ""
        generated = not password
        if generated:
            password = secrets.token_urlsafe(12)

        create_user(email, name, password, "owner")
        if generated:
            note = Path(app.root_path) / "db" / "first-login.txt"
            note.parent.mkdir(parents=True, exist_ok=True)
            note.write_text(f"{email}\n{password}\n", encoding="utf-8")
            print("\n  First login")
            print(f"    {email}")
            print(f"    {password}")
            print(f"  Also written to {note.relative_to(Path(app.root_path))}. "
                  "Change it and delete that file.\n")
        app.logger.warning("Created first owner account: %s", email)
