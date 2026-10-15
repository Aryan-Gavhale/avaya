"""Content admin: the page and section builder, plus every catalogue table.

The catalogues are declared as Resource() specs and get their screens from
core.crud, so treatments, clinicians, clinics, FAQs, quotes and menus all behave
identically. Pages and sections need their own screens because a section's form
changes with its type.
"""

from __future__ import annotations

from flask import (abort, flash, jsonify, redirect, render_template, request,
                   url_for)

from core import audit, crud, db, sections as sections_mod
from core.auth import require_role, verify_csrf
from core.crud import Field, Resource
from core.util import (dump_json, load_json, parse_int, slugify, unique_slug)

ICONS = [("tooth", "Tooth (default)"), ("implant", "Implant"), ("root", "Root canal"),
         ("aligner", "Aligner"), ("braces", "Braces"), ("rehab", "Full mouth"),
         ("crown", "Crown"), ("whiten", "Whitening"), ("veneer", "Veneer"),
         ("clean", "Scaling"), ("extract", "Extraction"), ("child", "Children"),
         ("denture", "Denture")]


def _category_options():
    rows = db.query("SELECT id, name FROM service_categories ORDER BY sort_order, name")
    return [("", "- none -")] + [(r["id"], r["name"]) for r in rows]


# ── resources ───────────────────────────────────────────────────────────────
SERVICES = Resource(
    key="services", table="services", label="Treatment", label_plural="Treatments",
    area="content", sortable=True, publishable=True, slug_from="name", icon="tooth",
    searchable=("name", "summary", "body"),
    intro="Cards on the site, and one page each at /treatments/<slug>. Drag to reorder.",
    list_sql=("SELECT s.*, c.name AS category_name FROM services s "
              "LEFT JOIN service_categories c ON c.id = s.category_id"),
    list_columns=[("name", "Treatment"), ("category_name", "Category"),
                  ("price_band", "Fee band"), ("flags", "Flags")],
    fields=[
        Field("name", "Name", "text", required=True, span=8),
        Field("slug", "URL slug", "slug", span=4, help="Leave blank to build it from the name."),
        Field("category_id", "Category", "select", options=_category_options, span=6),
        Field("icon", "Icon", "select", options=ICONS, span=6,
              help="Used when no photograph is set."),
        Field("summary", "One-line summary", "textarea", rows=2,
              help="Shown on the card and in search results."),
        Field("body", "Full description", "textarea", rows=12,
              help="Blank lines start a new paragraph. Plain text, no HTML needed."),
        Field("price_from", "Fee from", "money", span=3, prefix="\u20b9"),
        Field("price_to", "Fee to", "money", span=3, prefix="\u20b9"),
        Field("duration_min", "Chair time", "int", span=3, suffix="minutes"),
        Field("sittings", "Visits", "text", span=3, placeholder="2 visits, a week apart"),
        Field("media_id", "Photograph", "media", span=12),
        Field("emi_eligible", "Offer EMI on this treatment", "checkbox", span=4),
        Field("is_featured", "Feature on the home page", "checkbox", span=4),
        Field("is_published", "Published", "checkbox", span=4, default=1),
    ],
)

CATEGORIES = Resource(
    key="service_categories", table="service_categories", label="Category",
    label_plural="Treatment categories", area="content", sortable=True, publishable=True,
    slug_from="name", searchable=("name",),
    intro="Groups the treatments page. Deleting a category leaves its treatments uncategorised.",
    list_columns=[("name", "Category"), ("summary", "Summary")],
    fields=[
        Field("name", "Name", "text", required=True, span=8),
        Field("slug", "URL slug", "slug", span=4),
        Field("summary", "Summary", "textarea", rows=2),
        Field("is_published", "Published", "checkbox", span=6, default=1),
    ],
)

DOCTORS = Resource(
    key="doctors", table="doctors", label="Clinician", label_plural="Clinicians",
    area="content", sortable=True, publishable=True, searchable=("name", "specialities", "bio"),
    intro="Shown by the clinicians section. Registration numbers are printed on the card.",
    list_columns=[("name", "Name"), ("role_title", "Role"), ("reg_no", "Reg. no")],
    fields=[
        Field("name", "Name", "text", required=True, span=6),
        Field("role_title", "Role", "text", span=6, placeholder="Endodontist"),
        Field("qualification", "Qualifications", "text",
              placeholder="MDS Conservative Dentistry, Nair Hospital"),
        Field("reg_no", "Registration number", "text", span=4),
        Field("experience_yr", "Years in practice", "int", span=4),
        Field("specialities", "Specialities", "csv", span=4,
              help="Comma separated. Rendered as tags."),
        Field("bio", "Biography", "textarea", rows=6),
        Field("media_id", "Portrait", "media"),
        Field("is_published", "Published", "checkbox", span=6, default=1),
    ],
)

BRANCHES = Resource(
    key="branches", table="branches", label="Clinic", label_plural="Clinics",
    area="content", sortable=True, publishable=True, searchable=("name", "address", "city"),
    intro="Each clinic carries its own hours, which drive the open / closed pill on its card.",
    list_columns=[("name", "Clinic"), ("city", "City"), ("phone", "Phone")],
    fields=[
        Field("name", "Name", "text", required=True, span=6),
        Field("phone", "Phone", "tel", span=6),
        Field("address", "Street address", "text"),
        Field("city", "City", "text", span=4),
        Field("pincode", "PIN code", "text", span=4),
        Field("email", "Email", "email", span=4),
        Field("whatsapp", "WhatsApp number", "text", span=6,
              help="Digits with country code, no plus sign. Example 919000012345."),
        Field("place_id", "Google Place ID", "text", span=6,
              help="Optional. Used if you connect reviews per clinic later."),
        Field("directions_url", "Directions link", "url"),
        Field("map_embed", "Note under the address", "textarea", rows=3,
              help="Parking, which lists run here, anything practical."),
        Field("hours", "Opening hours", "hours"),
        Field("media_id", "Photograph", "media"),
        Field("is_published", "Published", "checkbox", span=6, default=1),
    ],
)

FAQS = Resource(
    key="faqs", table="faqs", label="Question", label_plural="FAQs",
    area="content", sortable=True, publishable=True, searchable=("question", "answer"),
    row_label="question",
    intro="Sections can show all questions or filter to one category.",
    list_columns=[("question", "Question"), ("category", "Category")],
    fields=[
        Field("question", "Question", "text", required=True),
        Field("answer", "Answer", "textarea", rows=6),
        Field("category", "Category", "text", span=6, default="General",
              help="Free text. Reuse the same word to group questions."),
        Field("is_published", "Published", "checkbox", span=6, default=1),
    ],
)

TESTIMONIALS = Resource(
    key="testimonials", table="testimonials", label="Quote", label_plural="Curated quotes",
    area="reviews", sortable=True, publishable=True, searchable=("author", "body"),
    row_label="author",
    intro="The fallback for the reviews section, and what shows while Google is not connected. "
          "Publish only quotes you have permission to use.",
    list_columns=[("author", "Patient"), ("rating", "Rating"), ("treatment", "Treatment")],
    fields=[
        Field("author", "Patient name", "text", required=True, span=6),
        Field("author_role", "Under the name", "text", span=6,
              placeholder="Implant patient, 2025"),
        Field("body", "Quote", "textarea", rows=5, required=True),
        Field("rating", "Rating", "select", span=4,
              options=[(5, "5 stars"), (4, "4 stars"), (3, "3 stars"), (2, "2 stars"), (1, "1 star")],
              default=5),
        Field("treatment", "Treatment", "text", span=4),
        Field("is_featured", "Featured", "checkbox", span=4),
        Field("is_published", "Published", "checkbox", span=6, default=1),
    ],
)

NAV = Resource(
    key="nav_items", table="nav_items", label="Menu link", label_plural="Menus",
    area="content", sortable=True, publishable=True, row_label="label",
    intro="Header, footer and treatments column. Use /#anchor to jump to a section on the "
          "home page.",
    list_columns=[("label", "Label"), ("url", "Links to"), ("location", "Menu")],
    fields=[
        Field("label", "Label", "text", required=True, span=6),
        Field("location", "Menu", "select", span=6, default="header",
              options=[("header", "Header"), ("footer", "Footer, practice column"),
                       ("footer2", "Footer, treatments column")]),
        Field("url", "Links to", "text", required=True, placeholder="/treatments or /#emi"),
        Field("is_published", "Published", "checkbox", span=6, default=1),
    ],
)

GALLERIES = Resource(
    key="galleries", table="galleries", label="Gallery", label_plural="Galleries",
    area="media", slug_from="name", order_by="name", searchable=("name",),
    intro="A named set of photographs a gallery section can point at.",
    list_sql=("SELECT g.*, (SELECT COUNT(*) FROM gallery_items i WHERE i.gallery_id = g.id) "
              "AS items FROM galleries g"),
    list_columns=[("name", "Gallery"), ("slug", "Slug"), ("items", "Photographs")],
    fields=[
        Field("name", "Name", "text", required=True, span=8),
        Field("slug", "Slug", "slug", span=4),
    ],
)

RESOURCES = [SERVICES, CATEGORIES, DOCTORS, BRANCHES, FAQS, TESTIMONIALS, NAV, GALLERIES]


# ── page and section builder ────────────────────────────────────────────────
def register(bp) -> None:
    for res in RESOURCES:
        crud.register(bp, res)

    @bp.route("/pages")
    @require_role("content")
    def pages_list():
        rows = db.query(
            "SELECT p.*, "
            "(SELECT COUNT(*) FROM sections s WHERE s.page_id = p.id) AS n_sections, "
            "(SELECT COUNT(*) FROM sections s WHERE s.page_id = p.id AND s.is_published = 0) AS n_draft "
            "FROM pages p ORDER BY p.is_home DESC, p.sort_order, p.id")
        return render_template("admin/pages.html", rows=rows, title="Pages and sections")

    @bp.route("/pages/new", methods=["GET", "POST"])
    @require_role("content")
    def page_new():
        if request.method == "POST":
            verify_csrf()
            title = (request.form.get("title") or "").strip()
            if not title:
                flash("Give the page a title.", "error")
                return redirect(url_for("admin.page_new"))
            slug = slugify(request.form.get("slug") or title)
            slug = unique_slug(slug, lambda s: db.one(
                "SELECT 1 FROM pages WHERE slug = ?", (s,)) is not None)
            page_id = db.insert("pages", {
                "slug": slug, "title": title,
                "meta_title": (request.form.get("meta_title") or "").strip(),
                "meta_description": (request.form.get("meta_description") or "").strip(),
                "og_media_id": parse_int(request.form.get("og_media_id"), 0) or None,
                "is_published": 1 if request.form.get("is_published") else 0,
                "sort_order": db.next_sort_order("pages"),
            })
            audit.log("create", "pages", page_id, title)
            flash("Page created. Now add some sections.", "ok")
            return redirect(url_for("admin.page_edit", row_id=page_id))
        return render_template("admin/page_form.html", row=None, title="New page")

    @bp.route("/pages/<int:row_id>", methods=["GET", "POST"])
    @require_role("content")
    def page_edit(row_id):
        row = db.one("SELECT * FROM pages WHERE id = ?", (row_id,))
        if not row:
            abort(404)
        if request.method == "POST":
            verify_csrf()
            data = {
                "title": (request.form.get("title") or row["title"]).strip(),
                "meta_title": (request.form.get("meta_title") or "").strip(),
                "meta_description": (request.form.get("meta_description") or "").strip(),
                "og_media_id": parse_int(request.form.get("og_media_id"), 0) or None,
                "is_published": 1 if request.form.get("is_published") else 0,
                "updated_at": db.scalar("SELECT datetime('now')"),
            }
            new_slug = slugify(request.form.get("slug") or "")
            if new_slug and new_slug != row["slug"]:
                data["slug"] = unique_slug(new_slug, lambda s: db.one(
                    "SELECT 1 FROM pages WHERE slug = ? AND id != ?", (s, row_id)) is not None)
            if request.form.get("is_home"):
                db.execute("UPDATE pages SET is_home = 0")
                data["is_home"] = 1
            db.update("pages", row_id, data)
            audit.log("update", "pages", row_id, row["title"], before=row, after=data)
            flash("Page saved.", "ok")
            return redirect(url_for("admin.page_edit", row_id=row_id))

        sections = db.query(
            "SELECT * FROM sections WHERE page_id = ? ORDER BY sort_order, id", (row_id,))
        return render_template(
            "admin/page_form.html", row=row, sections=sections,
            types=sections_mod.SECTION_TYPES, title=row["title"])

    @bp.route("/pages/<int:row_id>/delete", methods=["POST"])
    @require_role("content")
    def page_delete(row_id):
        verify_csrf()
        row = db.one("SELECT * FROM pages WHERE id = ?", (row_id,))
        if not row:
            abort(404)
        if row["is_home"]:
            flash("The home page cannot be deleted. Mark another page as home first.", "error")
            return redirect(url_for("admin.page_edit", row_id=row_id))
        db.delete("pages", row_id)
        audit.log("delete", "pages", row_id, row["title"], before=row)
        flash("Page and its sections deleted.", "ok")
        return redirect(url_for("admin.pages_list"))

    @bp.route("/pages/reorder", methods=["POST"])
    @require_role("content")
    def pages_reorder():
        verify_csrf()
        ids = (request.get_json(silent=True, force=True) or {}).get("ids", [])
        for index, page_id in enumerate(ids):
            db.update("pages", int(page_id), {"sort_order": index})
        return jsonify({"ok": True})

    # ── sections ────────────────────────────────────────────────────────────
    @bp.route("/pages/<int:page_id>/sections/add", methods=["POST"])
    @require_role("content")
    def section_add(page_id):
        verify_csrf()
        page = db.one("SELECT * FROM pages WHERE id = ?", (page_id,))
        if not page:
            abort(404)
        type_key = request.form.get("type") or "richtext"
        spec = sections_mod.SECTION_TYPES.get(type_key)
        if not spec:
            flash("Unknown section type.", "error")
            return redirect(url_for("admin.page_edit", row_id=page_id))

        defaults = {}
        for field in spec.get("fields", []):
            if field.default is not None:
                defaults[field.name] = field.default

        section_id = db.insert("sections", {
            "page_id": page_id, "type": type_key, "name": spec["label"],
            "title": spec["label"], "data": dump_json(defaults),
            "sort_order": db.next_sort_order("sections", "page_id = ?", (page_id,)),
            "is_published": 0,
        })
        audit.log("create", "sections", section_id, f"{spec['label']} on {page['title']}")
        flash(f"{spec['label']} section added as a draft. Fill it in and publish.", "ok")
        return redirect(url_for("admin.section_edit", section_id=section_id))

    @bp.route("/sections/<int:section_id>", methods=["GET", "POST"])
    @require_role("content")
    def section_edit(section_id):
        row = db.one("SELECT * FROM sections WHERE id = ?", (section_id,))
        if not row:
            abort(404)
        page = db.one("SELECT * FROM pages WHERE id = ?", (row["page_id"],))
        fields = sections_mod.fields_for(row["type"])

        if request.method == "POST":
            verify_csrf()
            blob = load_json(row["data"], {})
            direct = {
                "name": (request.form.get("name") or "").strip(),
                "anchor": slugify(request.form.get("anchor") or "") if request.form.get("anchor") else "",
                "is_published": 1 if request.form.get("is_published") else 0,
                "updated_at": db.scalar("SELECT datetime('now')"),
            }
            for f in fields:
                if f.kind == "hours":
                    blob[f.name] = crud.read_hours(request.form, f.name)
                    continue
                if f.name not in request.form and f.kind not in ("checkbox", "bool"):
                    continue
                value = crud.coerce(f, request.form.get(f.name))
                if f.json:
                    blob[f.name] = value
                else:
                    direct[f.name] = value
            direct["data"] = dump_json(blob)
            db.update("sections", section_id, direct)
            audit.log("update", "sections", section_id,
                      f"{row['name'] or row['type']} on {page['title']}", before=row, after=direct)
            flash("Section saved.", "ok")
            return redirect(url_for("admin.section_edit", section_id=section_id))

        return render_template(
            "admin/section_form.html", row=row, page=page, fields=fields,
            blob=load_json(row["data"], {}), spec=sections_mod.SECTION_TYPES.get(row["type"], {}),
            title=row["name"] or sections_mod.type_label(row["type"]))

    @bp.route("/sections/<int:section_id>/delete", methods=["POST"])
    @require_role("content")
    def section_delete(section_id):
        verify_csrf()
        row = db.one("SELECT * FROM sections WHERE id = ?", (section_id,))
        if not row:
            abort(404)
        db.delete("sections", section_id)
        audit.log("delete", "sections", section_id, row["name"] or row["type"], before=row)
        flash("Section deleted.", "ok")
        return redirect(url_for("admin.page_edit", row_id=row["page_id"]))

    @bp.route("/sections/<int:section_id>/toggle", methods=["POST"])
    @require_role("content")
    def section_toggle(section_id):
        verify_csrf()
        row = db.one("SELECT * FROM sections WHERE id = ?", (section_id,))
        if not row:
            abort(404)
        value = 0 if row["is_published"] else 1
        db.update("sections", section_id, {"is_published": value})
        audit.log("update", "sections", section_id, row["name"] or row["type"],
                  before={"is_published": row["is_published"]}, after={"is_published": value})
        flash("Published." if value else "Unpublished, it is now hidden on the site.", "ok")
        return redirect(request.referrer or url_for("admin.page_edit", row_id=row["page_id"]))

    @bp.route("/sections/<int:section_id>/duplicate", methods=["POST"])
    @require_role("content")
    def section_duplicate(section_id):
        verify_csrf()
        row = db.one("SELECT * FROM sections WHERE id = ?", (section_id,))
        if not row:
            abort(404)
        new_id = db.insert("sections", {
            "page_id": row["page_id"], "type": row["type"],
            "name": (row["name"] or row["type"]) + " copy", "anchor": "",
            "eyebrow": row["eyebrow"], "title": row["title"], "subtitle": row["subtitle"],
            "body": row["body"], "data": row["data"],
            "sort_order": db.next_sort_order("sections", "page_id = ?", (row["page_id"],)),
            "is_published": 0,
        })
        audit.log("create", "sections", new_id, "duplicate of " + (row["name"] or row["type"]))
        flash("Section duplicated as a draft.", "ok")
        return redirect(url_for("admin.section_edit", section_id=new_id))

    @bp.route("/sections/reorder", methods=["POST"])
    @require_role("content")
    def sections_reorder():
        verify_csrf()
        ids = (request.get_json(silent=True, force=True) or {}).get("ids", [])
        for index, section_id in enumerate(ids):
            db.update("sections", int(section_id), {"sort_order": index})
        audit.log("update", "sections", "", f"reordered {len(ids)} sections")
        return jsonify({"ok": True, "count": len(ids)})

    @bp.route("/sections/<int:section_id>/move", methods=["POST"])
    @require_role("content")
    def section_move(section_id):
        """Keyboard and no-JS fallback for reordering."""
        verify_csrf()
        row = db.one("SELECT * FROM sections WHERE id = ?", (section_id,))
        if not row:
            abort(404)
        direction = -1 if request.form.get("dir") == "up" else 1
        siblings = db.query(
            "SELECT id FROM sections WHERE page_id = ? ORDER BY sort_order, id", (row["page_id"],))
        order = [r["id"] for r in siblings]
        index = order.index(section_id)
        target = index + direction
        if 0 <= target < len(order):
            order[index], order[target] = order[target], order[index]
            for position, sid in enumerate(order):
                db.update("sections", sid, {"sort_order": position})
        return redirect(url_for("admin.page_edit", row_id=row["page_id"]))
