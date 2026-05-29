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


def test_chunk_text_splits_on_sentence_boundaries_with_overlap() -> None:
    text = (
        "Chest pain worsened over two weeks. "
        "Metoprolol was increased after clinic review. "
        "Patient later reported dizziness and fatigue."
    )

    chunks = TextChunkingService(max_chars=75, overlap_chars=20).chunk_text(text)

    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert chunks[0].content == "Chest pain worsened over two weeks."
    assert chunks[1].content == (
        "over two weeks. Metoprolol was increased after clinic review."
    )
    assert chunks[2].content == "after clinic review. Patient later reported dizziness and fatigue."
    assert chunks[1].metadata["char_start"] < chunks[0].metadata["char_end"]
    assert chunks[2].metadata["char_start"] < chunks[1].metadata["char_end"]


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
