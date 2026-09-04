"""Read balances from the ledger, with explicit no-policy rows."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import enums
from app.models import TimeOffCategory
from app.services import assignment_service, ledger_service, policy_service


def list_balances(session: Session, *, company_id: str, employee_id: str, on_date: date):
    rows = []
    categories = session.scalars(
        select(TimeOffCategory)
        .where(TimeOffCategory.company_id == company_id)
        .order_by(TimeOffCategory.name)
    )
    for category in categories:
        assignment = assignment_service.assignment_for_category(
            session,
            employee_id=employee_id,
            category_id=category.id,
            on_date=on_date,
        )
        if assignment is None:
            rows.append({
                "category_id": category.id,
                "category_name": category.name,
                "has_policy": False,
                "policy_id": None,
                "policy_name": None,
                "is_unlimited": False,
                "balance_minutes": 0,
                "day_minutes": 480,
            })
            continue
        version = policy_service.version_effective_on(
            session, assignment.policy_id, on_date
        )
        rows.append({
            "category_id": category.id,
            "category_name": category.name,
            "has_policy": True,
            "policy_id": assignment.policy_id,
            "policy_name": assignment.policy.name,
            "is_unlimited": version.kind == enums.PolicyKind.UNLIMITED,
            "balance_minutes": ledger_service.balance(
                session, employee_id=employee_id, policy_id=assignment.policy_id
            ),
            "day_minutes": 480,
        })
    return rows
