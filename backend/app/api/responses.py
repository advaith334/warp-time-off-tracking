"""Typed response shapes shared by FastAPI and the generated contract."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, PlainSerializer

from app import enums

Money = Annotated[Decimal, PlainSerializer(str, return_type=str, when_used="json")]


class Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EmployeeOut(Out):
    id: str
    name: str
    email: str
    employment_type: str
    start_date: date
    work_minutes_per_day: int
    work_state: str
    is_admin: bool


class CategoryOut(Out):
    id: str
    name: str
    icon: str | None


class AccrualRuleOut(Out):
    id: str
    method: enums.AccrualMethod
    amount: Money
    unit: enums.RateUnit
    frequency: enums.Schedule | None
    accrues_at: enums.AccruesAt | None
    per_minutes_worked: int | None
    min_tenure_months: int


class PolicyVersionOut(Out):
    id: str
    version_no: int
    effective_from: date
    kind: enums.PolicyKind
    created_by: str
    change_reason: str
    new_hire_proration: enums.NewHireProration
    allow_negative: bool
    negative_floor_minutes: int
    max_balance_minutes: int | None
    carryover_cap_minutes: int | None
    expires_at_period_end: bool
    tenure_transition: enums.TenureTransition
    created_at: datetime
    rules: list[AccrualRuleOut]


class PolicyOut(Out):
    id: str
    name: str
    category_id: str
    category_name: str
    created_by: str
    current_version: PolicyVersionOut
    version_count: int
    all_employees: bool
    group_ids: list[str]
    group_names: list[str]

    @classmethod
    def of(cls, policy, current):
        return cls.model_validate(
            {
                "id": policy.id,
                "name": policy.name,
                "category_id": policy.category_id,
                "category_name": policy.category.name,
                "created_by": policy.created_by,
                "current_version": current,
                "version_count": len(policy.versions),
                "all_employees": policy.all_employees,
                "group_ids": [target.group_id for target in policy.group_targets],
                "group_names": [target.group.name for target in policy.group_targets],
            }
        )


class AssignmentOut(Out):
    id: str
    employee_id: str
    employee_name: str
    policy_id: str
    policy_name: str
    category_id: str
    effective_from: date
    effective_to: date | None
    created_by: str


class GroupMemberOut(Out):
    employee_id: str
    employee_name: str
    employment_type: str


class EmployeeGroupOut(Out):
    id: str
    name: str
    members: list[GroupMemberOut]


class BalanceOut(Out):
    category_id: str
    category_name: str
    has_policy: bool
    policy_id: str | None
    policy_name: str | None
    is_unlimited: bool
    balance_minutes: int
    pending_hold_minutes: int
    available_minutes: int
    day_minutes: int


class LedgerEntryOut(Out):
    id: str
    entry_type: enums.EntryType
    amount_minutes: int
    effective_date: date
    source_type: enums.SourceType
    source_id: str
    note: str | None
    created_at: datetime


class JobRunOut(Out):
    id: str
    kind: enums.JobKind
    source_id: str
    status: str
    entries_created: int
    error: str | None
    created_at: datetime


class HolidayOut(Out):
    id: str
    date: date
    name: str
    observed: bool


class RequestDayOut(Out):
    date: date
    minutes: int


class RequestEventOut(Out):
    from_status: enums.RequestStatus | None
    to_status: enums.RequestStatus
    actor_id: str
    note: str | None
    at: datetime


class RequestPreviewOut(Out):
    total_minutes: int
    available_minutes: int
    days: list[RequestDayOut]


class TimeOffRequestOut(Out):
    id: str
    employee_id: str
    employee_name: str
    category_id: str
    policy_id: str
    reason: str
    status: enums.RequestStatus
    start_date: date
    end_date: date
    total_minutes: int
    is_partial_day: bool
    created_at: datetime
    decided_by: str | None
    decided_at: datetime | None
    days: list[RequestDayOut]
    events: list[RequestEventOut]

    @classmethod
    def of(cls, request, employee_name: str):
        return cls.model_validate(
            {
                **{
                    column.name: getattr(request, column.name)
                    for column in request.__table__.columns
                },
                "employee_name": employee_name,
                "days": request.days,
                "events": request.events,
            }
        )
