"""Regex-based PII redaction for inference log previews.

Keeps the system lightweight (no ML models) while catching the most
common PII patterns: emails, phone numbers, SSNs, credit cards, and
IP addresses. Each pattern is replaced with a placeholder tag.
"""

import re

from app.core.config import settings

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("[EMAIL]", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")),
    ("[PHONE]", re.compile(r"\b(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("[SSN]", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("[CREDIT_CARD]", re.compile(r"\b(?:\d[ -]*?){13,19}\b")),
    ("[IP_ADDR]", re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")),
]


def redact(text: str | None) -> str | None:
    """Replace PII patterns in *text* with placeholder tags.

    Returns the original text unchanged when PII redaction is disabled.
    """
    if text is None:
        return None
    if not settings.PII_REDACTION_ENABLED:
        return text

    for placeholder, pattern in _PATTERNS:
        text = pattern.sub(placeholder, text)
    return text
