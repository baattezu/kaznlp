"""Time-based train/validation/test split.

A random split lets near-duplicate reposts of the same story fall on both sides of
the boundary and makes test scores look better than they are. Splitting by date
also matches how the model is used: it is trained on the past and applied to new
mentions.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

Record = dict[str, Any]


def temporal_split(
    records: Sequence[Record],
    date_field: str = "date",
    ratios: tuple[float, float, float] = (0.70, 0.15, 0.15),
) -> dict[str, list[Record]]:
    """Sort records by date and cut them into train/val/test by the given ratios.

    Records with the same timestamp are never separated: a cut point is moved forward
    until the date changes, so no test record is older than a training record.
    """
    if len(ratios) != 3 or any(r < 0 for r in ratios) or abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError("ratios must be three non-negative numbers that sum to 1")

    ordered = sorted(records, key=lambda r: datetime.fromisoformat(str(r[date_field])))
    n = len(ordered)

    def cut(position: int) -> int:
        while (
            0 < position < n and ordered[position][date_field] == ordered[position - 1][date_field]
        ):
            position += 1
        return position

    first = cut(round(n * ratios[0]))
    second = max(first, cut(round(n * (ratios[0] + ratios[1]))))
    return {
        "train": list(ordered[:first]),
        "val": list(ordered[first:second]),
        "test": list(ordered[second:]),
    }
