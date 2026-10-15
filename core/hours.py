"""Opening hours: is the clinic open right now, and what does today look like."""

from __future__ import annotations

from datetime import date, datetime, time

from core import settings
from core.util import load_json

DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_LABELS = {
    "mon": "Monday", "tue": "Tuesday", "wed": "Wednesday", "thu": "Thursday",
    "fri": "Friday", "sat": "Saturday", "sun": "Sunday",
}


def _parse(value: str) -> time | None:
    try:
        hh, mm = str(value).split(":")[:2]
        return time(int(hh), int(mm))
    except (ValueError, TypeError, AttributeError):
        return None


def pretty(value: str) -> str:
    parsed = _parse(value)
    if not parsed:
        return str(value or "")
    hour = parsed.hour % 12 or 12
    suffix = "am" if parsed.hour < 12 else "pm"
    if parsed.minute:
        return f"{hour}.{parsed.minute:02d}{suffix}"
    return f"{hour}{suffix}"


def week(hours=None) -> list[dict]:
    data = load_json(hours, None) if hours else None
    if not data:
        data = settings.get("hours.week", {})
    today_key = DAYS[date.today().weekday()]
    rows = []
    for key in DAYS:
        span = data.get(key) or []
        rows.append({
            "key": key,
            "label": DAY_LABELS[key],
            "short": DAY_LABELS[key][:3],
            "closed": not span,
            "open": pretty(span[0]) if span else "",
            "close": pretty(span[1]) if len(span) > 1 else "",
            "text": f"{pretty(span[0])} - {pretty(span[1])}" if len(span) > 1 else "Closed",
            "is_today": key == today_key,
        })
    return rows


def is_holiday(when: date | None = None) -> str | None:
    when = when or date.today()
    for entry in settings.get("hours.holidays", []) or []:
        if isinstance(entry, dict):
            if str(entry.get("date")) == when.isoformat():
                return entry.get("label", "Closed")
        elif str(entry) == when.isoformat():
            return "Closed"
    return None


def state(hours=None) -> dict:
    """{open_now, label, detail} for the header pill and branch cards."""
    now = datetime.now()
    rows = week(hours)
    today = next(r for r in rows if r["is_today"])
    holiday = is_holiday()

    if holiday:
        return {"open_now": False, "label": "Closed today", "detail": holiday,
                "today": today}

    if today["closed"]:
        upcoming = _next_open(rows)
        return {"open_now": False, "label": "Closed today",
                "detail": f"Opens {upcoming['short']} at {upcoming['open']}" if upcoming else "",
                "today": today}

    data = load_json(hours, None) if hours else None
    if not data:
        data = settings.get("hours.week", {})
    span = data.get(today["key"]) or []
    start = _parse(span[0]) if span else None
    end = _parse(span[1]) if len(span) > 1 else None

    if start and end and start <= now.time() <= end:
        return {"open_now": True, "label": "Open now",
                "detail": f"Until {pretty(span[1])} today", "today": today}
    if start and now.time() < start:
        return {"open_now": False, "label": "Closed",
                "detail": f"Opens today at {pretty(span[0])}", "today": today}

    upcoming = _next_open(rows)
    return {"open_now": False, "label": "Closed",
            "detail": f"Opens {upcoming['short']} at {upcoming['open']}" if upcoming else "",
            "today": today}


def _next_open(rows: list[dict]) -> dict | None:
    start = date.today().weekday()
    for offset in range(1, 8):
        row = rows[(start + offset) % 7]
        if not row["closed"]:
            return row
    return None


def compact(hours=None) -> list[dict]:
    """Collapse the week into as few readable lines as possible:
    [{'days': 'Mon - Fri', 'text': '9.30am - 8pm'}, {'days': 'Sun', 'text': 'Closed'}]"""
    rows = week(hours)
    lines: list[dict] = []
    run: list[dict] = []

    def flush():
        if not run:
            return
        days = run[0]["short"] if len(run) == 1 else f"{run[0]['short']} - {run[-1]['short']}"
        lines.append({"days": days, "text": run[0]["text"],
                      "closed": run[0]["closed"],
                      "is_today": any(r["is_today"] for r in run)})

    for row in rows:
        if run and row["text"] != run[-1]["text"]:
            flush()
            run = []
        run.append(row)
    flush()
    return lines
