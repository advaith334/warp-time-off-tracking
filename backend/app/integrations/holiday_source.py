"""Read statutory holidays at the integration boundary."""

from collections.abc import Iterable
from datetime import date

import holidays


def statutory(*, years: Iterable[int]) -> dict[date, str]:
    """Return US holidays, including library-provided observed weekdays."""
    return dict(holidays.country_holidays("US", years=list(years), observed=True))
