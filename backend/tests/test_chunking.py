import pytest

from app.services.chunking import chunk_text


def test_empty_text_has_no_chunks():
    assert chunk_text("   \n\n ") == []


def test_short_text_is_one_chunk():
    assert chunk_text("A short note.", chunk_size=800) == ["A short note."]


def test_chunks_respect_size_limit():
    text = " ".join(f"Sentence number {i} talks about topic {i}." for i in range(200))
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)


def test_consecutive_chunks_overlap():
    text = " ".join(f"Fact {i} is here." for i in range(100))
    chunks = chunk_text(text, chunk_size=200, overlap=60)
    assert len(chunks) > 1
    for previous, current in zip(chunks, chunks[1:]):
        first_sentence = current.split(". ")[0] + "."
        assert previous.endswith(first_sentence) or first_sentence in previous


def test_prefers_paragraph_boundaries():
    para_a = "Alpha " * 40
    para_b = "Bravo " * 40
    chunks = chunk_text(f"{para_a.strip()}\n\n{para_b.strip()}", chunk_size=300, overlap=0)
    assert chunks == [para_a.strip(), para_b.strip()]


def test_oversized_word_is_hard_split():
    chunks = chunk_text("x" * 1000, chunk_size=300, overlap=0)
    assert all(len(c) <= 300 for c in chunks)
    assert "".join(chunks) == "x" * 1000


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=100, overlap=100)
