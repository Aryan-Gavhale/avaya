"""EMI arithmetic and instalment schedules.

quote() is the single place the monthly figure is worked out, so the public
calculator, the apply form and the admin panel can never disagree.

    E = P * r * (1 + r)^n / ((1 + r)^n - 1)      r = annual rate / 12 / 100
    r = 0  ->  E = P / n                          (no-cost EMI)
"""

from __future__ import annotations

from datetime import date

from core import db
from core.util import add_months, parse_date, ref_code


def quote(amount: float, tenure_months: int, interest_rate: float = 0.0,
          processing_fee_pct: float = 0.0, downpayment_pct: float = 0.0) -> dict:
    amount = max(0.0, float(amount or 0))
    tenure = max(1, int(tenure_months or 1))
    rate = max(0.0, float(interest_rate or 0))

    downpayment = round(amount * float(downpayment_pct or 0) / 100.0, 2)
    financed = round(amount - downpayment, 2)
    fee = round(financed * float(processing_fee_pct or 0) / 100.0, 2)

    if rate <= 0:
        emi = financed / tenure
    else:
        r = rate / 12.0 / 100.0
        growth = (1 + r) ** tenure
        emi = financed * r * growth / (growth - 1)

    emi = round(emi, 2)
    total_emis = round(emi * tenure, 2)
    interest = round(total_emis - financed, 2)
    total_payable = round(downpayment + total_emis + fee, 2)

    return {
        "amount": round(amount, 2),
        "tenure_months": tenure,
        "interest_rate": rate,
        "downpayment": downpayment,
        "financed": financed,
        "processing_fee": fee,
        "monthly_emi": emi,
        "interest": interest,
        "total_emis": total_emis,
        "total_payable": total_payable,
        "extra_cost": round(interest + fee, 2),
    }


def quote_for_plan(amount: float, plan) -> dict:
    return quote(
        amount,
        plan["tenure_months"],
        plan["interest_rate"],
        plan["processing_fee_pct"],
        plan["downpayment_pct"],
    )


def plan_eligible(plan, amount: float) -> bool:
    amount = float(amount or 0)
    if plan["min_amount"] and amount < float(plan["min_amount"]):
        return False
    if plan["max_amount"] and amount > float(plan["max_amount"]):
        return False
    return True


def active_plans():
    return db.query("SELECT * FROM emi_plans WHERE is_active = 1 ORDER BY sort_order, tenure_months")


def plans_payload(amount: float | None = None) -> list[dict]:
    """Plain dicts for the client-side calculator."""
    out = []
    for plan in active_plans():
        item = {
            "id": plan["id"],
            "name": plan["name"],
            "provider": plan["provider"],
            "tenure": plan["tenure_months"],
            "rate": plan["interest_rate"],
            "fee_pct": plan["processing_fee_pct"],
            "down_pct": plan["downpayment_pct"],
            "min": plan["min_amount"],
            "max": plan["max_amount"],
            "notes": plan["notes"],
        }
        if amount is not None:
            item["quote"] = quote_for_plan(amount, plan)
            item["eligible"] = plan_eligible(plan, amount)
        out.append(item)
    return out


# ── schedule ────────────────────────────────────────────────────────────────
def build_schedule(application_id: int, replace: bool = True) -> int:
    """(Re)generate instalment rows for an application. Returns the row count."""
    app_row = db.one("SELECT * FROM emi_applications WHERE id = ?", (application_id,))
    if not app_row:
        return 0

    if replace:
        paid = int(db.scalar(
            "SELECT COUNT(*) FROM emi_installments WHERE application_id = ? AND status = 'paid'",
            (application_id,), 0))
        if paid:
            return 0  # never rewrite a schedule that already has payments against it

    tenure = int(app_row["tenure_months"] or 1)
    emi = float(app_row["monthly_emi"] or 0)
    start = parse_date(app_row["start_date"]) or date.today()

    total = round(emi * tenure, 2)
    rows = []
    running = 0.0
    for seq in range(1, tenure + 1):
        amount = emi
        if seq == tenure:  # absorb rounding drift in the final instalment
            amount = round(total - running, 2)
        running = round(running + amount, 2)
        rows.append((application_id, seq, add_months(start, seq).isoformat(), amount, "due"))

    # The clear-out and the rebuild are one step, so a failure part-way cannot
    # leave an application with no schedule at all.
    with db.transaction():
        if replace:
            db.execute("DELETE FROM emi_installments WHERE application_id = ?", (application_id,))
        db.executemany(
            "INSERT INTO emi_installments (application_id, seq, due_date, amount, status) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def schedule(application_id: int):
    return db.query(
        "SELECT i.*, p.receipt_no FROM emi_installments i "
        "LEFT JOIN payments p ON p.id = i.payment_id "
        "WHERE i.application_id = ? ORDER BY i.seq",
        (application_id,),
    )


def totals(application_id: int) -> dict:
    row = db.one(
        "SELECT COUNT(*) AS n, "
        "COALESCE(SUM(amount), 0) AS scheduled, "
        "COALESCE(SUM(CASE WHEN status = 'paid' THEN amount ELSE 0 END), 0) AS paid, "
        "COALESCE(SUM(CASE WHEN status = 'due' THEN amount ELSE 0 END), 0) AS outstanding, "
        "COALESCE(SUM(CASE WHEN status = 'due' AND due_date < date('now') THEN amount ELSE 0 END), 0) AS overdue, "
        "COALESCE(SUM(CASE WHEN status = 'due' AND due_date < date('now') THEN 1 ELSE 0 END), 0) AS overdue_count "
        "FROM emi_installments WHERE application_id = ?",
        (application_id,),
    )
    paid_cash = float(db.scalar(
        "SELECT COALESCE(SUM(amount), 0) FROM payments "
        "WHERE application_id = ? AND status = 'paid'", (application_id,), 0))
    data = dict(row) if row else {}
    data["collected"] = paid_cash
    return data


def next_receipt_no(prefix: str = "ANV") -> str:
    n = int(db.scalar("SELECT COUNT(*) FROM payments", (), 0)) + 1
    return f"{prefix}-{date.today().strftime('%y%m')}-{n:04d}"


def new_application_ref() -> str:
    return ref_code("EMI")


STATUS_FLOW = {
    "submitted": ["under_review", "approved", "rejected", "cancelled"],
    "under_review": ["approved", "rejected", "cancelled"],
    "approved": ["active", "cancelled"],
    "active": ["completed", "defaulted"],
    "rejected": ["under_review"],
    "defaulted": ["active", "completed"],
    "completed": [],
    "cancelled": ["submitted"],
}

STATUS_LABELS = {
    "submitted": "Submitted",
    "under_review": "Under review",
    "approved": "Approved",
    "rejected": "Rejected",
    "active": "Active",
    "completed": "Completed",
    "defaulted": "Defaulted",
    "cancelled": "Cancelled",
}

STATUS_TONE = {
    "submitted": "info",
    "under_review": "warn",
    "approved": "good",
    "active": "good",
    "completed": "neutral",
    "rejected": "bad",
    "defaulted": "bad",
    "cancelled": "neutral",
}
