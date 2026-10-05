"""Primary phonetic code for blocking.

This is a Metaphone-style code: vowels drop after the first letter, and
close consonants fold together. RapidFuzz still does the real similarity.
"""

from __future__ import annotations

_VOWELS = set("aeiouy")


def metaphone(text: str) -> str:
    word = "".join(character for character in text.casefold() if "a" <= character <= "z")
    if not word:
        return ""
    if word.startswith(("kn", "gn", "pn", "wr", "ae")):
        word = word[1:]
    code: list[str] = []
    index = 0
    while index < len(word):
        character = word[index]
        nxt = word[index + 1] if index + 1 < len(word) else ""
        pair = character + nxt
        if character in _VOWELS:
            if index == 0:
                _push(code, character)
            index += 1
            continue
        if pair == "ph":
            _push(code, "f")
            index += 2
            continue
        if pair in {"sh", "ch"}:
            _push(code, "x")
            index += 2
            continue
        if pair == "th":
            _push(code, "0")
            index += 2
            continue
        if character == "c":
            _push(code, "s" if nxt in "eiy" else "k")
        elif character == "g":
            _push(code, "j" if nxt in "eiy" else "k")
        elif character == "q":
            _push(code, "k")
        elif character == "x":
            _push(code, "k")
            _push(code, "s")
        elif character in "zs":
            _push(code, "s")
        elif character == "d":
            _push(code, "t")
        elif character == "v":
            _push(code, "f")
        elif character == "w" and nxt not in _VOWELS:
            index += 1
            continue
        else:
            _push(code, character)
        index += 1
    return "".join(code)[:32]


def _push(code: list[str], character: str) -> None:
    if not code or code[-1] != character:
        code.append(character)
