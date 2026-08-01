from __future__ import annotations

import re
import string

# Ordered so multi-word fillers are stripped before their sub-phrases/words.
_FILLER_PHRASES: tuple[str, ...] = (
    "could you please",
    "can you please",
    "would you please",
    "could you kindly",
    "please could you",
    "please can you",
    "i want you to",
    "i need you to",
    "would you mind",
    "could you",
    "can you",
    "would you",
    "will you",
    "do you mind",
    "i want to",
    "i need to",
    "i would like to",
    "i'd like to",
    "please",
    "thanks a lot",
    "thank you",
    "thanks",
    "kindly",
    "um",
    "uh",
    "uhh",
    "umm",
)

_PUNCTUATION_TABLE = str.maketrans("", "", string.punctuation)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_transcript(text: str) -> str:
    """Normalize a raw STT transcript before it is dispatched to plugins.

    Steps applied in order:
      1. lowercase
      2. remove punctuation
      3. strip filler / politeness phrases (wake words, "please", "could you", etc.)
      4. collapse and trim whitespace
    """
    if not text:
        return ""

    normalized = text.lower()
    normalized = normalized.translate(_PUNCTUATION_TABLE)
    normalized = _WHITESPACE_RE.sub(" ", normalized).strip()

    for phrase in _FILLER_PHRASES:
        pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)")
        normalized = pattern.sub(" ", normalized)
        normalized = _WHITESPACE_RE.sub(" ", normalized).strip()

    return normalized
