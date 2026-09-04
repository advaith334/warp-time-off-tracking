"""Validation for the small policy rule language."""

from decimal import Decimal

from app import enums


class PolicyRuleError(ValueError):
    pass


def validate_policy(kind: enums.PolicyKind, rules: list[dict]) -> None:
    if kind == enums.PolicyKind.UNLIMITED:
        if rules:
            raise PolicyRuleError("An unlimited policy cannot have accrual rules.")
        return
    if len(rules) != 1:
        raise PolicyRuleError("An accrual policy needs exactly one rule.")

    rule = rules[0]
    if Decimal(str(rule["amount"])) <= 0:
        raise PolicyRuleError("The accrual amount must be greater than zero.")
    if rule["method"] == enums.AccrualMethod.TIME:
        if rule.get("frequency") is None or rule.get("accrues_at") is None:
            raise PolicyRuleError("A time-based rule needs a frequency and accrual point.")
    else:
        if not rule.get("per_minutes_worked"):
            raise PolicyRuleError("An hours-worked rule needs minutes worked per accrual.")
        if rule.get("frequency") is not None or rule.get("accrues_at") is not None:
            raise PolicyRuleError("An hours-worked rule cannot use a calendar frequency.")
