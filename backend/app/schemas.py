"""Validated API input shapes."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app import enums


class AccrualRuleIn(BaseModel):
    method: enums.AccrualMethod
    amount: Decimal = Field(gt=0)
    unit: enums.RateUnit
    frequency: enums.Schedule | None = None
    accrues_at: enums.AccruesAt | None = None
    per_minutes_worked: int | None = Field(default=None, gt=0)
    min_tenure_months: int = Field(default=0, ge=0)


class AdvancedPolicyFields(BaseModel):
    max_balance_minutes: int | None = Field(default=None, gt=0)
    carryover_cap_minutes: int | None = Field(default=None, ge=0)
    expires_at_period_end: bool = False
    tenure_transition: enums.TenureTransition = enums.TenureTransition.NEXT_PERIOD


class PolicyCreateIn(AdvancedPolicyFields):
    name: str = Field(min_length=1, max_length=128)
    category_id: str
    effective_from: date
    kind: enums.PolicyKind
    rules: list[AccrualRuleIn] = Field(default_factory=list)
    change_reason: str = "Policy created"
    new_hire_proration: enums.NewHireProration = enums.NewHireProration.PRORATE
    allow_negative: bool = False
    negative_floor_minutes: int = Field(default=0, le=0)


class PolicyUpdateIn(AdvancedPolicyFields):
    name: str | None = None
    effective_from: date
    kind: enums.PolicyKind
    rules: list[AccrualRuleIn] = Field(default_factory=list)
    change_reason: str = Field(min_length=1)
    new_hire_proration: enums.NewHireProration = enums.NewHireProration.PRORATE
    allow_negative: bool = False
    negative_floor_minutes: int = Field(default=0, le=0)


class PayrollAccrualIn(BaseModel):
    payroll_run_id: str = Field(min_length=1)
    period_end: date
    minutes_by_employee: dict[str, int]


class RequestIn(BaseModel):
    employee_id: str
    category_id: str
    reason: str = Field(min_length=1)
    start_date: date
    end_date: date
    hours: int | None = Field(default=None, ge=0, le=23)
    minutes: int | None = Field(default=None, ge=0, le=59)

    @model_validator(mode="after")
    def valid_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self

    @property
    def partial_minutes(self) -> int | None:
        if self.hours is None and self.minutes is None:
            return None
        return (self.hours or 0) * 60 + (self.minutes or 0)


class DecisionIn(BaseModel):
    note: str | None = None


class CategoryCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    icon: str | None = None


class AssignIn(BaseModel):
    employee_ids: list[str] = Field(min_length=1)
    effective_from: date


class EndAssignmentIn(BaseModel):
    effective_to: date


class HolidayIn(BaseModel):
    date: date
    name: str = Field(min_length=1, max_length=128)
    observed: bool = False


class ClockIn(BaseModel):
    current_date: date
