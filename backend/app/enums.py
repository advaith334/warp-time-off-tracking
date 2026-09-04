"""Domain enumerations.

These are stored as VARCHAR + CHECK rather than native Postgres enums: adding a
value to a native enum requires a migration and cannot be done inside a
transaction that also uses it, which is a poor trade for a set of values that is
still moving.
"""
from enum import StrEnum


class PolicyKind(StrEnum):
    UNLIMITED = "UNLIMITED"
    ACCRUAL = "ACCRUAL"


class AccrualMethod(StrEnum):
    TIME = "TIME"
    HOURS_WORKED = "HOURS_WORKED"


class Schedule(StrEnum):
    """Accrual cadences.

    The set Odoo and Frappe converged on after a decade of customers; a
    narrower list forces companies to misrepresent their real policy.
    """

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


class DayLengthBasis(StrEnum):
    """Whose definition of "a day" a DAY-denominated rate refers to.

    EMPLOYEE  - "5 days/month" means 5 of *this employee's* days, so a 6h
                employee accrues 1800 minutes and spends 360 for a day off.
    COMPANY_STANDARD - a day is always 480 minutes for everyone.
    """

    EMPLOYEE = "EMPLOYEE"
    COMPANY_STANDARD = "COMPANY_STANDARD"


class PeriodAnchor(StrEnum):
    CALENDAR = "CALENDAR"
    ANNIVERSARY = "ANNIVERSARY"


class NewHireProration(StrEnum):
    PRORATE = "PRORATE"
    FULL = "FULL"
    NONE = "NONE"


class EntryType(StrEnum):
    ACCRUAL = "ACCRUAL"
    CAP_FORFEITURE = "CAP_FORFEITURE"
    REQUEST_DEBIT = "REQUEST_DEBIT"
    REQUEST_REVERSAL = "REQUEST_REVERSAL"
    MANUAL_ADJUSTMENT = "MANUAL_ADJUSTMENT"
    CARRYOVER = "CARRYOVER"
    EXPIRATION = "EXPIRATION"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"


class SourceType(StrEnum):
    """The originating mechanism for a ledger entry.

    (source_type, source_id) is UNIQUE, which is what makes every writer
    idempotent under replay.
    """

    SCHEDULED_ACCRUAL = "SCHEDULED_ACCRUAL"
    ACCRUAL_CAP = "ACCRUAL_CAP"
    PAYROLL_ACCRUAL = "PAYROLL_ACCRUAL"
    REQUEST = "REQUEST"
    REQUEST_CANCELLATION = "REQUEST_CANCELLATION"
    PERIOD_ROLLOVER = "PERIOD_ROLLOVER"
    ASSIGNMENT_TRANSFER = "ASSIGNMENT_TRANSFER"
    ADMIN = "ADMIN"


class RequestStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    CANCELLED = "CANCELLED"
    TAKEN = "TAKEN"


class AccrualRunKind(StrEnum):
    SCHEDULED = "SCHEDULED"
    PAYROLL = "PAYROLL"
    ROLLOVER = "ROLLOVER"


class MilestoneTransition(StrEnum):
    """When an employee crossing a tenure milestone starts earning the new rate.

    Odoo exposes both because both are defensible: IMMEDIATE is generous and
    simple, NEXT_PERIOD avoids splitting a period at a boundary. Making it a
    setting is the whole point - it is a policy question, not an engineering one.
    """

    IMMEDIATE = "IMMEDIATE"
    NEXT_PERIOD = "NEXT_PERIOD"


class PayTreatment(StrEnum):
    """How payroll should treat time taken under this policy.

    Absent this, a system cannot express parental leave at 60% salary, which is
    an ordinary request at any company large enough to have a policy for it.
    """

    PAID = "PAID"
    UNPAID = "UNPAID"
    PARTIALLY_PAID = "PARTIALLY_PAID"


class HolidayHandling(StrEnum):
    """Whether a company holiday inside a leave range is consumed.

    EXCLUDE is the common default for vacation. INCLUDE is common for long
    sick and parental leave, where the leave is continuous and the holiday is
    not a working day the employee gets back.
    """

    EXCLUDE = "EXCLUDE"
    INCLUDE = "INCLUDE"
