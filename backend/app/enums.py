"""Business values stored as strings so adding a value stays transactional."""

from enum import StrEnum


class PolicyKind(StrEnum):
    UNLIMITED = "UNLIMITED"
    ACCRUAL = "ACCRUAL"


class AccrualMethod(StrEnum):
    TIME = "TIME"
    HOURS_WORKED = "HOURS_WORKED"


class Schedule(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    SEMIMONTHLY = "SEMIMONTHLY"
    BIWEEKLY = "BIWEEKLY"
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


class TenureTransition(StrEnum):
    NEXT_PERIOD = "NEXT_PERIOD"


class EntryType(StrEnum):
    ACCRUAL = "ACCRUAL"
    FORFEITURE = "FORFEITURE"
    CARRYOVER = "CARRYOVER"
    EXPIRATION = "EXPIRATION"
    REQUEST_DEBIT = "REQUEST_DEBIT"
    REQUEST_REVERSAL = "REQUEST_REVERSAL"


class SourceType(StrEnum):
    SCHEDULED_ACCRUAL = "SCHEDULED_ACCRUAL"
    PAYROLL_ACCRUAL = "PAYROLL_ACCRUAL"
    REQUEST = "REQUEST"
    REQUEST_CANCELLATION = "REQUEST_CANCELLATION"
    PERIOD_ROLLOVER = "PERIOD_ROLLOVER"


class JobKind(StrEnum):
    SCHEDULED = "SCHEDULED"
    PAYROLL = "PAYROLL"
    ROLLOVER = "ROLLOVER"


class RequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    CANCELLED = "CANCELLED"
