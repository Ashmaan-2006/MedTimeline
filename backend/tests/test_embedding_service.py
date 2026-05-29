import math

import pytest

from medgraph_api.services.embeddings import HashingEmbeddingService


def test_embed_text_returns_fixed_size_embedding_with_model_name() -> None:
    service = HashingEmbeddingService(dimensions=384)

    result = service.embed_text("Patient reports chest pain and dizziness.")

    assert result.text == "Patient reports chest pain and dizziness."
    assert result.embedding_model == "local-hashing-embedding-v1"
    assert len(result.embedding) == 384
    assert any(value != 0 for value in result.embedding)


def test_embed_text_is_deterministic_after_text_normalization() -> None:
    service = HashingEmbeddingService(dimensions=32)

    first = service.embed_text("Patient reports   chest pain.\nDizziness noted.")
    second = service.embed_text("Patient reports chest pain. Dizziness noted.")

    assert first.text == "Patient reports chest pain. Dizziness noted."
    assert first.embedding == second.embedding


def test_embed_text_normalizes_non_empty_vectors_to_unit_length() -> None:
    result = HashingEmbeddingService(dimensions=64).embed_text("troponin elevation chest pain")

    magnitude = math.sqrt(sum(value * value for value in result.embedding))

    assert magnitude == pytest.approx(1.0)


def test_embed_text_returns_zero_vector_for_blank_text() -> None:
    result = HashingEmbeddingService(dimensions=16).embed_text(" \n\n ")

    assert result.text == ""
    assert result.embedding == [0.0] * 16


def test_embed_texts_preserves_input_order() -> None:
    results = HashingEmbeddingService(dimensions=16).embed_texts(
        [
            "First clinical note.",
            "Second clinical note.",
        ]
    )

    assert [result.text for result in results] == [
        "First clinical note.",
        "Second clinical note.",
    ]
    assert results[0].embedding != results[1].embedding


def test_embedding_service_rejects_invalid_dimensions() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        HashingEmbeddingService(dimensions=0)
