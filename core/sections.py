"""The section catalogue.

A page is an ordered list of typed sections. Each type declares which of the
shared columns it uses (eyebrow / title / subtitle / body) plus its own fields,
which are stored in `sections.data` as JSON. Each type also maps to a partial in
templates/public/sections/, so adding a section type is two edits: an entry here
and a template with a matching name.
"""

from __future__ import annotations

from core import db
from core.crud import Field

SHARED_HELP = "Leave blank to hide this line on the page."


def _service_options():
    rows = db.query("SELECT id, name FROM services ORDER BY sort_order, name")
    return [("", "- any -")] + [(r["id"], r["name"]) for r in rows]


def _category_options():
    rows = db.query("SELECT id, name FROM service_categories ORDER BY sort_order, name")
    return [("", "- all categories -")] + [(r["id"], r["name"]) for r in rows]


def _gallery_options():
    rows = db.query("SELECT id, name FROM galleries ORDER BY name")
    return [("", "- none -")] + [(r["id"], r["name"]) for r in rows]


def _faq_category_options():
    rows = db.query("SELECT DISTINCT category FROM faqs ORDER BY category")
    return [("", "- all -")] + [(r["category"], r["category"]) for r in rows]


TONE_OPTIONS = [("light", "Light"), ("canvas", "Soft grey"), ("deep", "Deep teal"),
                ("ink", "Near black")]

SECTION_TYPES: dict[str, dict] = {
    "hero": {
        "label": "Hero",
        "blurb": "Opening statement, headline image and the two main buttons.",
        "uses": ["eyebrow", "title", "subtitle"],
        "fields": [
            Field("media_id", "Hero image", "media", json=True, span=6,
                  help="Landscape works best. 1600px wide or more."),
            Field("secondary_media_id", "Inset image", "media", json=True, span=6,
                  help="Small overlapping image. Optional."),
            Field("badge", "Badge", "text", json=True, span=6,
                  placeholder="ISO-certified sterilisation"),
            Field("rating_note", "Rating line", "text", json=True, span=6,
                  help="Leave blank to pull the live Google rating instead."),
            Field("points", "Reassurance points", "lines", json=True,
                  line_keys=("text",), rows=4,
                  help="One per line. Shown as a ticked list under the buttons."),
            Field("primary_label", "Primary button", "text", json=True, span=6,
                  default="Book an appointment"),
            Field("primary_url", "Primary link", "text", json=True, span=6, default="#enquiry"),
            Field("secondary_label", "Secondary button", "text", json=True, span=6,
                  default="See treatments"),
            Field("secondary_url", "Secondary link", "text", json=True, span=6, default="#services"),
        ],
    },
    "stats": {
        "label": "Trust numbers",
        "blurb": "Three to five counters that animate as they scroll in.",
        "uses": ["eyebrow", "title"],
        "fields": [
            Field("items", "Numbers", "lines", json=True,
                  line_keys=("value", "suffix", "label"), rows=6,
                  help="One per line as value | suffix | label. Example: 24000 | + | patients treated"),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="canvas", span=6),
        ],
    },
    "services": {
        "label": "Treatments grid",
        "blurb": "Cards pulled from the Services table.",
        "uses": ["eyebrow", "title", "subtitle"],
        "fields": [
            Field("mode", "Which treatments", "select", json=True, span=6, default="featured",
                  options=[("featured", "Featured only"), ("all", "All published"),
                           ("category", "One category")]),
            Field("category_id", "Category", "select", json=True, span=6,
                  options=_category_options,
                  help="Used when 'One category' is selected above."),
            Field("limit", "Maximum cards", "int", json=True, span=6, default=6),
            Field("show_price", "Show price bands", "checkbox", json=True, span=6, default=1),
            Field("cta_label", "Footer link text", "text", json=True, span=6,
                  default="All treatments and fees"),
            Field("cta_url", "Footer link", "text", json=True, span=6, default="/treatments"),
        ],
    },
    "about": {
        "label": "About / two column",
        "blurb": "Image on one side, copy and bullet points on the other.",
        "uses": ["eyebrow", "title", "subtitle", "body"],
        "fields": [
            Field("media_id", "Image", "media", json=True, span=6),
            Field("flip", "Image on the right", "checkbox", json=True, span=6),
            Field("points", "Bullet points", "lines", json=True,
                  line_keys=("title", "text"), rows=6,
                  help="One per line as heading | description."),
            Field("cta_label", "Button", "text", json=True, span=6),
            Field("cta_url", "Button link", "text", json=True, span=6),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="light", span=6),
        ],
    },
    "gallery": {
        "label": "Clinic gallery",
        "blurb": "Photographs of the practice with a lightbox.",
        "uses": ["eyebrow", "title", "subtitle"],
        "fields": [
            Field("gallery_id", "Gallery", "select", json=True, span=6, options=_gallery_options),
            Field("layout", "Layout", "select", json=True, span=6, default="mosaic",
                  options=[("mosaic", "Mosaic"), ("grid", "Even grid"), ("rail", "Scrolling rail")]),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="light", span=6),
        ],
    },
    "doctors": {
        "label": "Clinicians",
        "blurb": "Cards from the Doctors table.",
        "uses": ["eyebrow", "title", "subtitle"],
        "fields": [
            Field("limit", "Maximum cards", "int", json=True, span=6, default=4),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="canvas", span=6),
        ],
    },
    "reviews": {
        "label": "Google reviews",
        "blurb": "Live rating summary and reviews, with curated fallback.",
        "uses": ["eyebrow", "title", "subtitle"],
        "fields": [
            Field("source", "Source", "select", json=True, span=6, default="auto",
                  options=[("auto", "Google, fall back to curated"),
                           ("google", "Google only"), ("manual", "Curated only")]),
            Field("limit", "Maximum reviews", "int", json=True, span=6, default=6),
            Field("show_summary", "Show rating summary", "checkbox", json=True, span=6, default=1),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="light", span=6),
        ],
    },
    "emi": {
        "label": "EMI calculator",
        "blurb": "Live monthly-payment calculator driven by the EMI plans.",
        "uses": ["eyebrow", "title", "subtitle", "body"],
        "fields": [
            Field("default_amount", "Starting amount", "int", json=True, span=6, default=60000),
            Field("max_amount", "Slider maximum", "int", json=True, span=6, default=400000),
            Field("points", "Points beside the calculator", "lines", json=True,
                  line_keys=("title", "text"), rows=5,
                  help="One per line as heading | description."),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="deep", span=6),
        ],
    },
    "branches": {
        "label": "Locations",
        "blurb": "Address, hours and directions for each branch.",
        "uses": ["eyebrow", "title", "subtitle"],
        "fields": [
            Field("show_map", "Show map embed", "checkbox", json=True, span=6, default=1),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="canvas", span=6),
        ],
    },
    "faq": {
        "label": "FAQ accordion",
        "blurb": "Questions from the FAQ table.",
        "uses": ["eyebrow", "title", "subtitle"],
        "fields": [
            Field("category", "Category", "select", json=True, span=6,
                  options=_faq_category_options),
            Field("limit", "Maximum questions", "int", json=True, span=6, default=8),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="light", span=6),
        ],
    },
    "enquiry": {
        "label": "Enquiry form",
        "blurb": "The appointment request form. Submissions land in Enquiries.",
        "uses": ["eyebrow", "title", "subtitle", "body"],
        "fields": [
            Field("show_service", "Ask which treatment", "checkbox", json=True, span=6, default=1),
            Field("show_branch", "Ask which location", "checkbox", json=True, span=6, default=1),
            Field("show_slot", "Ask for a preferred time", "checkbox", json=True, span=6, default=1),
            Field("side_points", "Points beside the form", "lines", json=True,
                  line_keys=("title", "text"), rows=5,
                  help="One per line as heading | description."),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="light", span=6),
        ],
    },
    "cta": {
        "label": "Call to action band",
        "blurb": "One strong line with a button.",
        "uses": ["eyebrow", "title", "subtitle"],
        "fields": [
            Field("media_id", "Background image", "media", json=True, span=6),
            Field("primary_label", "Button", "text", json=True, span=6,
                  default="Book an appointment"),
            Field("primary_url", "Button link", "text", json=True, span=6, default="#enquiry"),
            Field("secondary_label", "Second button", "text", json=True, span=6),
            Field("secondary_url", "Second link", "text", json=True, span=6),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="ink", span=6),
        ],
    },
    "process": {
        "label": "How it works",
        "blurb": "Numbered steps with a progress line.",
        "uses": ["eyebrow", "title", "subtitle"],
        "fields": [
            Field("items", "Steps", "lines", json=True, line_keys=("title", "text"), rows=6,
                  help="One per line as heading | description."),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="light", span=6),
        ],
    },
    "richtext": {
        "label": "Text block",
        "blurb": "A heading and paragraphs. Blank lines become new paragraphs.",
        "uses": ["eyebrow", "title", "subtitle", "body"],
        "fields": [
            Field("width", "Width", "select", json=True, span=6, default="narrow",
                  options=[("narrow", "Narrow column"), ("wide", "Full width")]),
            Field("tone", "Background", "select", json=True, options=TONE_OPTIONS,
                  default="light", span=6),
        ],
    },
    "trust": {
        "label": "Assurance strip",
        "blurb": "A row of short guarantees or accreditations.",
        "uses": [],
        "fields": [
            Field("items", "Items", "lines", json=True, line_keys=("title", "text"), rows=6,
                  help="One per line as heading | description."),
        ],
    },
}

SHARED_FIELDS = {
    "eyebrow": Field("eyebrow", "Eyebrow", "text", span=4,
                     help="Small label above the heading."),
    "title": Field("title", "Heading", "text", span=8),
    "subtitle": Field("subtitle", "Standfirst", "textarea", rows=2,
                      help="One or two sentences under the heading."),
    "body": Field("body", "Body copy", "textarea", rows=8,
                  help="Blank lines start a new paragraph."),
}


def type_label(type_key: str) -> str:
    return SECTION_TYPES.get(type_key, {}).get("label", type_key.title())


def type_blurb(type_key: str) -> str:
    return SECTION_TYPES.get(type_key, {}).get("blurb", "")


def fields_for(type_key: str) -> list[Field]:
    spec = SECTION_TYPES.get(type_key)
    if not spec:
        return [SHARED_FIELDS["title"], SHARED_FIELDS["body"]]
    shared = [SHARED_FIELDS[name] for name in spec.get("uses", []) if name in SHARED_FIELDS]
    return shared + list(spec.get("fields", []))


def type_choices() -> list[tuple[str, str]]:
    return [(key, spec["label"]) for key, spec in SECTION_TYPES.items()]
