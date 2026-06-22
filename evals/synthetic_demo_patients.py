from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SYNTHETIC_DEMO_PATIENTS: list[dict[str, Any]] = [
    {
        "patient_id": "demo_patient_cardiac",
        "profile": {
            "age": 68,
            "sex": "female",
            "summary": "Synthetic cardiac follow-up record with medication change and symptoms.",
        },
        "documents": [
            {
                "document_id": "doc_cardiac_001",
                "title": "Cardiology Note",
                "created_at": "2026-03-07T09:00:00Z",
                "text": "Metoprolol dose increased after palpitations. No chest pain reported.",
            },
            {
                "document_id": "doc_cardiac_002",
                "title": "Follow-up Note",
                "created_at": "2026-03-10T10:30:00Z",
                "text": "Patient reported worsening dizziness after metoprolol dose increase.",
            },
        ],
        "timeline_events": [
            {
                "event_id": "event_cardiac_001",
                "occurred_at": "2026-03-07T09:00:00Z",
                "event_type": "medication",
                "title": "Metoprolol dose increased",
                "source_document_id": "doc_cardiac_001",
            },
            {
                "event_id": "event_cardiac_002",
                "occurred_at": "2026-03-10T10:30:00Z",
                "event_type": "symptom",
                "title": "Worsening dizziness reported",
                "source_document_id": "doc_cardiac_002",
            },
        ],
        "chunks": [
            {
                "chunk_id": "chunk_cardiac_001",
                "document_id": "doc_cardiac_001",
                "text": "Metoprolol dose increased after palpitations.",
                "entities": ["metoprolol"],
            },
            {
                "chunk_id": "chunk_cardiac_002",
                "document_id": "doc_cardiac_002",
                "text": "Patient reported worsening dizziness after metoprolol dose increase.",
                "entities": ["dizziness", "metoprolol"],
            },
        ],
        "entities": [
            {"type": "Medication", "name": "metoprolol"},
            {"type": "Symptom", "name": "dizziness"},
        ],
        "relationships": [
            {
                "source": "metoprolol",
                "target": "dizziness",
                "type": "WORSENED_AFTER",
                "evidence_chunk_ids": ["chunk_cardiac_001", "chunk_cardiac_002"],
            }
        ],
        "known_answers": [
            {
                "question": "Did dizziness worsen after the medication change?",
                "answer_points": [
                    "Metoprolol dose increased on March 7",
                    "Dizziness worsened on March 10 after the dose increase",
                ],
                "expected_chunk_ids": ["chunk_cardiac_001", "chunk_cardiac_002"],
            }
        ],
    },
    {
        "patient_id": "demo_patient_diabetes",
        "profile": {
            "age": 57,
            "sex": "male",
            "summary": "Synthetic diabetes record with glucose trend and follow-up concern.",
        },
        "documents": [
            {
                "document_id": "doc_diabetes_001",
                "title": "Primary Care Visit",
                "created_at": "2026-02-02T11:00:00Z",
                "text": "A1c elevated and metformin continued. Follow-up requested in four weeks.",
            },
            {
                "document_id": "doc_diabetes_002",
                "title": "Care Coordination Note",
                "created_at": "2026-03-09T14:00:00Z",
                "text": "Follow-up not documented after elevated A1c result.",
            },
        ],
        "timeline_events": [
            {
                "event_id": "event_diabetes_001",
                "occurred_at": "2026-02-02T11:00:00Z",
                "event_type": "lab",
                "title": "Elevated A1c noted",
                "source_document_id": "doc_diabetes_001",
            },
            {
                "event_id": "event_diabetes_002",
                "occurred_at": "2026-03-09T14:00:00Z",
                "event_type": "follow_up",
                "title": "Follow-up not documented",
                "source_document_id": "doc_diabetes_002",
            },
        ],
        "chunks": [
            {
                "chunk_id": "chunk_diabetes_001",
                "document_id": "doc_diabetes_001",
                "text": "A1c elevated and metformin continued.",
                "entities": ["a1c", "metformin"],
            },
            {
                "chunk_id": "chunk_diabetes_002",
                "document_id": "doc_diabetes_002",
                "text": "Follow-up not documented after elevated A1c result.",
                "entities": ["follow-up", "a1c"],
            },
        ],
        "entities": [
            {"type": "LabTest", "name": "a1c"},
            {"type": "Medication", "name": "metformin"},
            {"type": "Procedure", "name": "follow-up"},
        ],
        "relationships": [
            {
                "source": "a1c",
                "target": "follow-up",
                "type": "ORDERED_BECAUSE_OF",
                "evidence_chunk_ids": ["chunk_diabetes_001", "chunk_diabetes_002"],
            }
        ],
        "known_answers": [
            {
                "question": "Was diabetes follow-up documented after abnormal labs?",
                "answer_points": [
                    "A1c was elevated",
                    "Follow-up was requested but later not documented",
                ],
                "expected_chunk_ids": ["chunk_diabetes_001", "chunk_diabetes_002"],
            }
        ],
    },
    {
        "patient_id": "demo_patient_respiratory",
        "profile": {
            "age": 74,
            "sex": "female",
            "summary": "Synthetic respiratory record with repeated ED visits.",
        },
        "documents": [
            {
                "document_id": "doc_respiratory_001",
                "title": "ED Triage Note",
                "created_at": "2026-04-12T08:15:00Z",
                "text": "Emergency department visit for shortness of breath.",
            },
            {
                "document_id": "doc_respiratory_002",
                "title": "Return ED Note",
                "created_at": "2026-04-15T06:45:00Z",
                "text": "Returned to emergency department with worsening shortness of breath.",
            },
        ],
        "timeline_events": [
            {
                "event_id": "event_respiratory_001",
                "occurred_at": "2026-04-12T08:15:00Z",
                "event_type": "encounter",
                "title": "ED visit for shortness of breath",
                "source_document_id": "doc_respiratory_001",
            },
            {
                "event_id": "event_respiratory_002",
                "occurred_at": "2026-04-15T06:45:00Z",
                "event_type": "encounter",
                "title": "Return ED visit with worsening dyspnea",
                "source_document_id": "doc_respiratory_002",
            },
        ],
        "chunks": [
            {
                "chunk_id": "chunk_respiratory_001",
                "document_id": "doc_respiratory_001",
                "text": "Emergency department visit for shortness of breath.",
                "entities": ["emergency department", "shortness of breath"],
            },
            {
                "chunk_id": "chunk_respiratory_002",
                "document_id": "doc_respiratory_002",
                "text": "Returned to emergency department with worsening shortness of breath.",
                "entities": ["emergency department", "shortness of breath"],
            },
        ],
        "entities": [
            {"type": "Symptom", "name": "shortness of breath"},
            {"type": "Procedure", "name": "emergency department"},
        ],
        "relationships": [
            {
                "source": "shortness of breath",
                "target": "emergency department",
                "type": "ASSOCIATED_WITH",
                "evidence_chunk_ids": ["chunk_respiratory_001", "chunk_respiratory_002"],
            }
        ],
        "known_answers": [
            {
                "question": "Were there repeated emergency visits for respiratory symptoms?",
                "answer_points": [
                    "ED visit occurred on April 12",
                    "Return ED visit occurred on April 15 with worsening shortness of breath",
                ],
                "expected_chunk_ids": ["chunk_respiratory_001", "chunk_respiratory_002"],
            }
        ],
    },
    {
        "patient_id": "demo_patient_contradiction",
        "profile": {
            "age": 63,
            "sex": "male",
            "summary": "Synthetic record with intentionally conflicting chest pain claims.",
        },
        "documents": [
            {
                "document_id": "doc_contradiction_001",
                "title": "Nursing Note",
                "created_at": "2026-05-04T09:00:00Z",
                "text": "Patient denied chest pain during intake.",
            },
            {
                "document_id": "doc_contradiction_002",
                "title": "Physician Note",
                "created_at": "2026-05-04T09:30:00Z",
                "text": "Patient reported chest pain radiating to the left arm.",
            },
        ],
        "timeline_events": [
            {
                "event_id": "event_contradiction_001",
                "occurred_at": "2026-05-04T09:00:00Z",
                "event_type": "symptom",
                "title": "Chest pain denied",
                "source_document_id": "doc_contradiction_001",
            },
            {
                "event_id": "event_contradiction_002",
                "occurred_at": "2026-05-04T09:30:00Z",
                "event_type": "symptom",
                "title": "Chest pain reported",
                "source_document_id": "doc_contradiction_002",
            },
        ],
        "chunks": [
            {
                "chunk_id": "chunk_contradiction_001",
                "document_id": "doc_contradiction_001",
                "text": "Patient denied chest pain during intake.",
                "entities": ["chest pain"],
            },
            {
                "chunk_id": "chunk_contradiction_002",
                "document_id": "doc_contradiction_002",
                "text": "Patient reported chest pain radiating to the left arm.",
                "entities": ["chest pain"],
            },
        ],
        "entities": [{"type": "Symptom", "name": "chest pain"}],
        "relationships": [
            {
                "source": "chest pain denied",
                "target": "chest pain reported",
                "type": "CONTRAINDICATES",
                "evidence_chunk_ids": ["chunk_contradiction_001", "chunk_contradiction_002"],
            }
        ],
        "known_answers": [
            {
                "question": "Are there contradictions about chest pain?",
                "answer_points": [
                    "Nursing note says chest pain was denied",
                    "Physician note says chest pain was reported",
                ],
                "expected_chunk_ids": ["chunk_contradiction_001", "chunk_contradiction_002"],
            }
        ],
    },
    {
        "patient_id": "demo_patient_medication_change",
        "profile": {
            "age": 70,
            "sex": "female",
            "summary": "Synthetic medication continuity record with stop and resume events.",
        },
        "documents": [
            {
                "document_id": "doc_medchange_001",
                "title": "Discharge Summary",
                "created_at": "2026-06-01T16:00:00Z",
                "text": "Warfarin was stopped because INR was elevated.",
            },
            {
                "document_id": "doc_medchange_002",
                "title": "Anticoagulation Clinic Note",
                "created_at": "2026-06-08T13:00:00Z",
                "text": "Warfarin resumed at lower dose after repeat INR normalized.",
            },
        ],
        "timeline_events": [
            {
                "event_id": "event_medchange_001",
                "occurred_at": "2026-06-01T16:00:00Z",
                "event_type": "medication",
                "title": "Warfarin stopped",
                "source_document_id": "doc_medchange_001",
            },
            {
                "event_id": "event_medchange_002",
                "occurred_at": "2026-06-08T13:00:00Z",
                "event_type": "medication",
                "title": "Warfarin resumed",
                "source_document_id": "doc_medchange_002",
            },
        ],
        "chunks": [
            {
                "chunk_id": "chunk_medchange_001",
                "document_id": "doc_medchange_001",
                "text": "Warfarin was stopped because INR was elevated.",
                "entities": ["warfarin", "inr"],
            },
            {
                "chunk_id": "chunk_medchange_002",
                "document_id": "doc_medchange_002",
                "text": "Warfarin resumed at lower dose after repeat INR normalized.",
                "entities": ["warfarin", "inr"],
            },
        ],
        "entities": [
            {"type": "Medication", "name": "warfarin"},
            {"type": "LabTest", "name": "inr"},
        ],
        "relationships": [
            {
                "source": "warfarin",
                "target": "inr",
                "type": "STOPPED_AT",
                "evidence_chunk_ids": ["chunk_medchange_001"],
            },
            {
                "source": "warfarin",
                "target": "inr",
                "type": "IMPROVED_AFTER",
                "evidence_chunk_ids": ["chunk_medchange_002"],
            },
        ],
        "known_answers": [
            {
                "question": "What happened after warfarin was stopped?",
                "answer_points": [
                    "Warfarin was stopped after elevated INR",
                    "Warfarin was resumed at a lower dose after INR normalized",
                ],
                "expected_chunk_ids": ["chunk_medchange_001", "chunk_medchange_002"],
            }
        ],
    },
]


def generate_synthetic_demo_patients() -> list[dict[str, Any]]:
    return [json.loads(json.dumps(patient)) for patient in SYNTHETIC_DEMO_PATIENTS]


def write_jsonl(patients: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(json.dumps(patient, sort_keys=True) for patient in patients) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic MedGraph eval patients.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evals/datasets/synthetic_demo_patients.jsonl"),
        help="JSONL output path.",
    )
    args = parser.parse_args()

    write_jsonl(generate_synthetic_demo_patients(), args.output)
    print(f"Wrote {len(SYNTHETIC_DEMO_PATIENTS)} synthetic patients to {args.output}")


if __name__ == "__main__":
    main()
