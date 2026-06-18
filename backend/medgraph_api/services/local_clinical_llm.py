import json
import re
from itertools import combinations

ENTITY_PATTERNS = {
    "symptom": [
        "chest pain",
        "chest discomfort",
        "shortness of breath",
        "dyspnea",
        "fatigue",
        "dizziness",
        "palpitations",
    ],
    "medication": [
        "albuterol",
        "aspirin",
        "atorvastatin",
        "insulin",
        "lisinopril",
        "metoprolol",
        "warfarin",
    ],
    "diagnosis": [
        "atrial fibrillation",
        "diabetes",
        "heart failure",
        "hypertension",
        "myocardial infarction",
        "pneumonia",
    ],
    "lab_test": [
        "a1c",
        "bnp",
        "creatinine",
        "hemoglobin",
        "potassium",
        "sodium",
        "troponin",
    ],
    "procedure": [
        "ct",
        "ecg",
        "echocardiogram",
        "electrocardiogram",
        "mri",
        "x-ray",
    ],
    "finding": [
        "st depression",
        "st elevation",
        "qt prolongation",
    ],
}


class LocalClinicalEntityLLMClient:
    def generate(self, prompt: str) -> str:
        source_chunk_id = _extract_source_chunk_id(prompt)
        chunk_text = _extract_chunk_text(prompt)
        normalized_chunk = chunk_text.lower()
        entities = []

        for entity_type, patterns in ENTITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(rf"\b{re.escape(pattern)}\b", normalized_chunk):
                    entities.append(
                        {
                            "entity_type": entity_type,
                            "name": _match_source_text(chunk_text, pattern),
                            "normalized_name": pattern,
                            "source_chunk_id": source_chunk_id,
                            "confidence": 0.72,
                            "evidence_quote": _evidence_sentence(chunk_text, pattern),
                            "date": None,
                        }
                    )

        return json.dumps({"entities": entities})


class LocalClinicalRelationshipLLMClient:
    def generate(self, prompt: str) -> str:
        source_chunk_id = _extract_source_chunk_id(prompt)
        chunk_text = _extract_chunk_text(prompt)
        entities = _extract_prompt_entities(prompt)
        relationships = []

        for source, target in combinations(entities, 2):
            relationship_type = _infer_relationship_type(chunk_text, source, target)
            if relationship_type is None:
                continue

            relationships.append(
                {
                    "source": source["name"],
                    "target": target["name"],
                    "type": relationship_type,
                    "source_chunk_id": source_chunk_id,
                    "evidence": _shared_evidence(chunk_text, source["name"], target["name"]),
                    "confidence": 0.64,
                }
            )

        return json.dumps({"relationships": relationships})


def _extract_source_chunk_id(prompt: str) -> str:
    match = re.search(r'source_chunk_id:\s*"([^"]+)"', prompt)
    if match:
        return match.group(1)

    match = re.search(r"source_chunk_id[^0-9a-fA-F-]*([0-9a-fA-F-]{36})", prompt)
    if match:
        return match.group(1)

    return "00000000-0000-0000-0000-000000000000"


def _extract_chunk_text(prompt: str) -> str:
    match = re.search(r"Chunk:\s*(.*?)\s*Strict JSON response:", prompt, re.DOTALL)
    if match:
        return match.group(1).strip()
    return prompt


def _extract_prompt_entities(prompt: str) -> list[dict[str, str]]:
    match = re.search(
        r"Only use source and target values from this extracted entity list:\s*(.*?)\s*Use an empty",
        prompt,
        re.DOTALL,
    )
    if not match:
        return []

    entities = []
    for line in match.group(1).splitlines():
        entity_match = re.match(r"-\s*(.*?)\s*\((.*?)\)", line.strip())
        if entity_match:
            entities.append({"name": entity_match.group(1).strip(), "type": entity_match.group(2)})
    return entities


def _infer_relationship_type(
    chunk_text: str,
    source: dict[str, str],
    target: dict[str, str],
) -> str | None:
    normalized_chunk = chunk_text.lower()
    source_type = source["type"]
    target_type = target["type"]

    if source_type == "finding" and target_type == "diagnosis":
        return "SUPPORTS"
    if source_type == "lab_test" and target_type == "diagnosis":
        return "ORDERED_BECAUSE_OF"
    if source_type == "medication" and target_type == "symptom" and "after" in normalized_chunk:
        return "WORSENED_AFTER"
    if source_type == "symptom" and target_type == "medication" and "after" in normalized_chunk:
        return "OCCURRED_AFTER"
    if "started" in normalized_chunk and source_type == "medication":
        return "STARTED_AT"
    if "stopped" in normalized_chunk and source_type == "medication":
        return "STOPPED_AT"
    if source["name"] in normalized_chunk and target["name"] in normalized_chunk:
        return "ASSOCIATED_WITH"

    return None


def _match_source_text(chunk_text: str, normalized_entity: str) -> str:
    match = re.search(rf"\b{re.escape(normalized_entity)}\b", chunk_text, re.IGNORECASE)
    if match:
        return match.group(0)
    return normalized_entity


def _evidence_sentence(chunk_text: str, normalized_entity: str) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+", chunk_text):
        if normalized_entity in sentence.lower():
            return sentence.strip()[:500]
    return chunk_text.strip()[:500]


def _shared_evidence(chunk_text: str, source: str, target: str) -> str:
    source_lower = source.lower()
    target_lower = target.lower()
    for sentence in re.split(r"(?<=[.!?])\s+", chunk_text):
        lowered_sentence = sentence.lower()
        if source_lower in lowered_sentence and target_lower in lowered_sentence:
            return sentence.strip()[:500]
    return chunk_text.strip()[:500]
