"""Unicode normalization for Kazakh Cyrillic text scraped from Telegram, news and forums.

Scraped Kazakh text often contains letters that look identical on screen but are
different Unicode code points: a Latin "a" inside a Cyrillic word (keyboard layout
switching), the Bashkir "ҡ" instead of the Kazakh "қ", the Latin schwa "ə" instead of
the Cyrillic "ә", and so on. A tokenizer treats every such variant as a different word,
so the same word ends up split into several rare tokens. This module maps them back to
one canonical form before tokenization, deduplication or annotation.
"""

from __future__ import annotations

import re
import unicodedata

# Non-Kazakh code points that are visually identical to Kazakh letters.
KAZAKH_VARIANTS = str.maketrans(
    {
        "ə": "ә",  # U+0259 Latin schwa
        "Ə": "Ә",  # U+018F
        "ɵ": "ө",  # U+0275 Latin barred o
        "Ɵ": "Ө",  # U+019F
        "ҡ": "қ",  # U+04A1 Bashkir ka
        "Ҡ": "Қ",  # U+04A0
        "ӊ": "ң",  # U+04CA Khanty en
        "Ӊ": "Ң",  # U+04C9
        "ӯ": "ұ",  # U+04EF u with macron, sometimes used for "ұ"
        "Ӯ": "Ұ",  # U+04EE
    }
)

# Latin letters that have a Cyrillic twin. Applied only inside words that already
# contain Cyrillic letters, so purely Latin words ("Telegram", "iPhone") stay intact.
LATIN_TO_CYRILLIC = str.maketrans(
    {
        "a": "а",
        "e": "е",
        "o": "о",
        "p": "р",
        "c": "с",
        "x": "х",
        "y": "у",
        "k": "к",
        "i": "і",
        "h": "һ",
        "A": "А",
        "B": "В",
        "E": "Е",
        "H": "Н",
        "I": "І",
        "K": "К",
        "M": "М",
        "O": "О",
        "P": "Р",
        "C": "С",
        "T": "Т",
        "X": "Х",
        "Y": "У",
    }
)

_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_LATIN = re.compile(r"[A-Za-z]")
_WORD = re.compile(r"\w+")
_ZERO_WIDTH = re.compile("[​‌‍⁠﻿­]")
_WHITESPACE = re.compile(r"\s+")


def is_mixed_script(word: str) -> bool:
    """Return True if a word contains both Cyrillic and Latin letters."""
    return bool(_CYRILLIC.search(word) and _LATIN.search(word))


def fix_mixed_script(text: str) -> str:
    """Replace Latin look-alike letters inside Cyrillic words with their Cyrillic twins."""

    def _fix(match: re.Match[str]) -> str:
        """Fix one word if it mixes alphabets, otherwise return it unchanged."""
        word = match.group(0)
        return word.translate(LATIN_TO_CYRILLIC) if is_mixed_script(word) else word

    return _WORD.sub(_fix, text)


def normalize(text: str, *, lowercase: bool = False) -> str:
    """Return a canonical form of a Kazakh (or mixed Kazakh-Russian) text.

    Steps, in order: remove zero-width characters, Unicode NFC composition
    (e.g. "и" + combining breve -> "й"), map non-Kazakh look-alike letters to Kazakh
    ones, fix Latin letters inside Cyrillic words, collapse whitespace.
    """
    text = _ZERO_WIDTH.sub("", text)
    text = unicodedata.normalize("NFC", text)
    text = text.translate(KAZAKH_VARIANTS)
    text = fix_mixed_script(text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text.lower() if lowercase else text
