"""Bounded text normalization shared by local detectors and safety rules."""

import unicodedata

MAX_TEXT_LENGTH = 20_000


def normalize_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("Agent input must be a string")
    if len(text) > MAX_TEXT_LENGTH:
        raise ValueError("Agent input exceeds the maximum length")
    normalized = unicodedata.normalize("NFKC", text)
    # Ignore invisible format characters when checking for obfuscated sensitive text.
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Cf")
    if len(normalized) > MAX_TEXT_LENGTH:
        raise ValueError("Normalized agent input exceeds the maximum length")
    return normalized
