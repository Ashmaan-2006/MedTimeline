import json
from pathlib import Path

from evals.synthetic_demo_patients import generate_synthetic_demo_patients, write_jsonl


EXPECTED_PATIENT_IDS = {
    "demo_patient_cardiac",
    "demo_patient_diabetes",
    "demo_patient_respiratory",
    "demo_patient_contradiction",
    "demo_patient_medication_change",
}


def test_generate_synthetic_demo_patients_includes_required_personas() -> None:
    patients = generate_synthetic_demo_patients()

    assert {patient["patient_id"] for patient in patients} == EXPECTED_PATIENT_IDS


def test_synthetic_demo_patients_include_eval_facts() -> None:
    patients = generate_synthetic_demo_patients()

    for patient in patients:
        assert patient["documents"]
        assert patient["timeline_events"]
        assert patient["chunks"]
        assert patient["entities"]
        assert patient["relationships"]
        assert patient["known_answers"]
        assert all("chunk_id" in chunk and "document_id" in chunk for chunk in patient["chunks"])
        assert all("type" in entity and "name" in entity for entity in patient["entities"])
        assert all("type" in relationship for relationship in patient["relationships"])


def test_synthetic_demo_patients_encode_controlled_contradiction_case() -> None:
    patients = {
        patient["patient_id"]: patient
        for patient in generate_synthetic_demo_patients()
    }

    contradiction_patient = patients["demo_patient_contradiction"]

    assert contradiction_patient["relationships"] == [
        {
            "source": "chest pain denied",
            "target": "chest pain reported",
            "type": "CONTRAINDICATES",
            "evidence_chunk_ids": ["chunk_contradiction_001", "chunk_contradiction_002"],
        }
    ]
    assert contradiction_patient["known_answers"][0]["expected_chunk_ids"] == [
        "chunk_contradiction_001",
        "chunk_contradiction_002",
    ]


def test_write_jsonl_outputs_repeatable_patient_records(tmp_path: Path) -> None:
    output_path = tmp_path / "synthetic_demo_patients.jsonl"

    write_jsonl(generate_synthetic_demo_patients(), output_path)

    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 5
    assert rows[0]["patient_id"] == "demo_patient_cardiac"
