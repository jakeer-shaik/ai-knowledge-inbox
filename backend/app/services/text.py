"""Text normalisation shared by the URL fetcher and the chunker."""

import re

_HORIZONTAL_SPACE = re.compile(r"[ \t\f\v]+")
_EXTRA_NEWLINES = re.compile(r"\n{3,}")


def normalize_whitespace(text: str) -> str:
    """Collapse runs of spaces, keep paragraph breaks (blank lines)."""
    lines = [_HORIZONTAL_SPACE.sub(" ", line).strip() for line in text.replace("\r\n", "\n").split("\n")]
    return _EXTRA_NEWLINES.sub("\n\n", "\n".join(lines)).strip()
