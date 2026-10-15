"""Settings: brand, contact, theme, SEO, forms, EMI and opening hours.

Each group is a list of Field specs, so the settings screens use exactly the same
form renderer as every other admin form.
"""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from core import audit, crud, db, settings
from core.auth import require_role, verify_csrf
from core.crud import Field, coerce, read_hours
from core.util import dump_json, parse_int

GROUPS: dict[str, dict] = {
    "brand": {
        "label": "Practice and contact",
        "blurb": "The name, the numbers and the address used across the site, the schema markup "
                 "and every automated message.",
        "fields": [
            Field("brand.name", "Practice name", "text", required=True, span=6),
            Field("brand.tagline", "Tagline", "text", span=6),
            Field("brand.short", "Short name", "text", span=4,
                  help="Used where space is tight."),
            Field("brand.city", "City", "text", span=4),
            Field("brand.established", "Established", "text", span=4),
            Field("brand.logo_media_id", "Logo", "media",
                  help="Optional. Without one, the site uses the tooth mark and the name."),
            Field("contact.phone", "Main phone", "tel", span=4),
            Field("contact.phone_display", "Phone as displayed", "text", span=4),
            Field("contact.emergency", "Out of hours number", "tel", span=4),
            Field("contact.whatsapp", "WhatsApp number", "text", span=4,
                  help="Country code and digits only, e.g. 919000012345."),
            Field("contact.email", "Email", "email", span=4),
            Field("contact.map_url", "Map link", "url", span=4),
            Field("contact.address", "Address", "text"),
        ],
    },
    "social": {
        "label": "Social links",
        "blurb": "Shown in the footer. Leave a field blank to hide that link.",
        "fields": [
            Field("social.instagram", "Instagram", "url", span=6),
            Field("social.facebook", "Facebook", "url", span=6),
            Field("social.youtube", "YouTube", "url", span=6),
            Field("social.google", "Google profile", "url", span=6),
        ],
    },
    "theme": {
        "label": "Theme",
        "blurb": "Colours and type are written into the page as custom properties, so rebranding "
                 "is this form rather than a code change.",
        "fields": [
            Field("theme_site", "Website", "heading",
                  help="The public site. Buttons, links and bands use these."),
            Field("theme.primary", "Primary", "color", span=3),
            Field("theme.primary_dark", "Primary, dark", "color", span=3),
            Field("theme.accent", "Accent", "color", span=3,
                  help="Stars, eyebrows on dark bands."),
            Field("theme.ink", "Text", "color", span=3),
            Field("theme.muted", "Muted text", "color", span=3),
            Field("theme.surface", "Surface", "color", span=3),
            Field("theme.canvas", "Alternate section", "color", span=3),
            Field("theme.radius", "Corner radius", "int", span=3, suffix="px"),
            Field("theme.font_display", "Display font", "text", span=4),
            Field("theme.font_body", "Body font", "text", span=4),
            Field("theme.animations", "Scroll animations", "checkbox", span=4,
                  help="Off disables every reveal, counter and parallax effect."),
            Field("theme.font_url", "Web font stylesheet", "text",
                  help="A Google Fonts or self-hosted CSS URL that provides both families."),
            Field("theme_admin", "Admin panel", "heading",
                  help="The sidebar highlight, hover tint, buttons and focus rings are all mixed "
                       "from the accent at fixed strengths, so one colour restyles the panel."),
            Field("admin.accent", "Accent", "color", span=3),
            Field("admin.canvas", "Background", "color", span=3),
            Field("admin.sidebar", "Sidebar", "color", span=3),
            Field("admin.ink", "Text", "color", span=3),
        ],
    },
    "seo": {
        "label": "SEO",
        "blurb": "Defaults for pages that have no meta of their own. sitemap.xml and robots.txt "
                 "are generated from this and the published pages.",
        "fields": [
            Field("seo.title_suffix", "Title suffix", "text", span=6),
            Field("seo.indexable", "Allow search engines", "checkbox", span=6,
                  help="Off serves a blanket Disallow in robots.txt and adds noindex."),
            Field("seo.default_description", "Default description", "textarea", rows=3),
            Field("seo.og_media_id", "Social sharing image", "media"),
        ],
    },
    "enquiry": {
        "label": "Enquiry form",
        "blurb": "What patients see after they submit, and the time slots they can choose from.",
        "fields": [
            Field("enquiry.success_title", "Confirmation heading", "text"),
            Field("enquiry.success_body", "Confirmation message", "textarea", rows=3),
            Field("enquiry.slots", "Time slots", "lines", rows=5,
                  help="One per line. Shown as chips on the form."),
            Field("enquiry.notify_email", "Copy new enquiries to", "email",
                  help="Recorded for your own reference. No mail server is configured, so the "
                       "panel is the source of truth."),
        ],
    },
    "emi": {
        "label": "EMI",
        "blurb": "Wording and receipt numbering. The plans themselves live under EMI plans.",
        "fields": [
            Field("emi.enabled", "Offer EMI", "checkbox", span=6),
            Field("emi.receipt_prefix", "Receipt prefix", "text", span=6,
                  help="Receipts are numbered PREFIX-YYMM-0001."),
            Field("emi.note", "Note under the calculator", "textarea", rows=3),
        ],
    },
    "hours": {
        "label": "Opening hours",
        "blurb": "Drives the open / closed pill in the header. Individual clinics can override "
                 "these on their own record.",
        "fields": [
            Field("hours.week", "Hours", "hours"),
            Field("hours.note", "Note", "text"),
            Field("hours.holidays", "Closures", "lines", rows=5,
                  line_keys=("date", "label"),
                  help="One per line as YYYY-MM-DD | reason."),
        ],
    },
}


def register(bp) -> None:

    @bp.route("/settings")
    @bp.route("/settings/<group>")
    @require_role("settings")
    def settings_home(group="brand"):
        if group not in GROUPS:
            group = "brand"
        return render_template(
            "admin/settings.html", title="Settings", groups=GROUPS, group=group,
            spec=GROUPS[group], values=settings.all_settings(),
            defaults={k: v for k, v in settings.DEFAULTS.items()
                      if k.startswith(("theme.", "admin."))})

    @bp.route("/settings/<group>/save", methods=["POST"])
    @require_role("settings")
    def settings_save(group):
        verify_csrf()
        spec = GROUPS.get(group)
        if not spec:
            flash("Unknown settings group.", "error")
            return redirect(url_for("admin.settings_home"))

        before = {}
        changes = {}
        bad_colours = []
        for f in spec["fields"]:
            if f.kind == "heading":
                continue
            if f.kind == "hours":
                value = read_hours(request.form, f.name)
            elif f.name not in request.form and f.kind not in ("checkbox", "bool"):
                continue
            else:
                value = coerce(f, request.form.get(f.name))
                if f.kind in ("checkbox", "bool"):
                    value = bool(value)
            if f.kind == "color":
                # A blank colour goes back to the default rather than leaving
                # the stylesheet without a value.
                value = value or settings.DEFAULTS.get(f.name)
                if not settings.HEX_COLOUR.match(str(value or "")):
                    bad_colours.append(f.label if f.name.startswith("theme.") else f"Admin {f.label.lower()}")
                    continue
            before[f.name] = settings.get(f.name)
            changes[f.name] = value

        if bad_colours:
            flash(f"{', '.join(bad_colours)}: use a hex colour such as #22C57E. Nothing was saved.",
                  "error")
            return redirect(url_for("admin.settings_home", group=group))

        settings.set_many(changes)
        audit.log("update", "settings", group, spec["label"], before=before, after=changes)
        flash(f"{spec['label']} saved.", "ok")
        return redirect(url_for("admin.settings_home", group=group))

    @bp.route("/settings/reset/<key>", methods=["POST"])
    @require_role("settings")
    def settings_reset(key):
        verify_csrf()
        if key not in settings.DEFAULTS:
            flash("That setting has no default to restore.", "error")
        else:
            settings.set(key, settings.DEFAULTS[key])
            audit.log("update", "settings", key, f"reset {key} to the default")
            flash(f"{key} reset to the shipped default.", "ok")
        return redirect(request.referrer or url_for("admin.settings_home"))
