"""Assignments model arbitrary employee groups as effective-dated rows."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Policy, PolicyAssignment


class AssignmentError(ValueError):
    pass


def assign(
    session: Session,
    *,
    policy: Policy,
    employee_ids: list[str],
    effective_from: date,
    actor_id: str,
) -> list[PolicyAssignment]:
    created = []
    for employee_id in employee_ids:
        row = PolicyAssignment(
            company_id=policy.company_id,
            employee_id=employee_id,
            policy_id=policy.id,
            category_id=policy.category_id,
            effective_from=effective_from,
            created_by=actor_id,
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            raise AssignmentError(
                f"{employee_id} already has a policy in this category for that date."
            ) from exc
        created.append(row)
    return created


def assignments_for_employee(
    session: Session, *, employee_id: str, on_date: date | None = None
) -> list[PolicyAssignment]:
    query = select(PolicyAssignment).where(
        PolicyAssignment.employee_id == employee_id
    )
    if on_date:
        query = query.where(
            PolicyAssignment.effective_from <= on_date,
            (PolicyAssignment.effective_to.is_(None))
            | (PolicyAssignment.effective_to >= on_date),
        )
    return list(session.scalars(query.order_by(PolicyAssignment.effective_from)))


def assignment_for_category(
    session: Session, *, employee_id: str, category_id: str, on_date: date
) -> PolicyAssignment | None:
    return session.execute(
        select(PolicyAssignment).where(
            PolicyAssignment.employee_id == employee_id,
            PolicyAssignment.category_id == category_id,
            PolicyAssignment.effective_from <= on_date,
            (PolicyAssignment.effective_to.is_(None))
            | (PolicyAssignment.effective_to >= on_date),
        )
    ).scalar_one_or_none()


def end(
    session: Session, *, assignment: PolicyAssignment, effective_to: date
) -> PolicyAssignment:
    if effective_to < assignment.effective_from:
        raise AssignmentError("An assignment cannot end before it starts.")
    if assignment.effective_to is not None:
        raise AssignmentError("This assignment has already ended.")
    assignment.effective_to = effective_to
    session.flush()
    return assignment
