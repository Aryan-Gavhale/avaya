"""Enquiries: a small CRM. Filterable list, bulk actions, CSV export, and a
detail view with a timeline, internal notes, assignment and status workflow."""

from __future__ import annotations

import csv
import io
from datetime import date

from flask import (Response, abort, flash, redirect, render_template, request,
                   url_for)

from core import audit, db, emi as emi_core, settings
from core.auth import current_user, require_role, verify_csrf
from core.util import csv_cell, load_json, parse_float, parse_int

STATUSES = [
    ("new", "New"),
    ("contacted", "Contacted"),
    ("booked", "Appointment booked"),
    ("treated", "Treated"),
    ("closed", "Closed"),
    ("lost", "Lost"),
]
STATUS_TONE = {"new": "info", "contacted": "warn", "booked": "good", "treated": "good",
               "closed": "neutral", "lost": "bad"}
PRIORITIES = [("low", "Low"), ("normal", "Normal"), ("high", "High")]
PER_PAGE = 25


def _filters():
    return {
        "status": request.args.get("status", ""),
        "priority": request.args.get("priority", ""),
        "service": request.args.get("service", ""),
        "branch": request.args.get("branch", ""),
        "assignee": request.args.get("assignee", ""),
        "range": request.args.get("range", ""),
        "q": (request.args.get("q") or "").strip(),
        "spam": request.args.get("spam", ""),
    }


def _where(f: dict) -> tuple[str, list]:
    sql = " WHERE e.is_spam = " + ("1" if f["spam"] else "0")
    args: list = []
    if f["status"]:
        sql += " AND e.status = ?"
        args.append(f["status"])
    if f["priority"]:
        sql += " AND e.priority = ?"
        args.append(f["priority"])
    if f["service"]:
        sql += " AND e.service_id = ?"
        args.append(parse_int(f["service"], 0))
    if f["branch"]:
        sql += " AND e.branch_id = ?"
        args.append(parse_int(f["branch"], 0))
    if f["assignee"]:
        if f["assignee"] == "none":
            sql += " AND e.assigned_to IS NULL"
        else:
            sql += " AND e.assigned_to = ?"
            args.append(parse_int(f["assignee"], 0))
    if f["range"] == "today":
        sql += " AND date(e.created_at) = date('now')"
    elif f["range"] == "week":
        sql += " AND e.created_at > datetime('now', '-7 days')"
    elif f["range"] == "month":
        sql += " AND e.created_at > datetime('now', '-30 days')"
    if f["q"]:
        sql += " AND (e.name LIKE ? OR e.phone LIKE ? OR e.email LIKE ? OR e.message LIKE ? OR e.ref LIKE ?)"
        term = f"%{f['q']}%"
        args += [term] * 5
    return sql, args


BASE_SQL = (
    "SELECT e.*, s.name AS service_name, b.name AS branch_name, u.name AS assignee_name "
    "FROM enquiries e "
    "LEFT JOIN services s ON s.id = e.service_id "
    "LEFT JOIN branches b ON b.id = e.branch_id "
    "LEFT JOIN users u ON u.id = e.assigned_to"
)


def register(bp) -> None:

    @bp.route("/enquiries")
    @require_role("enquiries")
    def enquiries_list():
        f = _filters()
        where, args = _where(f)
        page = max(1, parse_int(request.args.get("page"), 1))
        total = int(db.scalar(f"SELECT COUNT(*) FROM enquiries e{where}", args, 0))
        rows = db.query(
            f"{BASE_SQL}{where} ORDER BY "
            "CASE e.status WHEN 'new' THEN 0 WHEN 'contacted' THEN 1 ELSE 2 END, "
            "CASE e.priority WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, e.id DESC "
            "LIMIT ? OFFSET ?",
            args + [PER_PAGE, (page - 1) * PER_PAGE])

        return render_template(
            "admin/enquiries.html", title="Enquiries", rows=rows, f=f,
            statuses=STATUSES, priorities=PRIORITIES, tone=STATUS_TONE,
            services=db.query("SELECT id, name FROM services ORDER BY name"),
            branches=db.query("SELECT id, name FROM branches ORDER BY sort_order"),
            staff=db.query("SELECT id, name FROM users WHERE is_active = 1 ORDER BY name"),
            counts={r["status"]: r["n"] for r in db.query(
                "SELECT status, COUNT(*) AS n FROM enquiries WHERE is_spam = 0 GROUP BY status")},
            spam_count=db.scalar("SELECT COUNT(*) FROM enquiries WHERE is_spam = 1", (), 0),
            page=page, pages=max(1, -(-total // PER_PAGE)), total=total, per_page=PER_PAGE)

    @bp.route("/enquiries/<int:row_id>")
    @require_role("enquiries")
    def enquiry_detail(row_id):
        row = db.one(f"{BASE_SQL} WHERE e.id = ?", (row_id,))
        if not row:
            abort(404)
        events = db.query(
            "SELECT ev.*, u.name AS user_name FROM enquiry_events ev "
            "LEFT JOIN users u ON u.id = ev.user_id "
            "WHERE ev.enquiry_id = ? ORDER BY ev.id DESC", (row_id,))
        return render_template(
            "admin/enquiry_detail.html", title=row["name"], row=row, events=events,
            statuses=STATUSES, priorities=PRIORITIES, tone=STATUS_TONE,
            utm=load_json(row["utm"], {}),
            staff=db.query("SELECT id, name FROM users WHERE is_active = 1 ORDER BY name"),
            plans=emi_core.active_plans(),
            emi_app=db.one("SELECT * FROM emi_applications WHERE enquiry_id = ?", (row_id,)),
        )

    @bp.route("/enquiries/<int:row_id>/update", methods=["POST"])
    @require_role("enquiries")
    def enquiry_update(row_id):
        verify_csrf()
        row = db.one("SELECT * FROM enquiries WHERE id = ?", (row_id,))
        if not row:
            abort(404)
        user = current_user()
        data: dict = {"updated_at": db.scalar("SELECT datetime('now')")}
        notes = []

        status = request.form.get("status")
        if status and status != row["status"]:
            data["status"] = status
            notes.append(("status", f"Status: {row['status']} to {status}"))

        priority = request.form.get("priority")
        if priority and priority != row["priority"]:
            data["priority"] = priority
            notes.append(("note", f"Priority set to {priority}"))

        if "assigned_to" in request.form:
            assignee = parse_int(request.form.get("assigned_to"), 0) or None
            if assignee != row["assigned_to"]:
                data["assigned_to"] = assignee
                who = db.scalar("SELECT name FROM users WHERE id = ?", (assignee,)) if assignee else "nobody"
                notes.append(("assign", f"Assigned to {who}"))

        note = (request.form.get("note") or "").strip()
        if note:
            notes.append(("note", note))

        if len(data) > 1:
            db.update("enquiries", row_id, data)
        for kind, text in notes:
            db.insert("enquiry_events", {
                "enquiry_id": row_id, "user_id": user["id"] if user else None,
                "type": kind, "note": text})
        if len(data) > 1 or notes:
            audit.log("update", "enquiries", row_id, row["name"], before=row, after=data)
            flash("Enquiry updated.", "ok")
        return redirect(url_for("admin.enquiry_detail", row_id=row_id))

    @bp.route("/enquiries/<int:row_id>/spam", methods=["POST"])
    @require_role("enquiries")
    def enquiry_spam(row_id):
        verify_csrf()
        row = db.one("SELECT * FROM enquiries WHERE id = ?", (row_id,))
        if not row:
            abort(404)
        value = 0 if row["is_spam"] else 1
        db.update("enquiries", row_id, {"is_spam": value})
        audit.log("update", "enquiries", row_id, row["name"], after={"is_spam": value})
        flash("Marked as spam." if value else "Restored to the main list.", "ok")
        return redirect(url_for("admin.enquiries_list"))

    @bp.route("/enquiries/<int:row_id>/delete", methods=["POST"])
    @require_role("enquiries")
    def enquiry_delete(row_id):
        verify_csrf()
        row = db.one("SELECT * FROM enquiries WHERE id = ?", (row_id,))
        if not row:
            abort(404)
        db.delete("enquiries", row_id)
        audit.log("delete", "enquiries", row_id, row["name"], before=row)
        flash("Enquiry deleted.", "ok")
        return redirect(url_for("admin.enquiries_list"))

    @bp.route("/enquiries/bulk", methods=["POST"])
    @require_role("enquiries")
    def enquiries_bulk():
        verify_csrf()
        ids = [parse_int(v, 0) for v in request.form.getlist("ids")]
        ids = [i for i in ids if i]
        action = request.form.get("action", "")
        if not ids or not action:
            flash("Select some rows and an action first.", "error")
            return redirect(url_for("admin.enquiries_list"))

        user = current_user()
        marks = ", ".join("?" for _ in ids)
        if action.startswith("status:"):
            status = action.split(":", 1)[1]
            db.execute(f"UPDATE enquiries SET status = ?, updated_at = datetime('now') "
                       f"WHERE id IN ({marks})", [status] + ids)
            for row_id in ids:
                db.insert("enquiry_events", {
                    "enquiry_id": row_id, "user_id": user["id"] if user else None,
                    "type": "status", "note": f"Status set to {status} in a bulk update"})
            flash(f"{len(ids)} enquiries moved to {status}.", "ok")
        elif action == "spam":
            db.execute(f"UPDATE enquiries SET is_spam = 1 WHERE id IN ({marks})", ids)
            flash(f"{len(ids)} enquiries marked as spam.", "ok")
        elif action == "unspam":
            db.execute(f"UPDATE enquiries SET is_spam = 0 WHERE id IN ({marks})", ids)
            flash(f"{len(ids)} enquiries restored.", "ok")
        elif action == "assign":
            assignee = parse_int(request.form.get("assign_to"), 0) or None
            db.execute(f"UPDATE enquiries SET assigned_to = ? WHERE id IN ({marks})",
                       [assignee] + ids)
            flash(f"{len(ids)} enquiries reassigned.", "ok")
        elif action == "delete":
            db.execute(f"DELETE FROM enquiries WHERE id IN ({marks})", ids)
            flash(f"{len(ids)} enquiries deleted.", "ok")
        else:
            flash("Unknown action.", "error")

        audit.log("update", "enquiries", "", f"bulk {action} on {len(ids)} rows")
        return redirect(request.referrer or url_for("admin.enquiries_list"))

    @bp.route("/enquiries/export")
    @require_role("enquiries")
    def enquiries_export():
        f = _filters()
        where, args = _where(f)
        rows = db.query(f"{BASE_SQL}{where} ORDER BY e.id DESC", args)

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Ref", "Received", "Name", "Phone", "Email", "Treatment", "Clinic",
                         "Preferred date", "Preferred time", "Status", "Priority", "Assigned to",
                         "Source", "Message"])
        for r in rows:
            # Every cell goes through csv_cell: names, messages and source pages are
            # anonymous input, and a leading = or @ would run when staff open the file.
            writer.writerow([csv_cell(v) for v in (
                r["ref"], r["created_at"], r["name"], r["phone"], r["email"],
                r["service_name"] or "", r["branch_name"] or "",
                r["preferred_date"], r["preferred_time"], r["status"],
                r["priority"], r["assignee_name"] or "", r["source_page"],
                (r["message"] or "").replace("\n", " "))])

        audit.log("export", "enquiries", "", f"CSV of {len(rows)} rows")
        stamp = date.today().isoformat()
        return Response(
            buffer.getvalue(), mimetype="text/csv",
            headers={"Content-Disposition": f'attachment; filename="enquiries-{stamp}.csv"'})

    @bp.route("/enquiries/<int:row_id>/to-emi", methods=["POST"])
    @require_role("enquiries", "emi")
    def enquiry_to_emi(row_id):
        verify_csrf()
        row = db.one("SELECT * FROM enquiries WHERE id = ?", (row_id,))
        if not row:
            abort(404)
        amount = parse_float(
            request.form.get("treatment_amount") or request.form.get("amount"), 0)
        plan = db.one("SELECT * FROM emi_plans WHERE id = ?",
                      (parse_int(request.form.get("plan_id"), 0),))
        if amount <= 0 or not plan:
            flash("An amount and a plan are needed.", "error")
            return redirect(url_for("admin.enquiry_detail", row_id=row_id))

        q = emi_core.quote_for_plan(amount, plan)
        service_name = db.scalar("SELECT name FROM services WHERE id = ?", (row["service_id"],)) or ""
        app_id = db.insert("emi_applications", {
            "ref": emi_core.new_application_ref(), "enquiry_id": row_id,
            "applicant_name": row["name"], "phone": row["phone"], "email": row["email"],
            "service_id": row["service_id"], "treatment_label": service_name,
            "treatment_amount": amount, "plan_id": plan["id"], "plan_label": plan["name"],
            "tenure_months": plan["tenure_months"], "interest_rate": plan["interest_rate"],
            "processing_fee": q["processing_fee"], "downpayment": q["downpayment"],
            "financed": q["financed"], "monthly_emi": q["monthly_emi"],
            "total_payable": q["total_payable"], "status": "under_review",
            "start_date": date.today().isoformat(),
            "notes": f"Raised from enquiry {row['ref']} by the front desk.",
        })
        db.insert("enquiry_events", {
            "enquiry_id": row_id, "user_id": (current_user() or {})["id"] if current_user() else None,
            "type": "emi", "note": f"EMI application raised for {settings.get('emi.currency', 'INR')} "
                                   f"{int(amount)} on {plan['name']}."})
        audit.log("create", "emi_applications", app_id, row["name"])
        flash("EMI application created and linked to this enquiry.", "ok")
        return redirect(url_for("admin.emi_application_detail", app_id=app_id))
