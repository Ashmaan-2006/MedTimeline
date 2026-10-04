import json

from medgraph_api.services.local_clinical_llm import LocalClinicalRelationshipLLMClient

CHUNK_ID = "11111111-2222-3333-4444-555555555555"


def build_prompt(chunk: str, entities: list[tuple[str, str]]) -> str:
    entity_lines = "\n".join(f"- {name} ({entity_type})" for name, entity_type in entities)
    return (
        f'source_chunk_id: "{CHUNK_ID}"\n'
        "Only use source and target values from this extracted entity list:\n"
        f"{entity_lines}\n"
        "Use an empty relationships array when none apply.\n"
        f"Chunk:\n{chunk}\n"
        "Strict JSON response:"
    )


def test_relationships_require_entities_in_the_same_sentence() -> None:
    chunk = "Patient reported dizziness on standing.\n12 Creatinine 14-Oct-2015 66 umol/L"
    prompt = build_prompt(chunk, [("dizziness", "symptom"), ("Creatinine", "lab_test")])

    response = json.loads(LocalClinicalRelationshipLLMClient().generate(prompt))

    assert response == {"relationships": []}


def test_relationship_evidence_is_the_shared_sentence() -> None:
    chunk = (
        "GENERAL INTERNAL MEDICINE DISCHARGE SUMMARY\n"
        "He has hypertension and diabetes. Tamsulosin was started for BPH."
    )
    prompt = build_prompt(chunk, [("hypertension", "diagnosis"), ("diabetes", "diagnosis")])

    response = json.loads(LocalClinicalRelationshipLLMClient().generate(prompt))

    assert response["relationships"][0]["evidence"] == "He has hypertension and diabetes."
    assert response["relationships"][0]["type"] == "ASSOCIATED_WITH"
