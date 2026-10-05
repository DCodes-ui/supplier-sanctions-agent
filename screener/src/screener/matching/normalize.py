"""Turn a raw name into the form used for blocking and scoring.

Order: casefold, Cyrillic to Latin, diacritics, punctuation, legal suffixes.
The stored evidence keeps the original spelling.
"""

from __future__ import annotations

import unicodedata

# Shared letters follow Russian passport style. Ukrainian-only letters are separate.
# г is the same character in both alphabets, so it maps to g.
_CYRILLIC = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    "ґ": "g",
    "є": "ye",
    "і": "i",
    "ї": "yi",
}

# Letters that do not decompose into a base letter plus a mark.
_EXTRA = {
    "ł": "l",
    "ø": "o",
    "đ": "d",
    "ð": "d",
    "þ": "th",
    "æ": "ae",
    "œ": "oe",
    "ß": "ss",
    "ı": "i",
}

# Longest suffixes first. A suffix is removed only when the name still has tokens left.
_LEGAL_SUFFIXES = (
    ("sp", "z", "oo"),
    ("sp", "z", "o", "o"),
    ("gmbh",),
    ("llc",),
    ("ltd",),
    ("inc",),
    ("uab",),
    ("sia",),
    ("oy",),
    ("ou",),
    ("as",),
    ("ab",),
)


def normalize_name(value: str) -> str:
    text = _transliterate(value.casefold())
    text = _strip_diacritics(text)
    text = _strip_punctuation(text)
    tokens = _strip_legal_forms(text.split())
    return " ".join(tokens)


def name_tokens(normalized: str) -> list[str]:
    """Tokens used for blocking. Single letters match too many unrelated names."""

    return [token for token in normalized.split() if len(token) >= 2]


def normalize_identifier(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _transliterate(text: str) -> str:
    return "".join(_CYRILLIC.get(character, character) for character in text)


def _strip_diacritics(text: str) -> str:
    replaced = "".join(_EXTRA.get(character, character) for character in text)
    decomposed = unicodedata.normalize("NFKD", replaced)
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def _strip_punctuation(text: str) -> str:
    kept: list[str] = []
    for character in text:
        if character.isalnum():
            kept.append(character)
        elif character.isspace() or character in "-'’":
            kept.append(" ")
    return " ".join("".join(kept).split())


def _strip_legal_forms(tokens: list[str]) -> list[str]:
    changed = True
    while changed and tokens:
        changed = False
        for suffix in _LEGAL_SUFFIXES:
            size = len(suffix)
            if len(tokens) > size and tuple(tokens[-size:]) == suffix:
                tokens = tokens[:-size]
                changed = True
                break
    return tokens
