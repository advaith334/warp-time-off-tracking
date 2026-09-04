"""Request transactions: frozen costs, holds, decisions, and reversals."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import enums
from app.domain.requests import RequestError, request_days
from app.models import (
    BalanceSnapshot,
    PolicyVersion,
    RequestDay,
    RequestEvent,
    TimeOffRequest,
)
from app.services import assignment_service, ledger_service, policy_service

LIVE = (enums.RequestStatus.PENDING, enums.RequestStatus.APPROVED)


def _snapshot(
    session: Session, *, employee_id: str, policy_id: str, lock: bool = False
) -> BalanceSnapshot:
    query = select(BalanceSnapshot).where(
        BalanceSnapshot.employee_id == employee_id,
        BalanceSnapshot.policy_id == policy_id,
    )
    if lock:
        query = query.with_for_update()
    row = session.scalar(query)
    if row is None:
        row = BalanceSnapshot(
            employee_id=employee_id,
            policy_id=policy_id,
            balance_minutes=ledger_service.balance(
                session, employee_id=employee_id, policy_id=policy_id
            ),
            pending_hold_minutes=0,
        )
        session.add(row)
        session.flush()
    return row


def preview(
    session: Session,
    *,
    employee_id: str,
    category_id: str,
    start_date: date,
    end_date: date,
    partial_minutes: int | None,
    lock_balance: bool = False,
) -> dict:
    assignment = assignment_service.assignment_for_category(
        session,
        employee_id=employee_id,
        category_id=category_id,
        on_date=start_date,
    )
    if assignment is None or (
        assignment.effective_to is not None and assignment.effective_to < end_date
    ):
        raise RequestError("No policy covers this employee for the full request range.")
    version = policy_service.version_effective_on(
        session, assignment.policy_id, start_date
    )
    if version is None:
        raise RequestError("No policy version is effective on the request date.")
    days = request_days(
        start=start_date,
        end=end_date,
        partial_minutes=partial_minutes,
    )
    overlap = session.scalar(
        select(TimeOffRequest.id).where(
            TimeOffRequest.employee_id == employee_id,
            TimeOffRequest.status.in_(LIVE),
            TimeOffRequest.start_date <= end_date,
            TimeOffRequest.end_date >= start_date,
        ).limit(1)
    )
    if overlap:
        raise RequestError("This request overlaps another pending or approved request.")

    total = sum(minutes for _, minutes in days)
    snapshot = _snapshot(
        session,
        employee_id=employee_id,
        policy_id=assignment.policy_id,
        lock=lock_balance,
    )
    available = snapshot.balance_minutes - snapshot.pending_hold_minutes
    floor = version.negative_floor_minutes if version.allow_negative else 0
    if version.kind != enums.PolicyKind.UNLIMITED and available - total < floor:
        raise RequestError("The request exceeds the available balance.")
    return {
        "assignment": assignment,
        "version": version,
        "days": days,
        "total_minutes": total,
        "available_minutes": available,
    }


def submit(session: Session, *, actor_id: str, reason: str, **request) -> TimeOffRequest:
    result = preview(session, lock_balance=True, **request)
    assignment = result["assignment"]
    version = result["version"]
    row = TimeOffRequest(
        company_id=assignment.company_id,
        employee_id=request["employee_id"],
        policy_id=assignment.policy_id,
        policy_version_id=version.id,
        category_id=request["category_id"],
        reason=reason,
        status=enums.RequestStatus.PENDING,
        start_date=request["start_date"],
        end_date=request["end_date"],
        total_minutes=result["total_minutes"],
        is_partial_day=request["partial_minutes"] is not None,
        created_by=actor_id,
    )
    row.days = [RequestDay(date=day, minutes=minutes) for day, minutes in result["days"]]
    row.events = [
        RequestEvent(
            from_status=None,
            to_status=enums.RequestStatus.PENDING,
            actor_id=actor_id,
        )
    ]
    session.add(row)
    if version.kind != enums.PolicyKind.UNLIMITED:
        snapshot = _snapshot(
            session, employee_id=row.employee_id, policy_id=row.policy_id, lock=True
        )
        snapshot.pending_hold_minutes += row.total_minutes
    session.flush()
    return row


def decide(
    session: Session,
    *,
    request: TimeOffRequest,
    approve: bool,
    actor_id: str,
    note: str | None,
) -> TimeOffRequest:
    if request.status != enums.RequestStatus.PENDING:
        raise RequestError("Only a pending request can be decided.")
    version_id = request.policy_version_id
    policy_version = policy_service.version_effective_on(
        session, request.policy_id, request.start_date
    )
    if policy_version is None or policy_version.id != version_id:
        policy_version = session.get(PolicyVersion, version_id)
    snapshot = _snapshot(
        session,
        employee_id=request.employee_id,
        policy_id=request.policy_id,
        lock=True,
    )
    target = enums.RequestStatus.APPROVED if approve else enums.RequestStatus.DENIED
    if approve and policy_version.kind != enums.PolicyKind.UNLIMITED:
        floor = (
            policy_version.negative_floor_minutes if policy_version.allow_negative else 0
        )
        if snapshot.balance_minutes - snapshot.pending_hold_minutes < floor:
            raise RequestError("The balance changed and can no longer cover this request.")
        ledger_service.post(
            session,
            company_id=request.company_id,
            employee_id=request.employee_id,
            policy_id=request.policy_id,
            policy_version_id=request.policy_version_id,
            entry_type=enums.EntryType.REQUEST_DEBIT,
            amount_minutes=-request.total_minutes,
            effective_date=request.start_date,
            source_type=enums.SourceType.REQUEST,
            source_id=request.id,
            note=request.reason,
        )
    if policy_version.kind != enums.PolicyKind.UNLIMITED:
        snapshot.pending_hold_minutes -= request.total_minutes
    request.status = target
    request.decided_by = actor_id
    request.decided_at = datetime.now(UTC)
    request.events.append(
        RequestEvent(
            from_status=enums.RequestStatus.PENDING,
            to_status=target,
            actor_id=actor_id,
            note=note,
        )
    )
    session.flush()
    return request


def cancel(
    session: Session, *, request: TimeOffRequest, actor_id: str, today: date
) -> TimeOffRequest:
    if request.status not in LIVE:
        raise RequestError("Only a pending or approved request can be cancelled.")
    if today >= request.start_date:
        raise RequestError("Leave that has started requires an admin correction.")
    previous = request.status
    snapshot = _snapshot(
        session,
        employee_id=request.employee_id,
        policy_id=request.policy_id,
        lock=True,
    )
    if previous == enums.RequestStatus.PENDING:
        snapshot.pending_hold_minutes -= request.total_minutes
    else:
        ledger_service.post(
            session,
            company_id=request.company_id,
            employee_id=request.employee_id,
            policy_id=request.policy_id,
            policy_version_id=request.policy_version_id,
            entry_type=enums.EntryType.REQUEST_REVERSAL,
            amount_minutes=request.total_minutes,
            effective_date=today,
            source_type=enums.SourceType.REQUEST_CANCELLATION,
            source_id=request.id,
            note="Cancelled before leave started",
        )
    request.status = enums.RequestStatus.CANCELLED
    request.events.append(
        RequestEvent(
            from_status=previous,
            to_status=enums.RequestStatus.CANCELLED,
            actor_id=actor_id,
        )
    )
    session.flush()
    return request
