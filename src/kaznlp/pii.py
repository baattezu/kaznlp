"""Removal of personal data (PII) from monitored mentions.

Kazakhstan's personal data law requires that annotators and stored training data do
not expose personal information. This module replaces e-mails, URLs, phone numbers,
bank card numbers, IINs (12-digit individual identification numbers) and @usernames
with type placeholders such as ``<PHONE>``.

The same function is meant to be used by the ingestion pipeline and by the NLP
service, so a privacy fix only has to be made in one place.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

# Order matters: e-mails and URLs contain "@" and digits, so they are matched before
# usernames and numbers.
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("URL", re.compile(r"https?://\S+|www\.\S+")),
    ("CARD", re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")),
    ("PHONE", re.compile(r"(?:\+7|\b8)[ \-(]*\d{3}[ \-)]*\d{3}[ -]?\d{2}[ -]?\d{2}\b")),
    ("IIN", re.compile(r"\b\d{12}\b")),
    ("USER", re.compile(r"(?<![\w@])@\w{3,}")),
]


@dataclass(frozen=True)
class PiiMatch:
    """One piece of personal data found in a text.

    Attributes:
        kind: type of data: EMAIL, URL, CARD, PHONE, IIN or USER.
        start: index of the first character in the text.
        end: index after the last character (``text[start:end] == value``).
        value: the matched text itself.
    """

    kind: str
    start: int
    end: int
    value: str


def is_valid_iin(value: str) -> bool:
    """Check the control digit of a Kazakhstan IIN/BIN (12 digits).

    The 12th digit is a weighted sum of the first 11 digits modulo 11. If the result
    is 10, a second set of weights is used; if it is 10 again, the number is invalid.
    """
    if len(value) != 12 or not value.isdigit():
        return False
    digits = [int(c) for c in value]
    # first pass: weights 1..11 for the first 11 digits
    control = sum(d * w for d, w in zip(digits, range(1, 12), strict=False)) % 11
    if control == 10:
        weights = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
        control = sum(d * w for d, w in zip(digits, weights, strict=False)) % 11
        if control == 10:
            return False
    return control == digits[11]


def find_pii(text: str, *, check_iin: bool = True) -> list[PiiMatch]:
    """Return all non-overlapping PII matches, in text order.

    With ``check_iin=True`` a 12-digit number is treated as an IIN only if its control
    digit is valid, which avoids masking order numbers and similar IDs.
    """
    taken: list[tuple[int, int]] = []
    found: list[PiiMatch] = []
    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            if any(m.start() < end and start < m.end() for start, end in taken):
                continue
            if kind == "IIN" and check_iin and not is_valid_iin(m.group()):
                continue
            taken.append((m.start(), m.end()))
            found.append(PiiMatch(kind, m.start(), m.end(), m.group()))
    return sorted(found, key=lambda p: p.start)


def scrub(text: str, *, check_iin: bool = True) -> str:
    """Replace every PII match with a ``<KIND>`` placeholder."""
    out = []
    pos = 0
    for match in find_pii(text, check_iin=check_iin):
        out.append(text[pos : match.start])
        out.append(f"<{match.kind}>")
        pos = match.end
    out.append(text[pos:])
    return "".join(out)


def count_pii(texts: list[str], *, check_iin: bool = True) -> Counter[str]:
    """Count PII matches by type over a collection of texts (for data reports)."""
    counts: Counter[str] = Counter()
    for text in texts:
        counts.update(m.kind for m in find_pii(text, check_iin=check_iin))
    return counts
