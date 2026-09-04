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
    if not rules:
        raise PolicyRuleError("An accrual policy needs at least one rule.")

    tiers = [int(rule.get("min_tenure_months", 0)) for rule in rules]
    if len(tiers) != len(set(tiers)) or 0 not in tiers:
        raise PolicyRuleError("Tenure tiers must be unique and include a zero-month tier.")
    baseline = rules[0]
    for rule in rules:
        if Decimal(str(rule["amount"])) <= 0:
            raise PolicyRuleError("The accrual amount must be greater than zero.")
        if rule["method"] != baseline["method"]:
            raise PolicyRuleError("All tenure tiers must use the same accrual method.")
        if rule["method"] == enums.AccrualMethod.TIME:
            if rule.get("frequency") is None or rule.get("accrues_at") is None:
                raise PolicyRuleError("A time-based rule needs a frequency and accrual point.")
            if (
                rule.get("frequency") != baseline.get("frequency")
                or rule.get("accrues_at") != baseline.get("accrues_at")
            ):
                raise PolicyRuleError("All tenure tiers must share one schedule and accrual point.")
        else:
            if not rule.get("per_minutes_worked"):
                raise PolicyRuleError("An hours-worked rule needs minutes worked per accrual.")
            if rule.get("frequency") is not None or rule.get("accrues_at") is not None:
                raise PolicyRuleError("An hours-worked rule cannot use a calendar frequency.")
