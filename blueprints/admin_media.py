"""Media library: uploads, alt text, usage-checked deletes, galleries and the
Google Place photo importer."""

from __future__ import annotations

from flask import (abort, flash, jsonify, redirect, render_template, request,
                   url_for)

from core import audit, db, media, settings
from core.auth import require_role, verify_csrf
from core.util import parse_int
from services import google_places


def register(bp) -> None:

    @bp.route("/media")
    @require_role("media")
    def media_library():
        search = (request.args.get("q") or "").strip()
        source = request.args.get("source", "")
        rows = media.library(search, source)
        return render_template(
            "admin/media.html", rows=rows, search=search, source=source,
            title="Media library",
            counts={
                "all": db.scalar("SELECT COUNT(*) FROM media", (), 0),
                "upload": db.scalar("SELECT COUNT(*) FROM media WHERE source = 'upload'", (), 0),
                "remote": db.scalar("SELECT COUNT(*) FROM media WHERE source = 'remote'", (), 0),
                "google": db.scalar("SELECT COUNT(*) FROM media WHERE source = 'google'", (), 0),
            },
            google_ready=bool(settings.get("google.api_key") and settings.get("google.place_id")),
        )

    @bp.route("/media/upload", methods=["POST"])
    @require_role("media")
    def media_upload():
        verify_csrf()
        files = request.files.getlist("files")
        saved, failed = 0, []
        for item in files:
            if not item or not item.filename:
                continue
            try:
                row = media.save_upload(item, alt=request.form.get("alt", ""))
                audit.log("create", "media", row["id"], row["filename"] or row["title"])
                saved += 1
            except Exception as exc:  # noqa: BLE001
                failed.append(str(exc))

        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify({"ok": not failed, "saved": saved, "errors": failed})
        if saved:
            flash(f"{saved} file{'s' if saved != 1 else ''} uploaded. Add alt text below.", "ok")
        for message in failed:
            flash(message, "error")
        return redirect(url_for("admin.media_library"))

    @bp.route("/media/<int:row_id>", methods=["POST"])
    @require_role("media")
    def media_save(row_id):
        verify_csrf()
        row = media.get(row_id)
        if not row:
            abort(404)
        data = {
            "alt": (request.form.get("alt") or "").strip(),
            "title": (request.form.get("title") or "").strip(),
            "credit": (request.form.get("credit") or "").strip(),
        }
        db.update("media", row_id, data)
        audit.log("update", "media", row_id, data["title"] or str(row_id), before=row, after=data)
        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify({"ok": True})
        flash("Image details saved.", "ok")
        return redirect(url_for("admin.media_library"))

    @bp.route("/media/<int:row_id>/delete", methods=["POST"])
    @require_role("media")
    def media_delete(row_id):
        verify_csrf()
        row = media.get(row_id)
        if not row:
            abort(404)
        used = media.usage(row_id)
        if used and not request.form.get("force"):
            names = ", ".join(f"{u['kind']}: {u['label']}" for u in used[:4])
            flash(f"That image is still used by {len(used)} item(s) - {names}. "
                  "Delete it again to remove it anyway.", "error")
            return redirect(url_for("admin.media_library", highlight=row_id))
        media.delete_media(row_id)
        audit.log("delete", "media", row_id, row["title"] or str(row_id), before=row)
        flash("Image deleted.", "ok")
        return redirect(url_for("admin.media_library"))

    @bp.route("/media/<int:row_id>/usage")
    @require_role("media")
    def media_usage(row_id):
        return jsonify({"usage": media.usage(row_id)})

    @bp.route("/media/picker")
    @require_role("media", "content")
    def media_picker():
        """HTML fragment for the image picker modal used by every media field."""
        search = (request.args.get("q") or "").strip()
        return render_template("admin/_picker.html",
                               rows=media.library(search, "", 120),
                               field=request.args.get("field", ""), search=search)

    # ── google photos ───────────────────────────────────────────────────────
    @bp.route("/media/google-import", methods=["POST"])
    @require_role("media")
    def media_google_import():
        verify_csrf()
        api_key = settings.get("google.api_key", "")
        place_id = settings.get("google.place_id", "")
        if not api_key or not place_id:
            flash("Connect a Google API key and Place ID first, on the reviews screen.", "error")
            return redirect(url_for("admin.media_library"))

        ok, payload, _status = google_places.place_photo_names(api_key, place_id, 10)
        if not ok:
            flash(f"Google refused the request: {payload}", "error")
            return redirect(url_for("admin.media_library"))

        settings.set("google.photos_enabled", True)
        added = 0
        for name in payload:
            proxy = url_for("public.google_photo", photo_name=name)
            if db.one("SELECT 1 FROM media WHERE url = ?", (proxy,)):
                continue
            media.add_remote(proxy, alt=f"{settings.get('brand.name')} on Google",
                             title="Google Place photo", credit="Google", source="google")
            added += 1
        audit.log("create", "media", "", f"imported {added} Google Place photos")
        flash(f"{added} Google photo{'s' if added != 1 else ''} linked. They stream from Google "
              "rather than being stored here, so add your own photographs for the gallery.",
              "ok" if added else "error")
        return redirect(url_for("admin.media_library", source="google"))

    # ── galleries ───────────────────────────────────────────────────────────
    @bp.route("/galleries/<int:gallery_id>/items")
    @require_role("media")
    def gallery_items(gallery_id):
        gallery = db.one("SELECT * FROM galleries WHERE id = ?", (gallery_id,))
        if not gallery:
            abort(404)
        items = db.query(
            "SELECT gi.id, gi.caption, gi.sort_order, gi.media_id, m.alt, m.title, m.url, "
            "m.filename, m.medium, m.thumb FROM gallery_items gi "
            "JOIN media m ON m.id = gi.media_id WHERE gi.gallery_id = ? ORDER BY gi.sort_order",
            (gallery_id,))
        return render_template("admin/gallery_items.html", gallery=gallery, items=items,
                               title=gallery["name"])

    @bp.route("/galleries/<int:gallery_id>/items/add", methods=["POST"])
    @require_role("media")
    def gallery_item_add(gallery_id):
        verify_csrf()
        media_ids = request.form.getlist("media_id")
        if not media_ids and request.form.get("media_id_single"):
            media_ids = [request.form["media_id_single"]]
        added = 0
        for value in media_ids:
            mid = parse_int(value, 0)
            if not mid or not media.get(mid):
                continue
            db.insert("gallery_items", {
                "gallery_id": gallery_id, "media_id": mid, "caption": "",
                "sort_order": db.next_sort_order("gallery_items", "gallery_id = ?", (gallery_id,)),
            })
            added += 1
        audit.log("create", "gallery_items", gallery_id, f"added {added} photographs")
        flash(f"{added} photograph{'s' if added != 1 else ''} added.", "ok")
        return redirect(url_for("admin.gallery_items", gallery_id=gallery_id))

    @bp.route("/galleries/items/<int:item_id>/save", methods=["POST"])
    @require_role("media")
    def gallery_item_save(item_id):
        verify_csrf()
        row = db.one("SELECT * FROM gallery_items WHERE id = ?", (item_id,))
        if not row:
            abort(404)
        db.update("gallery_items", item_id, {"caption": (request.form.get("caption") or "").strip()})
        flash("Caption saved.", "ok")
        return redirect(url_for("admin.gallery_items", gallery_id=row["gallery_id"]))

    @bp.route("/galleries/items/<int:item_id>/delete", methods=["POST"])
    @require_role("media")
    def gallery_item_delete(item_id):
        verify_csrf()
        row = db.one("SELECT * FROM gallery_items WHERE id = ?", (item_id,))
        if not row:
            abort(404)
        db.delete("gallery_items", item_id)
        flash("Removed from the gallery. The image itself is still in the library.", "ok")
        return redirect(url_for("admin.gallery_items", gallery_id=row["gallery_id"]))

    @bp.route("/galleries/items/reorder", methods=["POST"])
    @require_role("media")
    def gallery_items_reorder():
        verify_csrf()
        ids = (request.get_json(silent=True, force=True) or {}).get("ids", [])
        if not isinstance(ids, list):
            return jsonify({"ok": False, "error": "Expected a list of item ids."}), 400
        try:
            ids = [int(item_id) for item_id in ids]
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Item ids have to be numbers."}), 400
        with db.transaction():
            for index, item_id in enumerate(ids):
                db.update("gallery_items", item_id, {"sort_order": index})
        return jsonify({"ok": True})
