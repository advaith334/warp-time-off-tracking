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


class PolicyVersionOut(Out):
    id: str
    version_no: int
    effective_from: date
    kind: enums.PolicyKind
    created_by: str
    change_reason: str
    new_hire_proration: enums.NewHireProration
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


class BalanceOut(Out):
    category_id: str
    category_name: str
    has_policy: bool
    policy_id: str | None
    policy_name: str | None
    is_unlimited: bool
    balance_minutes: int
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
