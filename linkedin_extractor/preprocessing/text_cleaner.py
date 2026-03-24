"""
preprocessing/text_cleaner.py — Clean OCR noise from extracted LinkedIn text.
"""

import re

import ftfy
from loguru import logger


# LinkedIn UI strings that should be stripped out
_UI_NOISE = {
    "connect", "follow", "message", "more", "see all",
    "show more", "like", "comment", "share", "send",
}

# Regex patterns for common LinkedIn chrome noise
_NOISE_PATTERNS = [
    re.compile(r"^\d+\s*(connections?|followers?)", re.IGNORECASE),
    re.compile(r"^(Premium|Open to|Hiring)", re.IGNORECASE),
]


def clean_ocr_text(raw_text: str) -> str:
    """
    Apply multi-step cleaning to raw OCR text from LinkedIn screenshots.

    Steps:
        1. Fix encoding artifacts with ftfy.
        2. Remove LinkedIn UI chrome noise.
        3. Remove noise-pattern lines.
        4. Collapse excessive newlines.
        5. Strip per-line whitespace.
        6. Remove very short lines (< 3 chars).

    Args:
        raw_text: Raw OCR output string.

    Returns:
        Cleaned text ready for LLM extraction.
    """
    logger.debug("Cleaning OCR text ({} chars raw)", len(raw_text))

    # 1. Fix encoding artefacts
    text = ftfy.fix_text(raw_text)

    # 2+3. Filter lines
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()

        # Skip UI noise
        if stripped.lower() in _UI_NOISE:
            continue

        # Skip noise-pattern matches
        if any(pattern.match(stripped) for pattern in _NOISE_PATTERNS):
            continue

        cleaned_lines.append(stripped)

    text = "\n".join(cleaned_lines)

    # 4. Collapse 3+ consecutive newlines → 2
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 5. Strip whitespace per line (already done above, but ensure)
    lines = [line.strip() for line in text.splitlines()]

    # 6. Remove lines shorter than 3 characters
    lines = [line for line in lines if len(line) >= 3]

    result = "\n".join(lines)
    logger.debug("Cleaned OCR text: {} chars", len(result))
    return result
