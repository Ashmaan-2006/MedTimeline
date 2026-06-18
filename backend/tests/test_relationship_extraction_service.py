from uuid import uuid4

import pytest

from medgraph_api.schemas.clinical_entity import (
    ExtractedClinicalEntities,
    ExtractedClinicalEntity,
)
from medgraph_api.services.relationship_extraction_service import (
    ClinicalRelationshipExtractionService,
    RelationshipExtractionError,
)


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def build_entities(chunk_id):
    return ExtractedClinicalEntities(
        entities=[
            ExtractedClinicalEntity(
                entity_type="medication",
                name="Metoprolol",
                normalized_name="metoprolol",
                source_chunk_id=chunk_id,
                confidence=0.91,
                evidence_quote="metoprolol",
            ),
            ExtractedClinicalEntity(
                entity_type="symptom",
                name="Shortness of breath",
                normalized_name="shortness of breath",
                source_chunk_id=chunk_id,
                confidence=0.86,
                evidence_quote="shortness of breath",
            ),
        ]
    )


def test_extract_relationships_from_entities_and_chunk_context() -> None:
    chunk_id = uuid4()
    llm_client = FakeLLMClient(
        f"""
        {{
          "relationships": [
            {{
              "source": "Metoprolol",
              "target": "shortness of breath",
              "type": "WORSENED_AFTER",
              "source_chunk_id": "{chunk_id}",
              "evidence": "Patient reported shortness of breath after medication change",
              "confidence": 0.72
            }}
          ]
        }}
        """
    )
    service = ClinicalRelationshipExtractionService(llm_client)

    result = service.extract_relationships(
        source_chunk_id=chunk_id,
        chunk_text="Patient reported shortness of breath after medication change.",
        entities=build_entities(chunk_id),
    )

    assert len(result.relationships) == 1
    assert result.relationships[0].source == "metoprolol"
    assert result.relationships[0].target == "shortness of breath"
    assert result.relationships[0].type == "WORSENED_AFTER"
    assert result.relationships[0].confidence == 0.72
    assert "one of MENTIONED_IN" in llm_client.prompts[0]
    assert "metoprolol" in llm_client.prompts[0]


def test_extract_relationships_returns_empty_result_without_entities() -> None:
    chunk_id = uuid4()
    llm_client = FakeLLMClient('{"relationships": []}')
    service = ClinicalRelationshipExtractionService(llm_client)

    result = service.extract_relationships(
        source_chunk_id=chunk_id,
        chunk_text="Patient reports chest pain.",
        entities=ExtractedClinicalEntities(),
    )

    assert result.relationships == []
    assert llm_client.prompts == []


def test_extract_relationships_deduplicates_identical_relationships() -> None:
    chunk_id = uuid4()
    relationship = f"""
      {{
        "source": "metoprolol",
        "target": "shortness of breath",
        "type": "ASSOCIATED_WITH",
        "source_chunk_id": "{chunk_id}",
        "evidence": "metoprolol and shortness of breath",
        "confidence": 0.7
      }}
    """
    service = ClinicalRelationshipExtractionService(
        FakeLLMClient(f'{{"relationships": [{relationship}, {relationship}]}}')
    )

    result = service.extract_relationships(
        source_chunk_id=chunk_id,
        chunk_text="metoprolol and shortness of breath",
        entities=build_entities(chunk_id),
    )

    assert len(result.relationships) == 1


def test_extract_relationships_rejects_invalid_json() -> None:
    chunk_id = uuid4()
    service = ClinicalRelationshipExtractionService(FakeLLMClient("not json"))

    with pytest.raises(RelationshipExtractionError, match="invalid JSON"):
        service.extract_relationships(
            source_chunk_id=chunk_id,
            chunk_text="Patient reports shortness of breath.",
            entities=build_entities(chunk_id),
        )


def test_extract_relationships_rejects_unknown_relationship_type() -> None:
    chunk_id = uuid4()
    service = ClinicalRelationshipExtractionService(
        FakeLLMClient(
            f"""
            {{
              "relationships": [
                {{
                  "source": "metoprolol",
                  "target": "shortness of breath",
                  "type": "FREE_FORM_RELATIONSHIP",
                  "source_chunk_id": "{chunk_id}",
                  "evidence": "shortness of breath after medication change",
                  "confidence": 0.72
                }}
              ]
            }}
            """
        )
    )

    with pytest.raises(RelationshipExtractionError, match="invalid relationship values"):
        service.extract_relationships(
            source_chunk_id=chunk_id,
            chunk_text="shortness of breath after medication change",
            entities=build_entities(chunk_id),
        )


def test_extract_relationships_rejects_wrong_source_chunk_id() -> None:
    chunk_id = uuid4()
    wrong_chunk_id = uuid4()
    service = ClinicalRelationshipExtractionService(
        FakeLLMClient(
            f"""
            {{
              "relationships": [
                {{
                  "source": "metoprolol",
                  "target": "shortness of breath",
                  "type": "ASSOCIATED_WITH",
                  "source_chunk_id": "{wrong_chunk_id}",
                  "evidence": "shortness of breath after medication change",
                  "confidence": 0.72
                }}
              ]
            }}
            """
        )
    )

    with pytest.raises(RelationshipExtractionError, match="wrong source chunk"):
        service.extract_relationships(
            source_chunk_id=chunk_id,
            chunk_text="shortness of breath after medication change",
            entities=build_entities(chunk_id),
        )


def test_extract_relationships_rejects_unknown_entity_endpoint() -> None:
    chunk_id = uuid4()
    service = ClinicalRelationshipExtractionService(
        FakeLLMClient(
            f"""
            {{
              "relationships": [
                {{
                  "source": "unknown medication",
                  "target": "shortness of breath",
                  "type": "ASSOCIATED_WITH",
                  "source_chunk_id": "{chunk_id}",
                  "evidence": "shortness of breath after medication change",
                  "confidence": 0.72
                }}
              ]
            }}
            """
        )
    )

    with pytest.raises(RelationshipExtractionError, match="unknown relationship endpoint"):
        service.extract_relationships(
            source_chunk_id=chunk_id,
            chunk_text="shortness of breath after medication change",
            entities=build_entities(chunk_id),
        )
