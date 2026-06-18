from collections.abc import Mapping
from typing import Any

from neo4j import Session

ENTITY_LABELS = {
    "Symptom",
    "Medication",
    "Diagnosis",
    "Procedure",
    "LabTest",
    "LabResult",
    "ImagingStudy",
    "ECGFinding",
    "Provider",
}

RELATIONSHIP_TYPES = {
    "PATIENT_HAS_DOCUMENT",
    "DOCUMENT_HAS_CHUNK",
    "CHUNK_MENTIONS_ENTITY",
    "PATIENT_HAS_EVENT",
    "EVENT_MENTIONS_SYMPTOM",
    "EVENT_MENTIONS_MEDICATION",
    "EVENT_HAS_LAB_RESULT",
    "EVENT_ASSOCIATED_WITH_DIAGNOSIS",
    "MEDICATION_STARTED_AT_EVENT",
    "MEDICATION_STOPPED_AT_EVENT",
    "SYMPTOM_WORSENED_AFTER",
    "FINDING_SUPPORTS_DIAGNOSIS",
    "ENTITY_EVIDENCED_BY_CHUNK",
}

NODE_LABELS = ENTITY_LABELS | {"Patient", "Document", "Chunk", "ClinicalEvent"}


class ClinicalGraphRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_patient_node(self, patient_id: str, properties: Mapping[str, Any]) -> None:
        self._upsert_node("Patient", "id", patient_id, properties)

    def upsert_document_node(self, document_id: str, properties: Mapping[str, Any]) -> None:
        self._upsert_node("Document", "id", document_id, properties)

    def upsert_chunk_node(self, chunk_id: str, properties: Mapping[str, Any]) -> None:
        self._upsert_node("Chunk", "id", chunk_id, properties)

    def upsert_clinical_event_node(self, event_id: str, properties: Mapping[str, Any]) -> None:
        self._upsert_node("ClinicalEvent", "id", event_id, properties)

    def upsert_entity_node(
        self,
        label: str,
        key: str,
        value: str,
        properties: Mapping[str, Any],
    ) -> None:
        self._validate_label(label)
        if label not in ENTITY_LABELS:
            raise ValueError(f"Unsupported entity label: {label}")

        self._upsert_node(label, key, value, properties)

    def create_relationship(
        self,
        from_label: str,
        from_key: str,
        from_value: str,
        relationship_type: str,
        to_label: str,
        to_key: str,
        to_value: str,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        self._validate_label(from_label)
        self._validate_label(to_label)
        self._validate_relationship_type(relationship_type)
        relationship_properties = dict(properties or {})
        query = f"""
        MATCH (source:{from_label} {{{from_key}: $from_value}})
        MATCH (target:{to_label} {{{to_key}: $to_value}})
        MERGE (source)-[relationship:{relationship_type}]->(target)
        SET relationship += $properties
        """
        self.session.run(
            query,
            from_value=from_value,
            to_value=to_value,
            properties=relationship_properties,
        )

    def link_entity_to_chunk(
        self,
        entity_label: str,
        entity_key: str,
        entity_value: str,
        chunk_id: str,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        self.create_relationship(
            from_label=entity_label,
            from_key=entity_key,
            from_value=entity_value,
            relationship_type="ENTITY_EVIDENCED_BY_CHUNK",
            to_label="Chunk",
            to_key="id",
            to_value=chunk_id,
            properties=properties,
        )

    def link_event_to_patient(
        self,
        patient_id: str,
        event_id: str,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        self.create_relationship(
            from_label="Patient",
            from_key="id",
            from_value=patient_id,
            relationship_type="PATIENT_HAS_EVENT",
            to_label="ClinicalEvent",
            to_key="id",
            to_value=event_id,
            properties=properties,
        )

    def _upsert_node(
        self,
        label: str,
        key: str,
        value: str,
        properties: Mapping[str, Any],
    ) -> None:
        self._validate_label(label)
        node_properties = dict(properties)
        node_properties[key] = value
        query = f"""
        MERGE (node:{label} {{{key}: $value}})
        SET node += $properties
        """
        self.session.run(query, value=value, properties=node_properties)

    def _validate_label(self, label: str) -> None:
        if label not in NODE_LABELS:
            raise ValueError(f"Unsupported graph node label: {label}")

    def _validate_relationship_type(self, relationship_type: str) -> None:
        if relationship_type not in RELATIONSHIP_TYPES:
            raise ValueError(f"Unsupported graph relationship type: {relationship_type}")
