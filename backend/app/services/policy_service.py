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
) -> PolicyVersion:
    version = PolicyVersion(
        policy_id=policy_id,
        version_no=version_no,
        effective_from=effective_from,
        kind=kind,
        created_by=actor_id,
        change_reason=change_reason,
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
) -> Policy:
    _validate(kind, rules)
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
) -> PolicyVersion:
    _validate(kind, rules)
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
