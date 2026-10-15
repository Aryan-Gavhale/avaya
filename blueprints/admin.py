"""Admin shell: sign in, dashboard, users, audit log, backup.

The feature areas live in sibling modules that attach their routes to the same
blueprint. They are imported at the bottom of this file, after `bp` exists.
"""

from __future__ import annotations

import io
import os
import shutil
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (Blueprint, abort, current_app, flash, redirect,
                   render_template, request, send_file, session, url_for)

from core import audit, auth, db, media, settings
from core.auth import (ROLES, current_user, login_required, require_role,
                       verify_csrf)
from core.util import client_ip, parse_int, valid_email
from services import google_reviews

bp = Blueprint("admin", __name__)

NAV_GROUPS = [
    ("Overview", [
        ("admin.dashboard", "Dashboard", "grid", None),
    ]),
    ("Patients", [
        ("admin.enquiries_list", "Enquiries", "inbox", "enquiries"),
        ("admin.emi_applications", "EMI applications", "wallet", "emi"),
        ("admin.emi_plans_list", "EMI plans", "percent", "emi_admin"),
        ("admin.emi_ledger", "Payments ledger", "receipt", "emi"),
    ]),
    ("Practice", [
        ("admin.settings_home", "Settings", "sliders", "settings"),
        ("admin.users_list", "Staff accounts", "users", "users"),
        ("admin.audit_list", "Activity log", "clock", "audit"),
        ("admin.backup_home", "Backup", "database", "settings"),
    ]),
    ("Website", [
        ("admin.pages_list", "Pages and sections", "layout", "content"),
        ("admin.services_list", "Treatments", "tooth", "content"),
        ("admin.service_categories_list", "Treatment categories", "folder", "content"),
        ("admin.doctors_list", "Clinicians", "user", "content"),
        ("admin.branches_list", "Clinics", "pin", "content"),
        ("admin.faqs_list", "FAQs", "help", "content"),
        ("admin.nav_items_list", "Menus", "menu", "content"),
    ]),
    ("Media and reviews", [
        ("admin.media_library", "Media library", "image", "media"),
        ("admin.galleries_list", "Galleries", "images", "media"),
        ("admin.reviews_home", "Google reviews", "star", "reviews"),
        ("admin.testimonials_list", "Curated quotes", "quote", "reviews"),
    ]),
]

# Groups the practice opens a few times a month, not a few times an hour. They sit
# last and fold away, so the daily work stays at the top of the sidebar.
NAV_FOLDED = {"Website", "Media and reviews"}
AUDIT_PER_PAGE = 25


@bp.context_processor
def admin_context():
    user = current_user()
    return {
        "nav_groups": NAV_GROUPS,
        "nav_folded": NAV_FOLDED,
        "admin_theme": {key: settings.colour(f"admin.{key}")
                        for key in ("accent", "canvas", "sidebar", "ink")},
        "admin_user": user,
        "brand_name": settings.get("brand.name"),
        "today": date.today(),
        "new_enquiries": db.scalar(
            "SELECT COUNT(*) FROM enquiries WHERE status = 'new' AND is_spam = 0", (), 0
        ) if user else 0,
    }


# ── auth ────────────────────────────────────────────────────────────────────
@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect(url_for("admin.dashboard"))

    error = None
    if request.method == "POST":
        verify_csrf()
        ip = client_ip()
        user, error = auth.attempt_login(
            request.form.get("email", ""), request.form.get("password", ""), ip)
        if user:
            audit.log("login", "users", user["id"], user["email"])
            nxt = request.args.get("next") or request.form.get("next") or ""
            if nxt.startswith("/admin"):
                return redirect(nxt)
            return redirect(url_for("admin.dashboard"))

    return render_template("admin/login.html", error=error,
                           next=request.args.get("next", ""),
                           title="Sign in")


@bp.route("/logout", methods=["POST"])
def logout():
    verify_csrf()
    user = current_user()
    if user:
        audit.log("logout", "users", user["id"], user["email"])
    auth.logout()
    flash("Signed out.", "ok")
    return redirect(url_for("admin.login"))


# ── dashboard ───────────────────────────────────────────────────────────────
@bp.route("/")
@login_required
def dashboard():
    user = current_user()
    scope = {}

    scope["enq_today"] = db.scalar(
        "SELECT COUNT(*) FROM enquiries WHERE date(created_at) = date('now') AND is_spam = 0", (), 0)
    scope["enq_week"] = db.scalar(
        "SELECT COUNT(*) FROM enquiries WHERE created_at > datetime('now', '-7 days') AND is_spam = 0", (), 0)
    scope["enq_new"] = db.scalar(
        "SELECT COUNT(*) FROM enquiries WHERE status = 'new' AND is_spam = 0", (), 0)
    scope["enq_total"] = db.scalar("SELECT COUNT(*) FROM enquiries WHERE is_spam = 0", (), 0)

    scope["by_status"] = db.query(
        "SELECT status, COUNT(*) AS n FROM enquiries WHERE is_spam = 0 GROUP BY status")
    scope["latest"] = db.query(
        "SELECT e.*, s.name AS service_name, b.name AS branch_name FROM enquiries e "
        "LEFT JOIN services s ON s.id = e.service_id "
        "LEFT JOIN branches b ON b.id = e.branch_id "
        "WHERE e.is_spam = 0 ORDER BY e.id DESC LIMIT 6")

    scope["emi_apps"] = db.scalar("SELECT COUNT(*) FROM emi_applications", (), 0)
    scope["emi_pending"] = db.scalar(
        "SELECT COUNT(*) FROM emi_applications WHERE status IN ('submitted', 'under_review')", (), 0)
    scope["emi_outstanding"] = db.scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM emi_installments WHERE status = 'due'", (), 0)
    scope["emi_overdue"] = db.scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM emi_installments "
        "WHERE status = 'due' AND due_date < date('now')", (), 0)
    scope["emi_overdue_n"] = db.scalar(
        "SELECT COUNT(*) FROM emi_installments WHERE status = 'due' AND due_date < date('now')", (), 0)
    scope["collected_month"] = db.scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM payments "
        "WHERE status = 'paid' AND strftime('%Y-%m', paid_at) = strftime('%Y-%m', 'now')", (), 0)
    scope["due_30"] = db.query(
        "SELECT i.*, a.applicant_name, a.ref FROM emi_installments i "
        "JOIN emi_applications a ON a.id = i.application_id "
        "WHERE i.status = 'due' AND i.due_date <= date('now', '+30 days') "
        "ORDER BY i.due_date LIMIT 8")

    scope["content"] = {
        "pages": db.scalar("SELECT COUNT(*) FROM pages", (), 0),
        "sections": db.scalar("SELECT COUNT(*) FROM sections WHERE is_published = 1", (), 0),
        "services": db.scalar("SELECT COUNT(*) FROM services WHERE is_published = 1", (), 0),
        "media": db.scalar("SELECT COUNT(*) FROM media", (), 0),
        "drafts": db.scalar("SELECT COUNT(*) FROM sections WHERE is_published = 0", (), 0),
    }

    scope["reviews"] = google_reviews.connection_state()
    scope["activity"] = audit.recent(12)
    scope["is_staff"] = user["role"] == "staff"
    return render_template("admin/dashboard.html", title="Dashboard", d=scope)


# ── users ───────────────────────────────────────────────────────────────────
@bp.route("/users")
@require_role("users")
def users_list():
    rows = db.query("SELECT * FROM users ORDER BY role, name")
    return render_template("admin/users.html", rows=rows, title="Staff accounts")


@bp.route("/users/save", methods=["POST"])
@require_role("users")
def users_save():
    verify_csrf()
    user_id = parse_int(request.form.get("id"), 0)
    email = (request.form.get("email") or "").strip().lower()
    name = (request.form.get("name") or "").strip()
    role = request.form.get("role") or "staff"
    password = request.form.get("password") or ""
    active = 1 if request.form.get("is_active") else 0

    if role not in ROLES:
        role = "staff"
    if not valid_email(email) or len(name) < 2:
        flash("A name and a valid email address are needed.", "error")
        return redirect(url_for("admin.users_list"))

    existing = db.one("SELECT * FROM users WHERE email = ? AND id != ?", (email, user_id or 0))
    if existing:
        flash("Another account already uses that email address.", "error")
        return redirect(url_for("admin.users_list"))

    if user_id:
        row = db.one("SELECT * FROM users WHERE id = ?", (user_id,))
        if not row:
            abort(404)
        data = {"email": email, "name": name, "role": role, "is_active": active}
        if password:
            data["password_hash"] = auth.hash_password(password)
        owners = db.scalar("SELECT COUNT(*) FROM users WHERE role = 'owner' AND is_active = 1", (), 0)
        if row["role"] == "owner" and (role != "owner" or not active) and owners <= 1:
            flash("There has to be one active owner account.", "error")
            return redirect(url_for("admin.users_list"))
        db.update("users", user_id, data)
        audit.log("update", "users", user_id, email, before=row, after=data)
        flash("Account updated.", "ok")
    else:
        if len(password) < 8:
            flash("New accounts need a password of at least 8 characters.", "error")
            return redirect(url_for("admin.users_list"))
        new_id = auth.create_user(email, name, password, role)
        audit.log("create", "users", new_id, email)
        flash("Account created.", "ok")
    return redirect(url_for("admin.users_list"))


@bp.route("/users/<int:row_id>/delete", methods=["POST"])
@require_role("users")
def users_delete(row_id):
    verify_csrf()
    row = db.one("SELECT * FROM users WHERE id = ?", (row_id,))
    if not row:
        abort(404)
    me = current_user()
    if me and me["id"] == row_id:
        flash("You cannot delete the account you are signed in with.", "error")
        return redirect(url_for("admin.users_list"))
    owners = db.scalar("SELECT COUNT(*) FROM users WHERE role = 'owner' AND is_active = 1", (), 0)
    if row["role"] == "owner" and owners <= 1:
        flash("There has to be one active owner account.", "error")
        return redirect(url_for("admin.users_list"))
    db.delete("users", row_id)
    audit.log("delete", "users", row_id, row["email"], before=row)
    flash("Account deleted.", "ok")
    return redirect(url_for("admin.users_list"))


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    user = current_user()
    if request.method == "POST":
        verify_csrf()
        name = (request.form.get("name") or "").strip()
        current = request.form.get("current_password") or ""
        new = request.form.get("new_password") or ""
        data = {}
        if name and name != user["name"]:
            data["name"] = name
        if new:
            from werkzeug.security import check_password_hash
            if not check_password_hash(user["password_hash"], current):
                flash("Your current password did not match.", "error")
                return redirect(url_for("admin.account"))
            if len(new) < 8:
                flash("Use at least 8 characters.", "error")
                return redirect(url_for("admin.account"))
            data["password_hash"] = auth.hash_password(new)
        if data:
            db.update("users", user["id"], data)
            audit.log("update", "users", user["id"], user["email"], after={"self": list(data)})
            flash("Your account was updated.", "ok")
        return redirect(url_for("admin.account"))
    return render_template("admin/account.html", title="Your account")


# ── audit ───────────────────────────────────────────────────────────────────
@bp.route("/activity")
@require_role("audit")
def audit_list():
    action = request.args.get("action", "")
    entity = request.args.get("entity", "")
    where = " WHERE 1 = 1"
    args: list = []
    if action:
        where += " AND action = ?"
        args.append(action)
    if entity:
        where += " AND entity = ?"
        args.append(entity)
    total = db.one("SELECT COUNT(*) AS n FROM audit_log" + where, args)["n"]
    pages = max(1, -(-total // AUDIT_PER_PAGE))
    page = min(max(request.args.get("page", 1, type=int) or 1, 1), pages)
    rows = db.query(f"SELECT * FROM audit_log{where} ORDER BY id DESC LIMIT ? OFFSET ?",
                    args + [AUDIT_PER_PAGE, (page - 1) * AUDIT_PER_PAGE])
    return render_template(
        "admin/audit.html", title="Activity log", rows=rows,
        actions=db.query("SELECT DISTINCT action FROM audit_log ORDER BY action"),
        entities=db.query("SELECT DISTINCT entity FROM audit_log ORDER BY entity"),
        action=action, entity=entity, page=page, pages=pages, total=total,
        per_page=AUDIT_PER_PAGE,
    )


# ── backup ──────────────────────────────────────────────────────────────────
@bp.route("/backup")
@require_role("settings")
def backup_home():
    folder = Path(current_app.root_path) / "backups"
    folder.mkdir(exist_ok=True)
    files = sorted(folder.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return render_template(
        "admin/backup.html", title="Backup and restore",
        files=[{"name": f.name, "size": f.stat().st_size,
                "when": datetime.fromtimestamp(f.stat().st_mtime)} for f in files[:20]],
        db_size=db.db_file_size(),
        media_count=db.scalar("SELECT COUNT(*) FROM media", (), 0),
        upload_size=_upload_size(),
    )


def _upload_size() -> int:
    total = 0
    try:
        for path in media.upload_dir().glob("*"):
            if path.is_file():
                total += path.stat().st_size
    except OSError:
        pass
    return total


@bp.route("/backup/create", methods=["POST"])
@require_role("settings")
def backup_create():
    verify_csrf()
    folder = Path(current_app.root_path) / "backups"
    folder.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = folder / f"clinic-backup-{stamp}.zip"

    db_path = Path(db.db_file_path())
    snapshot = folder / "_snapshot.db"
    source = db.connect(str(db_path))
    dest = db.connect(str(snapshot))
    try:
        source.backup(dest)   # consistent copy even while the app is serving
    finally:
        dest.close()
        source.close()

    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(snapshot, "clinic.db")
        for path in media.upload_dir().glob("*"):
            if path.is_file():
                archive.write(path, f"uploads/{path.name}")
    snapshot.unlink(missing_ok=True)

    audit.log("backup", "system", "", target.name)
    flash(f"Backup written: {target.name}", "ok")
    return redirect(url_for("admin.backup_home"))


@bp.route("/backup/download/<name>")
@require_role("settings")
def backup_download(name):
    safe = os.path.basename(name)
    path = Path(current_app.root_path) / "backups" / safe
    if not path.exists() or path.suffix != ".zip":
        abort(404)
    return send_file(path, as_attachment=True, download_name=safe)


@bp.route("/backup/delete/<name>", methods=["POST"])
@require_role("settings")
def backup_delete(name):
    verify_csrf()
    safe = os.path.basename(name)
    path = Path(current_app.root_path) / "backups" / safe
    if path.exists() and path.suffix == ".zip":
        path.unlink()
        audit.log("delete", "backup", "", safe)
        flash("Backup deleted.", "ok")
    return redirect(url_for("admin.backup_home"))


@bp.route("/backup/restore", methods=["POST"])
@require_role("settings")
def backup_restore():
    verify_csrf()
    upload = request.files.get("archive")
    if not upload or not upload.filename.endswith(".zip"):
        flash("Choose a .zip backup produced by this panel.", "error")
        return redirect(url_for("admin.backup_home"))

    payload = io.BytesIO(upload.read())
    try:
        with zipfile.ZipFile(payload) as archive:
            names = archive.namelist()
            if "clinic.db" not in names:
                flash("That archive does not contain clinic.db.", "error")
                return redirect(url_for("admin.backup_home"))

            db_path = Path(db.db_file_path())
            shutil.copy2(db_path, db_path.with_suffix(".db.pre-restore"))
            db.close_db()
            with archive.open("clinic.db") as source, open(db_path, "wb") as target:
                shutil.copyfileobj(source, target)

            folder = media.upload_dir()
            for name in names:
                if name.startswith("uploads/") and not name.endswith("/"):
                    with archive.open(name) as source:
                        (folder / os.path.basename(name)).write_bytes(source.read())
    except zipfile.BadZipFile:
        flash("That file is not a readable zip archive.", "error")
        return redirect(url_for("admin.backup_home"))

    session.clear()
    flash("Database restored from the archive. Please sign in again.", "ok")
    return redirect(url_for("admin.login"))


# ── feature modules ─────────────────────────────────────────────────────────
from blueprints import (admin_content, admin_emi, admin_enquiries,  # noqa: E402
                        admin_media, admin_reviews, admin_settings)

admin_content.register(bp)
admin_media.register(bp)
admin_reviews.register(bp)
admin_enquiries.register(bp)
admin_emi.register(bp)
admin_settings.register(bp)
