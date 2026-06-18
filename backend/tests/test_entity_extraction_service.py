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


def test_extract_entities_from_chunk_with_strict_json_response() -> None:
    llm_client = FakeLLMClient(
        """
        {
          "symptoms": ["chest pain", "shortness of breath", "chest pain"],
          "medications": ["metoprolol"],
          "diagnoses": ["atrial fibrillation"],
          "lab_tests": ["troponin"],
          "procedures": ["ECG"],
          "findings": ["ST elevation"]
        }
        """
    )
    service = ClinicalEntityExtractionService(llm_client)

    result = service.extract_entities(
        "Patient reports chest pain and shortness of breath. ECG shows ST elevation."
    )

    assert result.symptoms == ["chest pain", "shortness of breath"]
    assert result.medications == ["metoprolol"]
    assert result.diagnoses == ["atrial fibrillation"]
    assert result.lab_tests == ["troponin"]
    assert result.procedures == ["ECG"]
    assert result.findings == ["ST elevation"]
    assert "Return only valid JSON" in llm_client.prompts[0]
    assert "Extract only entities explicitly stated" in llm_client.prompts[0]


def test_extract_entities_returns_empty_result_for_blank_chunk() -> None:
    llm_client = FakeLLMClient("{}")
    service = ClinicalEntityExtractionService(llm_client)

    result = service.extract_entities("   \n ")

    assert result.symptoms == []
    assert result.medications == []
    assert result.diagnoses == []
    assert result.lab_tests == []
    assert result.procedures == []
    assert result.findings == []
    assert llm_client.prompts == []


def test_extract_entities_rejects_invalid_json() -> None:
    service = ClinicalEntityExtractionService(FakeLLMClient("not json"))

    with pytest.raises(EntityExtractionError, match="invalid JSON"):
        service.extract_entities("Patient reports chest pain.")


def test_extract_entities_rejects_missing_or_extra_keys() -> None:
    service = ClinicalEntityExtractionService(
        FakeLLMClient(
            """
            {
              "symptoms": [],
              "medications": [],
              "diagnoses": [],
              "lab_tests": [],
              "procedures": [],
              "extra": []
            }
            """
        )
    )

    with pytest.raises(EntityExtractionError, match="clinical entity schema"):
        service.extract_entities("Patient reports chest pain.")


def test_extract_entities_rejects_non_list_entity_values() -> None:
    service = ClinicalEntityExtractionService(
        FakeLLMClient(
            """
            {
              "symptoms": "chest pain",
              "medications": [],
              "diagnoses": [],
              "lab_tests": [],
              "procedures": [],
              "findings": []
            }
            """
        )
    )

    with pytest.raises(EntityExtractionError, match="invalid entity values"):
        service.extract_entities("Patient reports chest pain.")
