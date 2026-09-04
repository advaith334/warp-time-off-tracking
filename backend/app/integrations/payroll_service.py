"""Shape of the `on_payroll_processed` event the brief tells us to subscribe to.

The Payroll Service aggregates hours worked over a period; we consume the event
to drive hours-worked accrual (R3). `payroll_run_id` is the idempotency key -
a redelivered or replayed event must not double-credit anyone.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PayrollEntry:
    employee_id: str
    minutes_worked: int


@dataclass(frozen=True)
class PayrollEvent:
    payroll_run_id: str
    company_id: str
    period_start: date
    period_end: date
    entries: tuple[PayrollEntry, ...]
