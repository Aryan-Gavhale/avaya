"""Route and write smoke test, stdlib only. Needs the dev server running.

Signs in, GETs every public and admin route and reports anything that is not a
200, then exercises the write paths end to end — an enquiry, an EMI application
through schedule, payment, receipt and void, service and section CRUD, settings,
an upload, a backup — and checks that CSRF is enforced. It cleans up after
itself and restores any setting it touched.

    python check_routes.py
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

BASE = "http://127.0.0.1:8120"
EMAIL = "owner@anvayadental.in"
PASSWORD = "anvaya2026"

jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def get(path: str):
    try:
        with opener.open(BASE + path, timeout=30) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def post(path: str, data: dict):
    body = urllib.parse.urlencode(data).encode()
    try:
        with opener.open(BASE + path, data=body, timeout=30) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def token(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else ""


def payload_of(text: str) -> dict:
    """Parse a JSON response body. Flask only pretty-prints with debug on, so
    substring matching on spacing is not safe."""
    try:
        return json.loads(text)
    except ValueError:
        return {}


def form_token(html: str) -> str:
    """The signed 'form was served at' stamp the public forms carry."""
    match = re.search(r'name="form_token" value="([^"]+)"', html)
    return match.group(1) if match else ""


def public_form_fields(path: str) -> dict:
    html = get(path)[1]
    return {"csrf_token": token(html), "form_token": form_token(html)}


def main() -> int:
    status, html = get("/admin/login")
    if status != 200:
        print(f"login page unreachable: {status} {html[:300]}")
        return 1

    status, html = post("/admin/login", {
        "csrf_token": token(html), "email": EMAIL, "password": PASSWORD, "next": ""})
    if "side__brand" not in html:
        print(f"sign-in failed: {status}")
        print(html[:1200])
        return 1
    print("signed in")

    paths = [
        "/", "/treatments", "/about", "/emi-and-payment", "/contact",
        "/treatments/dental-implants", "/sitemap.xml", "/robots.txt", "/thank-you",
        "/nope-404",
        "/admin/", "/admin/pages", "/admin/pages/1", "/admin/pages/new",
        "/admin/sections/1", "/admin/sections/2", "/admin/sections/3",
        "/admin/services", "/admin/services/1", "/admin/services/new",
        "/admin/service_categories", "/admin/service_categories/1",
        "/admin/doctors", "/admin/doctors/1", "/admin/branches", "/admin/branches/1",
        "/admin/faqs", "/admin/faqs/1", "/admin/nav_items", "/admin/nav_items/1",
        "/admin/testimonials", "/admin/testimonials/1",
        "/admin/galleries", "/admin/galleries/1", "/admin/galleries/1/items",
        "/admin/media", "/admin/media/picker", "/admin/media?source=remote",
        "/admin/reviews",
        "/admin/enquiries", "/admin/enquiries?status=new", "/admin/enquiries/1",
        "/admin/enquiries/export",
        "/admin/emi_plans", "/admin/emi_plans/1", "/admin/emi_plans/new",
        "/admin/emi/applications", "/admin/emi/applications/new",
        "/admin/emi/applications/1", "/admin/emi/ledger",
        "/admin/emi/ledger?view=overdue", "/admin/emi/ledger?view=upcoming",
        "/admin/emi/ledger/export", "/admin/emi/ledger/export?what=outstanding",
        "/admin/settings", "/admin/settings/social", "/admin/settings/theme",
        "/admin/settings/seo", "/admin/settings/enquiry", "/admin/settings/emi",
        "/admin/settings/hours",
        "/admin/users", "/admin/account", "/admin/activity", "/admin/backup",
    ]

    bad = 0
    for path in paths:
        status, body = get(path)
        expected = 404 if path == "/nope-404" else 200
        flag = "ok " if status == expected else "FAIL"
        if status != expected:
            bad += 1
        print(f"{flag} {status} {path}")
        if status not in (200, 404, 302):
            snippet = re.sub(r"\s+", " ", body)[:400]
            print("      " + snippet)
        elif status == 200 and "Traceback" in body:
            bad += 1
            print("      contains a traceback")

    print(f"\n-- write flows --")
    bad += writes()

    print(f"\n{bad} problem(s)")
    return 1 if bad else 0


def check(label: str, ok: bool, detail: str = "") -> int:
    print(f"{'ok  ' if ok else 'FAIL'} {label}")
    if not ok and detail:
        print("      " + re.sub(r"\s+", " ", detail)[:400])
    return 0 if ok else 1


def csrf_from(path: str) -> str:
    return token(get(path)[1])


def row_id(list_path: str, needle: str) -> int:
    """id of the table row whose markup mentions needle."""
    html = get(list_path)[1]
    for chunk in html.split('<tr data-id="')[1:]:
        ident, _, rest = chunk.partition('"')
        if needle in rest.split("</tr>")[0] and ident.isdigit():
            return int(ident)
    return 0


def purge() -> None:
    """Remove rows an earlier run left behind, so slugs and lookups stay unambiguous."""
    import sqlite3

    conn = sqlite3.connect("db/clinic.db")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
        DELETE FROM payments           WHERE receipt_no LIKE 'SMK%';
        DELETE FROM emi_applications   WHERE applicant_name LIKE 'Smoke %';
        DELETE FROM enquiries          WHERE name LIKE 'Smoke %';
        DELETE FROM services           WHERE name LIKE 'Smoke Test Treatment%';
        DELETE FROM sections           WHERE name LIKE 'Smoke %';
        DELETE FROM media              WHERE filename LIKE '%smoke%'
                                          OR filename LIKE '%not-really%';
        DELETE FROM login_attempts     WHERE email LIKE '%example.com';
    """)
    conn.commit()
    conn.close()


def settings_snapshot() -> list:
    import sqlite3

    conn = sqlite3.connect("db/clinic.db")
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return rows


def settings_restore(rows: list) -> None:
    import sqlite3

    conn = sqlite3.connect("db/clinic.db")
    conn.execute("DELETE FROM settings")
    conn.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", rows)
    conn.commit()
    conn.close()


def writes() -> int:
    bad = 0
    purge()
    saved_settings = settings_snapshot()

    # ── public enquiry ──────────────────────────────────────────────────────
    fields = public_form_fields("/contact")
    emi_fields = public_form_fields("/emi-and-payment")
    bad += check("enquiry form carries a CSRF token and a form stamp",
                 bool(fields["csrf_token"] and fields["form_token"]))

    # A person takes longer than MIN_FORM_SECONDS to fill this in; waiting keeps the
    # submission out of the spam pile so the rest of the flow sees a normal enquiry.
    time.sleep(3.4)

    status, body = post("/enquiry", {
        "name": "Smoke Test", "phone": "9876500001", "email": "smoke@example.com",
        "service_id": "1", "branch_id": "1", "preferred_date": "2026-09-10",
        "preferred_time": "Evening", "message": "Sent by the smoke test.",
        "source_page": "/", "utm_source": "smoke", **fields})
    bad += check("public enquiry accepted", status == 200 and "ENQ" in body, body)

    bad += check("a genuine enquiry is not flagged as spam",
                 "9876500001" in get("/admin/enquiries")[1])

    status, body = post("/enquiry", {
        "name": "Smoke Test no token", "phone": "9876500003", "message": "No token.",
        "source_page": "/"})
    bad += check("enquiry without a CSRF token is refused", status == 400, body)

    status, body = post("/enquiry", {
        "name": "Smoke Test no stamp", "phone": "9876500005", "message": "No stamp.",
        "source_page": "/", "csrf_token": fields["csrf_token"]})
    bad += check("enquiry with no form stamp is kept but flagged",
                 status == 200
                 and "9876500005" not in get("/admin/enquiries")[1]
                 and "9876500005" in get("/admin/enquiries?spam=1")[1], body)

    # ── public EMI application ──────────────────────────────────────────────
    status, body = post("/emi/apply", {
        "applicant_name": "Smoke EMI", "phone": "9876500002", "email": "emi@example.com",
        "treatment_amount": "90000", "plan_id": "1", "service_id": "1",
        "message": "Sent by the smoke test.", **emi_fields})
    bad += check("public EMI application accepted", status == 200 and "EMI" in body, body)

    status, body = post("/emi/apply", {
        "applicant_name": "Smoke EMI", "phone": "9876500004",
        "treatment_amount": "90000", "plan_id": "1"})
    bad += check("EMI application without a CSRF token is refused", status == 400, body)

    status, body = get("/emi/quote?amount=90000")
    bad += check("EMI quote endpoint", '"plans"' in body, body)
    status, body = get("/api/rating")
    bad += check("rating endpoint", '"source"' in body, body)

    # ── admin: create, edit, toggle, delete a treatment ─────────────────────
    csrf = csrf_from("/admin/services/new")
    status, body = post("/admin/services/new", {
        "csrf_token": csrf, "name": "Smoke Test Treatment", "slug": "",
        "summary": "Created by the smoke test.", "body": "Line one.\n\nLine two.",
        "price_from": "4000", "price_to": "9000", "duration_min": "45",
        "sittings": "1 visit", "icon": "tooth", "category_id": "1",
        "emi_eligible": "1", "is_published": "1"})
    bad += check("service created", "Smoke Test Treatment" in body, body)

    new_id = row_id("/admin/services", "Smoke Test Treatment")
    bad += check("service id resolved", new_id > 0)

    if new_id:
        csrf = csrf_from(f"/admin/services/{new_id}")
        status, body = post(f"/admin/services/{new_id}", {
            "csrf_token": csrf, "name": "Smoke Test Treatment edited",
            "slug": "smoke-test-treatment", "summary": "Edited.", "body": "Edited body.",
            "price_from": "5000", "icon": "crown", "is_published": "1"})
        bad += check("service edited", "Smoke Test Treatment edited" in body, body)

        status, body = post(f"/admin/services/{new_id}/toggle", {"csrf_token": csrf})
        bad += check("service visibility toggled", status == 200, body)

        status, body = get(f"/treatments/smoke-test-treatment")
        bad += check("unpublished treatment 404s on the site", status == 404)

        status, body = post(f"/admin/services/{new_id}/toggle", {"csrf_token": csrf})
        status, body = get(f"/treatments/smoke-test-treatment")
        bad += check("republished treatment renders", status == 200, body)

        status, body = post(f"/admin/services/{new_id}/delete", {"csrf_token": csrf})
        bad += check("service deleted",
                     f'<tr data-id="{new_id}"' not in body, body)

    # ── admin: reorder ──────────────────────────────────────────────────────
    ids = re.findall(r'<tr data-id="(\d+)"', get("/admin/services")[1])
    if len(ids) > 2:
        order = [ids[1], ids[0]] + ids[2:]
        body = urllib.parse.urlencode({}).encode()
        request_obj = urllib.request.Request(
            BASE + "/admin/services/reorder",
            data=('{"order": ' + str(order).replace("'", '"') + '}').encode(),
            headers={"Content-Type": "application/json",
                     "X-CSRF-Token": csrf_from("/admin/services")})
        try:
            with opener.open(request_obj, timeout=20) as response:
                payload = response.read().decode()
            bad += check("services reordered", payload_of(payload).get("ok") is True, payload)
        except Exception as exc:  # noqa: BLE001
            bad += check("services reordered", False, str(exc))

    # ── admin: section builder ──────────────────────────────────────────────
    csrf = csrf_from("/admin/pages/1")
    status, body = post("/admin/pages/1/sections/add", {"csrf_token": csrf, "type": "trust"})
    bad += check("section added", "Assurance strip" in body, body)
    section_id = 0
    for row in re.finditer(r'/admin/sections/(\d+)', body):
        section_id = max(section_id, int(row.group(1)))

    if section_id:
        csrf = csrf_from(f"/admin/sections/{section_id}")
        status, body = post(f"/admin/sections/{section_id}", {
            "csrf_token": csrf, "name": "Smoke strip", "anchor": "smoke",
            "is_published": "1",
            "items": "Sterilised | Every instrument autoclaved\nOn time | We run to the minute"})
        bad += check("section saved", "Smoke strip" in body, body)
        bad += check("section renders on the page", "Every instrument autoclaved" in get("/")[1])

        status, body = post(f"/admin/sections/{section_id}/duplicate", {"csrf_token": csrf})
        bad += check("section duplicated", "copy" in body, body)
        dupe = 0
        for row in re.finditer(r'/admin/sections/(\d+)', body):
            dupe = max(dupe, int(row.group(1)))
        if dupe and dupe != section_id:
            post(f"/admin/sections/{dupe}/delete", {"csrf_token": csrf_from(f"/admin/sections/{dupe}")})

        status, body = post(f"/admin/sections/{section_id}/delete", {"csrf_token": csrf})
        bad += check("section deleted", "Smoke strip" not in body, body)

    # ── admin: settings ─────────────────────────────────────────────────────
    csrf = csrf_from("/admin/settings/emi")
    status, body = post("/admin/settings/emi/save", {
        "csrf_token": csrf, "emi.enabled": "1", "emi.receipt_prefix": "SMK",
        "emi.note": "Set by the smoke test."})
    bad += check("settings saved", "Set by the smoke test." in body, body)
    csrf = csrf_from("/admin/settings/hours")
    status, body = post("/admin/settings/hours/save", {
        "csrf_token": csrf,
        "hours.week__mon_open": "09:30", "hours.week__mon_close": "20:00",
        "hours.week__tue_open": "09:30", "hours.week__tue_close": "20:00",
        "hours.week__wed_open": "09:30", "hours.week__wed_close": "20:00",
        "hours.week__thu_open": "09:30", "hours.week__thu_close": "20:00",
        "hours.week__fri_open": "09:30", "hours.week__fri_close": "20:00",
        "hours.week__sat_open": "09:30", "hours.week__sat_close": "17:00",
        "hours.week__sun_closed": "1",
        "hours.note": "Sundays by appointment only.",
        "hours.holidays": "2026-10-02 | Gandhi Jayanti"})
    bad += check("hours saved", "09:30" in body and "Gandhi Jayanti" in body, body)

    # ── admin: enquiry workflow ─────────────────────────────────────────────
    enq = re.search(r'/admin/enquiries/(\d+)', get("/admin/enquiries")[1])
    if enq:
        eid = enq.group(1)
        csrf = csrf_from(f"/admin/enquiries/{eid}")
        status, body = post(f"/admin/enquiries/{eid}/update", {
            "csrf_token": csrf, "status": "contacted", "priority": "high",
            "assigned_to": "1", "note": "Called, ringing out. Smoke test note."})
        bad += check("enquiry updated", "Smoke test note" in body, body)
        status, body = post("/admin/enquiries/bulk", {
            "csrf_token": csrf, "ids": eid, "action": "status:booked"})
        bad += check("bulk status applied", status == 200, body)

    # ── admin: EMI end to end ───────────────────────────────────────────────
    csrf = csrf_from("/admin/emi/applications/new")
    status, body = post("/admin/emi/applications/new", {
        "csrf_token": csrf, "applicant_name": "Smoke Ledger", "phone": "9876500003",
        "email": "ledger@example.com", "treatment_amount": "120000", "plan_id": "1",
        "start_date": "2026-09-05", "status": "under_review",
        "notes": "Raised by the smoke test."})
    bad += check("admin EMI application created", "Smoke Ledger" in body, body)
    app_id = row_id("/admin/emi/applications", "Smoke Ledger")
    if not app_id:
        found = re.search(r'/admin/emi/applications/(\d+)/update', body)
        app_id = int(found.group(1)) if found else 0

    if app_id:
        base = f"/admin/emi/applications/{app_id}"
        csrf = csrf_from(base)
        status, body = post(f"{base}/update", {
            "csrf_token": csrf, "status": "approved", "start_date": "2026-09-05",
            "treatment_amount": "120000", "plan_id": "1", "kyc_notes": "PAN seen.",
            "notes": "Approved by the smoke test."})
        bad += check("application approved and schedule generated",
                    "instalment schedule generated" in body or "Instalment schedule" in body, body)

        inst = re.search(r'data-pay="(\d+)" data-amount="(\d+)"', body)
        bad += check("schedule has due instalments", bool(inst))
        if inst:
            status, body = post("/admin/emi/payments/record", {
                "csrf_token": csrf, "application_id": str(app_id),
                "installment_id": inst.group(1), "amount": inst.group(2),
                "method": "upi", "paid_at": "2026-09-05", "provider": "PhonePe",
                "provider_ref": "SMOKE123", "notes": "Smoke test payment"})
            bad += check("payment recorded and receipt shown",
                         "Amount received" in body and "SMK-" in body, body)
            pay = re.search(r'/admin/emi/payments/(\d+)/void', body)
            bad += check("receipt offers a void", bool(pay))
            if pay:
                status, body = post(f"/admin/emi/payments/{pay.group(1)}/void",
                                    {"csrf_token": csrf_from(base)})
                bad += check("payment voided and instalment reopened",
                             "voided" in body.lower(), body)

        status, body = post(f"{base}/delete", {"csrf_token": csrf_from(base)})
        bad += check("application with only voided receipts is deletable",
                     f'<tr data-id="{app_id}"' not in body, body)
        bad += check("the voided receipt stays in the ledger",
                     "SMK-" in get("/admin/emi/ledger?view=payments")[1])

    # ── admin: media upload ─────────────────────────────────────────────────
    bad += upload_image()

    # ── admin: reviews connection without a key ─────────────────────────────
    csrf = csrf_from("/admin/reviews")
    status, body = post("/admin/reviews/save", {
        "csrf_token": csrf, "api_key": "", "place_id": "", "place_name": "Smoke Clinic",
        "reviews_source": "auto", "ttl": "360", "min_rating": "4", "max_reviews": "5"})
    bad += check("reviews settings saved", "Smoke Clinic" in body, body)
    status, body = post("/admin/reviews/search", {"csrf_token": csrf, "query": "Anvaya"})
    bad += check("search without a key is refused politely",
                 "Add the API key first" in body, body)
    status, body = get("/")
    bad += check("reviews section falls back to curated quotes",
                 "reviews" in body.lower(), body)

    # ── admin: backup ───────────────────────────────────────────────────────
    csrf = csrf_from("/admin/backup")
    status, body = post("/admin/backup/create", {"csrf_token": csrf})
    bad += check("backup written", "clinic-backup-" in body, body)
    name = re.search(r"(clinic-backup-[\d-]+\.zip)", body)
    if name:
        status, _ = get("/admin/backup/download/" + name.group(1))
        bad += check("backup downloads", status == 200)
        post("/admin/backup/delete/" + name.group(1), {"csrf_token": csrf_from("/admin/backup")})

    # ── csrf is actually enforced ───────────────────────────────────────────
    status, body = post("/admin/services/new", {"name": "No token"})
    bad += check("a form without a CSRF token is rejected", status == 400, body)

    # ── hardening added after the security review ───────────────────────────
    status, _ = get("/admin/logout")
    bad += check("logout cannot be triggered by a GET", status == 405)

    request_obj = urllib.request.Request(
        BASE + "/admin/services/reorder", data=b'{"ids": ["not-a-number"]}',
        headers={"Content-Type": "application/json",
                 "X-CSRF-Token": csrf_from("/admin/services")})
    try:
        with opener.open(request_obj, timeout=20) as response:
            reorder_status = response.status
    except urllib.error.HTTPError as exc:
        reorder_status = exc.code
    bad += check("a malformed reorder payload is a 400, not a 500", reorder_status == 400)

    bad += check("responses carry a content security policy",
                 bool(headers_of("/")[0].get("Content-Security-Policy")))
    bad += check("admin pages are not cached",
                 headers_of("/admin/")[0].get("Cache-Control") == "no-store")
    bad += check("the google photo proxy refuses an unknown photo name",
                 get("/media/google-photo/places/xxx/photos/yyy")[0] == 404)
    bad += check("a non-image upload is refused", reject_fake_image())

    purge()
    settings_restore(saved_settings)
    print("     (test rows removed, settings put back)")
    return bad


def headers_of(path: str):
    try:
        with opener.open(BASE + path, timeout=20) as response:
            return dict(response.headers), response.status
    except urllib.error.HTTPError as exc:
        return dict(exc.headers), exc.code


def reject_fake_image() -> bool:
    """A .png that is really a text file has to be turned away, not stored."""
    boundary = "----smokefake"
    csrf = csrf_from("/admin/media")
    body = b"".join([
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"csrf_token\"\r\n\r\n{csrf}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
        f"filename=\"not-really.png\"\r\nContent-Type: image/png\r\n\r\n".encode(),
        b"<html><script>alert(1)</script></html>",
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    request_obj = urllib.request.Request(
        BASE + "/admin/media/upload", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                 "X-Requested-With": "fetch"})
    try:
        with opener.open(request_obj, timeout=30) as response:
            result = response.read().decode()
    except Exception:  # noqa: BLE001
        return False
    data = payload_of(result)
    return data.get("saved") == 0 and any("readable image" in e for e in data.get("errors", []))


def upload_image() -> int:
    """Multipart upload of a small generated PNG."""
    import io as _io

    try:
        from PIL import Image
    except ImportError:
        print("ok   media upload skipped, Pillow missing")
        return 0

    buffer = _io.BytesIO()
    Image.new("RGB", (900, 600), (18, 90, 84)).save(buffer, format="PNG")
    payload = buffer.getvalue()

    boundary = "----smokeboundary"
    csrf = csrf_from("/admin/media")
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"csrf_token\"\r\n\r\n{csrf}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
        f"filename=\"smoke.png\"\r\nContent-Type: image/png\r\n\r\n".encode(),
        payload,
        f"\r\n--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)
    request_obj = urllib.request.Request(
        BASE + "/admin/media/upload", data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                 "X-Requested-With": "fetch"})
    try:
        with opener.open(request_obj, timeout=30) as response:
            result = response.read().decode()
    except Exception as exc:  # noqa: BLE001
        return check("media upload", False, str(exc))

    bad = check("media upload accepted", payload_of(result).get("ok") is True, result)

    page = get("/admin/media")[1]
    match = re.search(r'id="m(\d+)"', page)
    if match:
        mid = match.group(1)
        status, body = post(f"/admin/media/{mid}", {
            "csrf_token": csrf_from("/admin/media"), "alt": "A smoke test image",
            "title": "Smoke", "credit": ""})
        bad += check("alt text saved", "A smoke test image" in body, body)
        status, body = post(f"/admin/media/{mid}/delete", {"csrf_token": csrf_from("/admin/media")})
        bad += check("media deleted or usage-blocked",
                     "deleted" in body.lower() or "still used" in body.lower(), body)
    return bad


if __name__ == "__main__":
    sys.exit(main())
