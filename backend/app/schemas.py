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


class PolicyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    category_id: str
    effective_from: date
    kind: enums.PolicyKind
    rules: list[AccrualRuleIn] = Field(default_factory=list)
    change_reason: str = "Policy created"


class PolicyUpdateIn(BaseModel):
    name: str | None = None
    effective_from: date
    kind: enums.PolicyKind
    rules: list[AccrualRuleIn] = Field(default_factory=list)
    change_reason: str = Field(min_length=1)


class CategoryCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    icon: str | None = None


class AssignIn(BaseModel):
    employee_ids: list[str] = Field(min_length=1)
    effective_from: date


class EndAssignmentIn(BaseModel):
    effective_to: date
