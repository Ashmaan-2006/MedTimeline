from uuid import uuid4

import pytest

from medgraph_api.services.entity_extraction_service import (
    ClinicalEntityExtractionService,
    EntityExtractionError,
)


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_extract_entities_from_chunk_with_validated_strict_json_response() -> None:
    chunk_id = uuid4()
    llm_client = FakeLLMClient(
        f"""
        {{
          "entities": [
            {{
              "entity_type": "symptom",
              "name": "Chest pain",
              "normalized_name": "chest pain",
              "source_chunk_id": "{chunk_id}",
              "confidence": 0.92,
              "evidence_quote": "Patient reports chest pain",
              "date": "2026-01-05"
            }},
            {{
              "entity_type": "medication",
              "name": "Metoprolol",
              "normalized_name": "METOPROLOL",
              "source_chunk_id": "{chunk_id}",
              "confidence": 0.88,
              "evidence_quote": "started metoprolol",
              "date": null
            }},
            {{
              "entity_type": "finding",
              "name": "ST elevation",
              "normalized_name": "st elevation",
              "source_chunk_id": "{chunk_id}",
              "confidence": 0.81,
              "evidence_quote": "ECG shows ST elevation",
              "date": null
            }}
          ]
        }}
        """
    )
    service = ClinicalEntityExtractionService(llm_client)

    result = service.extract_entities(
        source_chunk_id=chunk_id,
        chunk_text="Patient reports chest pain. ECG shows ST elevation. Started metoprolol.",
    )

    assert [entity.entity_type for entity in result.entities] == ["symptom", "medication", "finding"]
    assert result.entities[0].normalized_name == "chest pain"
    assert result.entities[0].source_chunk_id == chunk_id
    assert result.entities[0].confidence == 0.92
    assert result.entities[0].evidence_quote == "Patient reports chest pain"
    assert result.entities[0].date is not None
    assert result.entities[1].normalized_name == "metoprolol"
    assert "Return only valid JSON" in llm_client.prompts[0]
    assert "source_chunk_id" in llm_client.prompts[0]


def test_extract_entities_returns_empty_result_for_blank_chunk() -> None:
    chunk_id = uuid4()
    llm_client = FakeLLMClient('{"entities": []}')
    service = ClinicalEntityExtractionService(llm_client)

    result = service.extract_entities(source_chunk_id=chunk_id, chunk_text="   \n ")

    assert result.entities == []
    assert llm_client.prompts == []


def test_extract_entities_deduplicates_identical_entities() -> None:
    chunk_id = uuid4()
    entity = f"""
      {{
        "entity_type": "symptom",
        "name": "Chest pain",
        "normalized_name": "chest pain",
        "source_chunk_id": "{chunk_id}",
        "confidence": 0.9,
        "evidence_quote": "chest pain",
        "date": null
      }}
    """
    service = ClinicalEntityExtractionService(FakeLLMClient(f'{{"entities": [{entity}, {entity}]}}'))

    result = service.extract_entities(source_chunk_id=chunk_id, chunk_text="chest pain")

    assert len(result.entities) == 1


def test_extract_entities_rejects_invalid_json() -> None:
    service = ClinicalEntityExtractionService(FakeLLMClient("not json"))

    with pytest.raises(EntityExtractionError, match="invalid JSON"):
        service.extract_entities(source_chunk_id=uuid4(), chunk_text="Patient reports chest pain.")


def test_extract_entities_rejects_missing_or_extra_top_level_keys() -> None:
    service = ClinicalEntityExtractionService(
        FakeLLMClient('{"entities": [], "extra": []}')
    )

    with pytest.raises(EntityExtractionError, match="clinical entity schema"):
        service.extract_entities(source_chunk_id=uuid4(), chunk_text="Patient reports chest pain.")


def test_extract_entities_rejects_invalid_entity_type() -> None:
    chunk_id = uuid4()
    service = ClinicalEntityExtractionService(
        FakeLLMClient(
            f"""
            {{
              "entities": [
                {{
                  "entity_type": "unsupported",
                  "name": "Chest pain",
                  "normalized_name": "chest pain",
                  "source_chunk_id": "{chunk_id}",
                  "confidence": 0.9,
                  "evidence_quote": "chest pain",
                  "date": null
                }}
              ]
            }}
            """
        )
    )

    with pytest.raises(EntityExtractionError, match="invalid entity values"):
        service.extract_entities(source_chunk_id=chunk_id, chunk_text="Patient reports chest pain.")


def test_extract_entities_rejects_invalid_confidence() -> None:
    chunk_id = uuid4()
    service = ClinicalEntityExtractionService(
        FakeLLMClient(
            f"""
            {{
              "entities": [
                {{
                  "entity_type": "symptom",
                  "name": "Chest pain",
                  "normalized_name": "chest pain",
                  "source_chunk_id": "{chunk_id}",
                  "confidence": 1.7,
                  "evidence_quote": "chest pain",
                  "date": null
                }}
              ]
            }}
            """
        )
    )

    with pytest.raises(EntityExtractionError, match="invalid entity values"):
        service.extract_entities(source_chunk_id=chunk_id, chunk_text="Patient reports chest pain.")


def test_extract_entities_rejects_wrong_source_chunk_id() -> None:
    chunk_id = uuid4()
    wrong_chunk_id = uuid4()
    service = ClinicalEntityExtractionService(
        FakeLLMClient(
            f"""
            {{
              "entities": [
                {{
                  "entity_type": "symptom",
                  "name": "Chest pain",
                  "normalized_name": "chest pain",
                  "source_chunk_id": "{wrong_chunk_id}",
                  "confidence": 0.9,
                  "evidence_quote": "chest pain",
                  "date": null
                }}
              ]
            }}
            """
        )
    )

    with pytest.raises(EntityExtractionError, match="wrong source chunk"):
        service.extract_entities(source_chunk_id=chunk_id, chunk_text="Patient reports chest pain.")
