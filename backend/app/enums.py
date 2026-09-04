"""Business values stored as strings so adding a value stays transactional."""

from enum import StrEnum


class PolicyKind(StrEnum):
    UNLIMITED = "UNLIMITED"
    ACCRUAL = "ACCRUAL"


class AccrualMethod(StrEnum):
    TIME = "TIME"
    HOURS_WORKED = "HOURS_WORKED"


class Schedule(StrEnum):
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"


class AccruesAt(StrEnum):
    START_OF_PERIOD = "START_OF_PERIOD"
    END_OF_PERIOD = "END_OF_PERIOD"


class RateUnit(StrEnum):
    DAY = "DAY"
    HOUR = "HOUR"
    MINUTE = "MINUTE"


class NewHireProration(StrEnum):
    PRORATE = "PRORATE"
    FULL = "FULL"
    NONE = "NONE"


class EntryType(StrEnum):
    ACCRUAL = "ACCRUAL"


class SourceType(StrEnum):
    SCHEDULED_ACCRUAL = "SCHEDULED_ACCRUAL"
    PAYROLL_ACCRUAL = "PAYROLL_ACCRUAL"


class JobKind(StrEnum):
    SCHEDULED = "SCHEDULED"
    PAYROLL = "PAYROLL"
