"""Policy writes preserve history by appending immutable versions."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import enums
from app.domain.rules import PolicyRuleError, validate_policy
from app.models import AccrualRule, Policy, PolicyVersion, TimeOffCategory


class PolicyError(ValueError):
    pass


def _validate(kind: enums.PolicyKind, rules: list[dict]) -> None:
    try:
        validate_policy(kind, rules)
    except PolicyRuleError as exc:
        raise PolicyError(str(exc)) from exc


def _validate_balance_settings(allow_negative: bool, floor: int) -> None:
    if allow_negative and floor >= 0:
        raise PolicyError("A negative-balance policy needs a floor below zero.")


def _validate_advanced_settings(
    max_balance_minutes: int | None,
    carryover_cap_minutes: int | None,
    expires_at_period_end: bool,
) -> None:
    if max_balance_minutes is not None and max_balance_minutes <= 0:
        raise PolicyError("The maximum balance must be greater than zero.")
    if carryover_cap_minutes is not None and carryover_cap_minutes < 0:
        raise PolicyError("The carryover cap cannot be negative.")
    if expires_at_period_end and carryover_cap_minutes is not None:
        raise PolicyError("Choose either full expiration or a carryover cap, not both.")


def _add_version(
    session: Session,
    *,
    policy_id: str,
    version_no: int,
    effective_from: date,
    kind: enums.PolicyKind,
    rules: list[dict],
    actor_id: str,
    change_reason: str,
    new_hire_proration: enums.NewHireProration = enums.NewHireProration.PRORATE,
    allow_negative: bool = False,
    negative_floor_minutes: int = 0,
    max_balance_minutes: int | None = None,
    carryover_cap_minutes: int | None = None,
    expires_at_period_end: bool = False,
    tenure_transition: enums.TenureTransition = enums.TenureTransition.NEXT_PERIOD,
) -> PolicyVersion:
    version = PolicyVersion(
        policy_id=policy_id,
        version_no=version_no,
        effective_from=effective_from,
        kind=kind,
        created_by=actor_id,
        change_reason=change_reason,
        new_hire_proration=new_hire_proration,
        allow_negative=allow_negative,
        negative_floor_minutes=negative_floor_minutes,
        max_balance_minutes=max_balance_minutes,
        carryover_cap_minutes=carryover_cap_minutes,
        expires_at_period_end=expires_at_period_end,
        tenure_transition=tenure_transition,
    )
    session.add(version)
    session.flush()
    session.add_all(
        AccrualRule(policy_version_id=version.id, **rule) for rule in rules
    )
    session.flush()
    session.refresh(version)
    return version


def create(
    session: Session,
    *,
    company_id: str,
    actor_id: str,
    name: str,
    category_id: str,
    effective_from: date,
    kind: enums.PolicyKind,
    rules: list[dict],
    change_reason: str,
    new_hire_proration: enums.NewHireProration = enums.NewHireProration.PRORATE,
    allow_negative: bool = False,
    negative_floor_minutes: int = 0,
    max_balance_minutes: int | None = None,
    carryover_cap_minutes: int | None = None,
    expires_at_period_end: bool = False,
    tenure_transition: enums.TenureTransition = enums.TenureTransition.NEXT_PERIOD,
) -> Policy:
    _validate(kind, rules)
    _validate_balance_settings(allow_negative, negative_floor_minutes)
    _validate_advanced_settings(
        max_balance_minutes, carryover_cap_minutes, expires_at_period_end
    )
    category = session.get(TimeOffCategory, category_id)
    if category is None or category.company_id != company_id:
        raise PolicyError("Unknown time-off category.")

    policy = Policy(
        company_id=company_id,
        category_id=category_id,
        name=name,
        created_by=actor_id,
    )
    session.add(policy)
    session.flush()
    _add_version(
        session,
        policy_id=policy.id,
        version_no=1,
        effective_from=effective_from,
        kind=kind,
        rules=rules,
        actor_id=actor_id,
        change_reason=change_reason,
        new_hire_proration=new_hire_proration,
        allow_negative=allow_negative,
        negative_floor_minutes=negative_floor_minutes,
        max_balance_minutes=max_balance_minutes,
        carryover_cap_minutes=carryover_cap_minutes,
        expires_at_period_end=expires_at_period_end,
        tenure_transition=tenure_transition,
    )
    session.refresh(policy)
    return policy


def update(
    session: Session,
    *,
    policy: Policy,
    actor_id: str,
    effective_from: date,
    kind: enums.PolicyKind,
    rules: list[dict],
    change_reason: str,
    name: str | None,
    new_hire_proration: enums.NewHireProration = enums.NewHireProration.PRORATE,
    allow_negative: bool = False,
    negative_floor_minutes: int = 0,
    max_balance_minutes: int | None = None,
    carryover_cap_minutes: int | None = None,
    expires_at_period_end: bool = False,
    tenure_transition: enums.TenureTransition = enums.TenureTransition.NEXT_PERIOD,
) -> PolicyVersion:
    _validate(kind, rules)
    _validate_balance_settings(allow_negative, negative_floor_minutes)
    _validate_advanced_settings(
        max_balance_minutes, carryover_cap_minutes, expires_at_period_end
    )
    current = latest_version(session, policy.id)
    if current is None:
        raise PolicyError("Policy has no version.")
    if effective_from <= current.effective_from:
        raise PolicyError(
            f"A new version must start after {current.effective_from.isoformat()}."
        )
    if name:
        policy.name = name
    return _add_version(
        session,
        policy_id=policy.id,
        version_no=current.version_no + 1,
        effective_from=effective_from,
        kind=kind,
        rules=rules,
        actor_id=actor_id,
        change_reason=change_reason,
        new_hire_proration=new_hire_proration,
        allow_negative=allow_negative,
        negative_floor_minutes=negative_floor_minutes,
        max_balance_minutes=max_balance_minutes,
        carryover_cap_minutes=carryover_cap_minutes,
        expires_at_period_end=expires_at_period_end,
        tenure_transition=tenure_transition,
    )


def latest_version(session: Session, policy_id: str) -> PolicyVersion | None:
    return session.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .order_by(PolicyVersion.version_no.desc())
        .limit(1)
    ).scalar_one_or_none()


def version_effective_on(
    session: Session, policy_id: str, on_date: date
) -> PolicyVersion | None:
    return session.execute(
        select(PolicyVersion)
        .where(
            PolicyVersion.policy_id == policy_id,
            PolicyVersion.effective_from <= on_date,
        )
        .order_by(PolicyVersion.effective_from.desc())
        .limit(1)
    ).scalar_one_or_none()
