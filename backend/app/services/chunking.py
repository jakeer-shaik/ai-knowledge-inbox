"""Recursive, structure-aware chunking.

Strategy: split on the largest natural boundary first (paragraphs), and only fall
back to smaller ones (lines -> sentences -> words) for pieces that are still too big.
Pieces are then packed into chunks of up to `chunk_size` characters, and each new
chunk starts with the tail of the previous one (up to `overlap` characters, whole
pieces only) so a fact spanning a boundary is retrievable from either side.

Why characters, not tokens: no tokenizer dependency, and ~800 chars (~200 tokens)
is small enough for precise retrieval yet large enough to keep a thought intact.
"""

import re

from app.services.text import normalize_whitespace

_SEPARATORS = (
    re.compile(r"\n\s*\n"),  # paragraphs
    re.compile(r"\n"),  # lines
    re.compile(r"(?<=[.!?])\s+"),  # sentences
    re.compile(r"\s+"),  # words
)


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    text = normalize_whitespace(text)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    return _pack(_split(text, chunk_size, level=0), chunk_size, overlap)


def _split(text: str, chunk_size: int, level: int) -> list[str]:
    """Break text into pieces no longer than chunk_size, preferring larger boundaries."""
    if len(text) <= chunk_size:
        return [text]
    if level >= len(_SEPARATORS):
        # A single "word" longer than a chunk (e.g. a giant URL): hard cut.
        return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]

    pieces: list[str] = []
    for part in _SEPARATORS[level].split(text):
        part = part.strip()
        if part:
            pieces.extend(_split(part, chunk_size, level + 1))
    return pieces


def _pack(pieces: list[str], chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []

    def length(parts: list[str]) -> int:
        return sum(len(p) for p in parts) + max(len(parts) - 1, 0)

    for piece in pieces:
        if current and length([*current, piece]) > chunk_size:
            chunks.append(" ".join(current))
            current = _overlap_tail(current, overlap)
            if length([*current, piece]) > chunk_size:
                current = []
        current.append(piece)

    if current:
        chunks.append(" ".join(current))
    return chunks


def _overlap_tail(parts: list[str], overlap: int) -> list[str]:
    tail: list[str] = []
    size = 0
    for part in reversed(parts):
        size += len(part) + (1 if tail else 0)
        if size > overlap:
            break
        tail.insert(0, part)
    return tail
