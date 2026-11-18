"""Post-extraction cleanup for web pages.

trafilatura removes navigation and layout, but some article furniture survives and
hurts retrieval:
  - reference lists ("↑ Smith (2023)… Retrieved 2024-01-01") become chunks of pure citations
  - footnote markers like [12] look exactly like this app's own [n] citations
  - "[edit]" links, "¶" heading anchors and table rules are noise
"""

import re

from app.services.text import normalize_whitespace

_EDIT_LINK = re.compile(r"\[edit\]", re.IGNORECASE)
_FOOTNOTE = re.compile(r"\[(?:\d+|[a-z]|note \d+|citation needed|clarification needed|when\?|who\?|according to whom\?)\]", re.IGNORECASE)
_HEADING_ANCHOR = re.compile(r"[¶§]")
_BACK_MATTER_HEADING = re.compile(
    r"^(?:References|Notes|Notes and references|External links|Further reading|See also|Bibliography|Sources|Citations|Footnotes)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
# "- ↑ Smith (2023)…", "- ^ …", and multi-backlink entries like '- 1 2 3 4 "Vector database". …'
_REFERENCE_LINE = re.compile(r'^\s*(?:[-*]\s*)?(?:[↑^]|(?:\d+\s+)+["“])')
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}")

# Only cut at a back-matter heading past the first part of a page, so an early
# "See also" line can't truncate the article. Not 0.5: on short articles the
# reference list can be longer than the article itself.
BACK_MATTER_MIN_POSITION = 0.25


def clean_extracted_text(text: str) -> str:
    text = _EDIT_LINK.sub("", text)
    text = _FOOTNOTE.sub("", text)
    text = _HEADING_ANCHOR.sub("", text)

    for match in _BACK_MATTER_HEADING.finditer(text):
        late_in_page = match.start() >= len(text) * BACK_MATTER_MIN_POSITION
        if late_in_page or _mostly_references(text[match.end() :]):
            text = text[: match.start()]
            break

    lines = [line for line in text.split("\n") if not _REFERENCE_LINE.match(line) and not _TABLE_RULE.match(line)]
    return normalize_whitespace("\n".join(lines))


def _mostly_references(rest: str) -> bool:
    """True when what follows a heading is a citation list, wherever the heading sits."""
    lines = [line for line in rest.split("\n") if line.strip()]
    return len(lines) >= 3 and sum(bool(_REFERENCE_LINE.match(line)) for line in lines) >= 0.6 * len(lines)
