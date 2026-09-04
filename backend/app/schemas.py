"""Validated API input shapes."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field

from app import enums


class AccrualRuleIn(BaseModel):
    method: enums.AccrualMethod
    amount: Decimal = Field(gt=0)
    unit: enums.RateUnit
    frequency: enums.Schedule | None = None
    accrues_at: enums.AccruesAt | None = None
    per_minutes_worked: int | None = Field(default=None, gt=0)


class PolicyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    category_id: str
    effective_from: date
    kind: enums.PolicyKind
    rules: list[AccrualRuleIn] = Field(default_factory=list)
    change_reason: str = "Policy created"
    new_hire_proration: enums.NewHireProration = enums.NewHireProration.PRORATE


class PolicyUpdateIn(BaseModel):
    name: str | None = None
    effective_from: date
    kind: enums.PolicyKind
    rules: list[AccrualRuleIn] = Field(default_factory=list)
    change_reason: str = Field(min_length=1)
    new_hire_proration: enums.NewHireProration = enums.NewHireProration.PRORATE


class PayrollAccrualIn(BaseModel):
    payroll_run_id: str = Field(min_length=1)
    period_end: date
    minutes_by_employee: dict[str, int]


class CategoryCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    icon: str | None = None


class AssignIn(BaseModel):
    employee_ids: list[str] = Field(min_length=1)
    effective_from: date


class EndAssignmentIn(BaseModel):
    effective_to: date
