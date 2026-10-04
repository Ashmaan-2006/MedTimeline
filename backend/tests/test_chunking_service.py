import pytest

from medgraph_api.services.chunking import TextChunkingService


def test_chunk_text_returns_empty_list_for_blank_text() -> None:
    chunks = TextChunkingService().chunk_text(" \n\n ")

    assert chunks == []


def test_chunk_text_normalizes_extracted_document_text() -> None:
    text = """
    Patient reports intermittent chest pain.

    Troponin was negative.
    Follow up ECG was ordered.
    """

    chunks = TextChunkingService(max_chars=300).chunk_text(text)

    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].content == (
        "Patient reports intermittent chest pain.\n"
        "Troponin was negative.\n"
        "Follow up ECG was ordered."
    )
    assert chunks[0].token_count == 13
    assert chunks[0].metadata == {"char_start": 0, "char_end": len(chunks[0].content)}


def test_chunk_text_starts_chunks_on_sentence_boundaries() -> None:
    text = (
        "Chest pain worsened over two weeks. "
        "Metoprolol was increased after clinic review. "
        "Patient later reported dizziness and fatigue."
    )

    chunks = TextChunkingService(max_chars=75, overlap_chars=20).chunk_text(text)

    # Chunks that end on a sentence boundary do not repeat a partial sentence.
    assert [chunk.content for chunk in chunks] == [
        "Chest pain worsened over two weeks.",
        "Metoprolol was increased after clinic review.",
        "Patient later reported dizziness and fatigue.",
    ]


def test_chunk_text_overlaps_from_sentence_start_when_split_mid_sentence() -> None:
    text = "Troponin was negative. Chest pain worsened over two weeks while on metoprolol."

    chunks = TextChunkingService(max_chars=50, overlap_chars=40).chunk_text(text)

    assert chunks[0].content.startswith("Troponin was negative. Chest pain worsened")
    assert not chunks[0].content.endswith(".")
    assert chunks[1].content.startswith("Chest pain worsened")


def test_chunk_text_records_section_heading_path() -> None:
    text = "DISCHARGE PLAN\nNew Medications:\n" + "\n".join(
        f"- Medication {index} 10 mg daily for the next several weeks" for index in range(20)
    )

    chunks = TextChunkingService(max_chars=200, overlap_chars=50).chunk_text(text)

    assert "section" not in chunks[0].metadata
    assert chunks[1].metadata["section"] == "DISCHARGE PLAN > New Medications"


def test_chunk_text_falls_back_to_word_boundaries() -> None:
    text = "alpha beta gamma delta epsilon zeta eta theta"

    chunks = TextChunkingService(max_chars=18, overlap_chars=5).chunk_text(text)

    assert [chunk.content for chunk in chunks] == [
        "alpha beta gamma",
        "gamma delta",
        "delta epsilon",
        "zeta eta theta",
    ]


def test_chunking_service_rejects_invalid_configuration() -> None:
    with pytest.raises(ValueError, match="max_chars"):
        TextChunkingService(max_chars=0)

    with pytest.raises(ValueError, match="overlap_chars"):
        TextChunkingService(overlap_chars=-1)

    with pytest.raises(ValueError, match="smaller"):
        TextChunkingService(max_chars=100, overlap_chars=100)


def test_chunk_text_terminates_when_break_falls_inside_overlap_window() -> None:
    text = "A" * 990 + " short line\n" + ("word " * 400)

    chunks = TextChunkingService(max_chars=1200, overlap_chars=150).chunk_text(text)

    starts = [chunk.metadata["char_start"] for chunk in chunks]
    assert starts == sorted(set(starts))
    assert chunks[-1].metadata["char_end"] == len(chunks[-1].content) + starts[-1]


@pytest.mark.parametrize("seed", range(25))
def test_chunk_text_always_advances_and_covers_text(seed: int) -> None:
    import random

    rng = random.Random(seed)
    pieces = []
    for _ in range(rng.randint(50, 400)):
        word = "x" * rng.randint(1, 60)
        pieces.append(word + rng.choice([" ", " ", "\n", ". ", "! "]))
    text = "".join(pieces)
    service = TextChunkingService(max_chars=200, overlap_chars=50)

    chunks = service.chunk_text(text)
    normalized = service._normalize_text(text)

    starts = [chunk.metadata["char_start"] for chunk in chunks]
    assert starts == sorted(set(starts))
    assert chunks[0].metadata["char_start"] == 0
    assert chunks[-1].metadata["char_end"] == len(normalized)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert current.metadata["char_start"] <= previous.metadata["char_end"]
