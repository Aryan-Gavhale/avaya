"""Small helpers shared by the public site and the admin panel."""

from __future__ import annotations

import json
import re
import secrets
import unicodedata
from datetime import date, datetime, timedelta

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(value: str, fallback: str = "item") -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    text = _SLUG_STRIP.sub("-", text.lower()).strip("-")
    return text or fallback


def unique_slug(value: str, exists) -> str:
    """`exists(slug) -> bool` decides whether a candidate is taken."""
    base = slugify(value)
    candidate = base
    n = 2
    while exists(candidate):
        candidate = f"{base}-{n}"
        n += 1
    return candidate


def ref_code(prefix: str, length: int = 5) -> str:
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    tail = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}-{tail}"


def client_ip() -> str:
    """The address to rate-limit and log against.

    X-Forwarded-For is only read when TRUSTED_PROXIES says a proxy really is in
    front of us, because anything self-reported by the caller can be rotated per
    request, which would make every per-IP limit here decorative.
    """
    from flask import current_app, request

    remote = request.remote_addr or ""
    hops = int(current_app.config.get("TRUSTED_PROXIES", 0) or 0)
    if hops <= 0:
        return remote

    chain = [p.strip() for p in (request.headers.get("X-Forwarded-For") or "").split(",") if p.strip()]
    if not chain:
        return remote
    # The rightmost entries were added by our own proxies; step back over them.
    index = max(0, len(chain) - hops)
    return chain[index] if index < len(chain) else chain[0]


_CSV_TRIGGER = ("=", "+", "-", "@", "\t", "\r")


def csv_cell(value) -> str:
    """Defuse spreadsheet formula injection.

    Enquiry names and messages come from anonymous visitors and end up in a file
    staff open in Excel, where a leading = + - @ is executed. Prefixing with an
    apostrophe makes the cell text, which is what it always was.
    """
    text = "" if value is None else str(value)
    if text[:1] in _CSV_TRIGGER:
        return "'" + text
    return text


def inr(value, decimals: int = 0) -> str:
    """Format a number the Indian way: 12,34,567."""
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        return "-"
    negative = amount < 0
    amount = abs(amount)
    whole = int(amount)
    frac = amount - whole
    digits = str(whole)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        digits = f"{head},{tail}"
    out = digits
    if decimals:
        out = f"{digits}.{int(round(frac * (10 ** decimals))):0{decimals}d}"
    return ("-" if negative else "") + out


def money(value, decimals: int = 0) -> str:
    return "\u20b9" + inr(value, decimals)


def parse_float(value, default=0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(str(value).replace(",", "").replace("\u20b9", "").strip())
    except (TypeError, ValueError):
        return default


def parse_int(value, default=0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def parse_bool(value) -> bool:
    return str(value).strip().lower() in {"1", "true", "on", "yes", "y"}


def load_json(raw, default=None):
    if isinstance(raw, (dict, list)):
        return raw
    if not raw:
        return default if default is not None else {}
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default if default is not None else {}


def dump_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def today_iso() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_date(value, default=None):
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except (ValueError, TypeError, AttributeError):
            continue
    return default


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    # clamp to the last valid day of the target month
    day = start.day
    while day > 28:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1
    return date(year, month, day)


def pretty_date(value, fmt: str = "%d %b %Y") -> str:
    parsed = parse_date(value)
    if parsed:
        return parsed.strftime(fmt)
    try:
        return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").strftime(fmt)
    except (ValueError, TypeError):
        return str(value or "")


def pretty_datetime(value, fmt: str = "%d %b %Y, %H:%M") -> str:
    try:
        return datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S").strftime(fmt)
    except (ValueError, TypeError):
        return pretty_date(value, fmt)


def time_ago(value) -> str:
    try:
        stamp = datetime.strptime(str(value)[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        parsed = parse_date(value)
        if not parsed:
            return ""
        stamp = datetime.combine(parsed, datetime.min.time())
    delta = datetime.now() - stamp
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        mins = seconds // 60
        return f"{mins} min ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    days = seconds // 86400
    if days < 30:
        return f"{days} day{'s' if days > 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months > 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years > 1 else ''} ago"


def days_until(value) -> int | None:
    parsed = parse_date(value)
    if not parsed:
        return None
    return (parsed - date.today()).days


def week_bounds(reference: date | None = None) -> tuple[str, str]:
    ref = reference or date.today()
    start = ref - timedelta(days=ref.weekday())
    return start.isoformat(), (start + timedelta(days=7)).isoformat()


def clean_phone(value: str) -> str:
    return re.sub(r"[^\d+]", "", value or "")


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


def valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match((value or "").strip()))


def valid_phone(value: str) -> bool:
    digits = re.sub(r"\D", "", value or "")
    return 8 <= len(digits) <= 15


def truncate(value: str, length: int = 120) -> str:
    text = (value or "").strip()
    if len(text) <= length:
        return text
    return text[: length - 1].rstrip() + "\u2026"


def initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def split_list(value: str, sep: str = ",") -> list[str]:
    return [p.strip() for p in (value or "").split(sep) if p.strip()]
