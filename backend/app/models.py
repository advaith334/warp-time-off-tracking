"""Database models introduced beside the behavior that uses them."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    literal_column,
)
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app import enums


def _uuid() -> str:
    return str(uuid.uuid4())


def _enum(enum_type, name: str):
    return Enum(
        enum_type,
        name=name,
        native_enum=False,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TimeOffCategory(Base, TimestampMixin):
    __tablename__ = "time_off_categories"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(16))

    policies: Mapped[list[Policy]] = relationship(back_populates="category")
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_category_name_per_company"),
    )


class EmployeeGroup(Base, TimestampMixin):
    __tablename__ = "employee_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    members: Mapped[list[EmployeeGroupMember]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    policy_targets: Mapped[list[PolicyGroupTarget]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_employee_group_name_per_company"),
    )


class EmployeeGroupMember(Base, TimestampMixin):
    __tablename__ = "employee_group_members"

    group_id: Mapped[str] = mapped_column(
        ForeignKey("employee_groups.id", ondelete="CASCADE"), primary_key=True
    )
    employee_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)

    group: Mapped[EmployeeGroup] = relationship(back_populates="members")
    __table_args__ = (
        UniqueConstraint(
            "company_id", "employee_id", name="uq_employee_single_group_per_company"
        ),
    )


class Policy(Base, TimestampMixin):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category_id: Mapped[str] = mapped_column(ForeignKey("time_off_categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    all_employees: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    category: Mapped[TimeOffCategory] = relationship(back_populates="policies")
    versions: Mapped[list[PolicyVersion]] = relationship(
        back_populates="policy",
        order_by="PolicyVersion.version_no",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list[PolicyAssignment]] = relationship(back_populates="policy")
    group_targets: Mapped[list[PolicyGroupTarget]] = relationship(
        back_populates="policy", cascade="all, delete-orphan"
    )
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_policy_name_per_company"),
    )


class PolicyGroupTarget(Base, TimestampMixin):
    __tablename__ = "policy_group_targets"

    policy_id: Mapped[str] = mapped_column(
        ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(
        ForeignKey("employee_groups.id", ondelete="CASCADE"), primary_key=True
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)

    policy: Mapped[Policy] = relationship(back_populates="group_targets")
    group: Mapped[EmployeeGroup] = relationship(back_populates="policy_targets")


class PolicyVersion(Base, TimestampMixin):
    __tablename__ = "policy_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    kind: Mapped[enums.PolicyKind] = mapped_column(
        _enum(enums.PolicyKind, "policy_kind"), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    change_reason: Mapped[str] = mapped_column(Text, nullable=False)
    new_hire_proration: Mapped[enums.NewHireProration] = mapped_column(
        _enum(enums.NewHireProration, "new_hire_proration"),
        nullable=False,
        default=enums.NewHireProration.PRORATE,
    )
    allow_negative: Mapped[bool] = mapped_column(nullable=False, default=False)
    negative_floor_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_balance_minutes: Mapped[int | None] = mapped_column(Integer)
    carryover_cap_minutes: Mapped[int | None] = mapped_column(Integer)
    expires_at_period_end: Mapped[bool] = mapped_column(nullable=False, default=False)
    tenure_transition: Mapped[enums.TenureTransition] = mapped_column(
        _enum(enums.TenureTransition, "tenure_transition"),
        nullable=False,
        default=enums.TenureTransition.NEXT_PERIOD,
    )

    policy: Mapped[Policy] = relationship(back_populates="versions")
    rules: Mapped[list[AccrualRule]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )
    __table_args__ = (
        UniqueConstraint("policy_id", "version_no", name="uq_policy_version_number"),
        UniqueConstraint("policy_id", "effective_from", name="uq_policy_version_effective_date"),
    )


class AccrualRule(Base):
    __tablename__ = "accrual_rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    policy_version_id: Mapped[str] = mapped_column(
        ForeignKey("policy_versions.id"), nullable=False, index=True
    )
    method: Mapped[enums.AccrualMethod] = mapped_column(
        _enum(enums.AccrualMethod, "accrual_method"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    unit: Mapped[enums.RateUnit] = mapped_column(
        _enum(enums.RateUnit, "rate_unit"), nullable=False
    )
    frequency: Mapped[enums.Schedule | None] = mapped_column(
        _enum(enums.Schedule, "accrual_schedule")
    )
    accrues_at: Mapped[enums.AccruesAt | None] = mapped_column(
        _enum(enums.AccruesAt, "accrues_at")
    )
    per_minutes_worked: Mapped[int | None] = mapped_column(Integer)
    min_tenure_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    version: Mapped[PolicyVersion] = relationship(back_populates="rules")


class PolicyAssignment(Base, TimestampMixin):
    __tablename__ = "policy_assignments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"), nullable=False)
    category_id: Mapped[str] = mapped_column(ForeignKey("time_off_categories.id"), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)

    policy: Mapped[Policy] = relationship(back_populates="assignments")
    __table_args__ = (
        ExcludeConstraint(
            ("employee_id", "="),
            ("category_id", "="),
            (
                func.daterange(
                    effective_from,
                    func.coalesce(effective_to, literal_column("'infinity'::date")),
                    "[]",
                ),
                "&&",
            ),
            name="ex_no_overlapping_assignment_per_category",
            using="gist",
        ),
    )


class LedgerEntry(Base, TimestampMixin):
    __tablename__ = "ledger_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"), nullable=False)
    policy_version_id: Mapped[str] = mapped_column(
        ForeignKey("policy_versions.id"), nullable=False
    )
    entry_type: Mapped[enums.EntryType] = mapped_column(
        _enum(enums.EntryType, "entry_type"), nullable=False
    )
    amount_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_type: Mapped[enums.SourceType] = mapped_column(
        _enum(enums.SourceType, "source_type"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_ledger_source"),
    )


class BalanceSnapshot(Base):
    __tablename__ = "balance_snapshots"

    employee_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    policy_id: Mapped[str] = mapped_column(
        ForeignKey("policies.id"), primary_key=True
    )
    balance_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_hold_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class JobRun(Base, TimestampMixin):
    __tablename__ = "job_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[enums.JobKind] = mapped_column(
        _enum(enums.JobKind, "job_kind"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    entries_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class DemoState(Base):
    __tablename__ = "demo_state"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    current_date: Mapped[date] = mapped_column(Date, nullable=False)


class Holiday(Base, TimestampMixin):
    __tablename__ = "holidays"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    observed: Mapped[bool] = mapped_column(nullable=False, default=False)
    __table_args__ = (
        UniqueConstraint("company_id", "date", name="uq_holiday_company_date"),
    )


class TimeOffRequest(Base, TimestampMixin):
    __tablename__ = "time_off_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    employee_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"), nullable=False)
    policy_version_id: Mapped[str] = mapped_column(ForeignKey("policy_versions.id"), nullable=False)
    category_id: Mapped[str] = mapped_column(ForeignKey("time_off_categories.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[enums.RequestStatus] = mapped_column(
        _enum(enums.RequestStatus, "request_status"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    is_partial_day: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_by: Mapped[str | None] = mapped_column(String(64))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    days: Mapped[list[RequestDay]] = relationship(
        back_populates="request", order_by="RequestDay.date", cascade="all, delete-orphan"
    )
    events: Mapped[list[RequestEvent]] = relationship(
        back_populates="request", order_by="RequestEvent.at", cascade="all, delete-orphan"
    )


class RequestDay(Base):
    __tablename__ = "request_days"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    request_id: Mapped[str] = mapped_column(ForeignKey("time_off_requests.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    request: Mapped[TimeOffRequest] = relationship(back_populates="days")
    __table_args__ = (
        UniqueConstraint("request_id", "date", name="uq_request_day"),
    )


class RequestEvent(Base):
    __tablename__ = "request_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    request_id: Mapped[str] = mapped_column(ForeignKey("time_off_requests.id"), nullable=False)
    from_status: Mapped[enums.RequestStatus | None] = mapped_column(
        _enum(enums.RequestStatus, "request_event_from_status")
    )
    to_status: Mapped[enums.RequestStatus] = mapped_column(
        _enum(enums.RequestStatus, "request_event_to_status"), nullable=False
    )
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    request: Mapped[TimeOffRequest] = relationship(back_populates="events")
