from datetime import date, datetime
from typing import Any

from medgraph_api.models.document import Document
from medgraph_api.models.document_chunk import DocumentChunk
from medgraph_api.models.patient import Patient
from medgraph_api.repositories.clinical_graph_repository import ClinicalGraphRepository
from medgraph_api.schemas.clinical_entity import ClinicalEntityType, ExtractedClinicalEntities
from medgraph_api.schemas.clinical_relationship import ExtractedClinicalRelationships

ENTITY_LABEL_BY_TYPE = {
    ClinicalEntityType.SYMPTOM: "Symptom",
    ClinicalEntityType.MEDICATION: "Medication",
    ClinicalEntityType.DIAGNOSIS: "Diagnosis",
    ClinicalEntityType.LAB_TEST: "LabTest",
    ClinicalEntityType.PROCEDURE: "Procedure",
    ClinicalEntityType.FINDING: "ECGFinding",
}


class ClinicalGraphSyncService:
    def __init__(self, graph: ClinicalGraphRepository) -> None:
        self.graph = graph

    def sync_patient(self, patient: Patient) -> None:
        patient_id = str(patient.id)
        self.graph.upsert_patient_node(
            patient_id=patient_id,
            properties={
                "id": patient_id,
                "patient_id": patient_id,
                "source_table": "patients",
                "medical_record_number": patient.medical_record_number,
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "date_of_birth": self._serialize_value(patient.date_of_birth),
                "sex": patient.sex,
                "created_at": self._serialize_value(patient.created_at),
                "updated_at": self._serialize_value(patient.updated_at),
            },
        )

    def sync_document(self, document: Document) -> None:
        patient_id = str(document.patient_id)
        document_id = str(document.id)
        self.graph.upsert_document_node(
            document_id=document_id,
            properties={
                "id": document_id,
                "document_id": document_id,
                "patient_id": patient_id,
                "source_table": "documents",
                "filename": document.filename,
                "content_type": document.content_type,
                "processing_status": document.processing_status,
                "summary": document.summary,
                "created_at": self._serialize_value(document.created_at),
                "updated_at": self._serialize_value(document.updated_at),
            },
        )
        self.graph.create_relationship(
            from_label="Patient",
            from_key="id",
            from_value=patient_id,
            relationship_type="PATIENT_HAS_DOCUMENT",
            to_label="Document",
            to_key="id",
            to_value=document_id,
        )

    def sync_chunk(self, chunk: DocumentChunk) -> None:
        document_id = str(chunk.document_id)
        chunk_id = str(chunk.id)
        chunk_metadata = chunk.chunk_metadata or {}
        self.graph.upsert_chunk_node(
            chunk_id=chunk_id,
            properties={
                "id": chunk_id,
                "chunk_id": chunk_id,
                "document_id": document_id,
                "patient_id": str(chunk.patient_id),
                "source_table": "document_chunks",
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "embedding_model": chunk.embedding_model,
                "token_count": chunk.token_count,
                "char_start": chunk_metadata.get("char_start"),
                "char_end": chunk_metadata.get("char_end"),
                "created_at": self._serialize_value(chunk.created_at),
            },
        )
        self.graph.create_relationship(
            from_label="Document",
            from_key="id",
            from_value=document_id,
            relationship_type="DOCUMENT_HAS_CHUNK",
            to_label="Chunk",
            to_key="id",
            to_value=chunk_id,
        )

    def sync_chunks(self, chunks: list[DocumentChunk]) -> None:
        for chunk in chunks:
            self.sync_chunk(chunk)

    def sync_entities_for_chunk(
        self,
        chunk: DocumentChunk,
        entities: ExtractedClinicalEntities,
    ) -> None:
        chunk_id = str(chunk.id)
        for entity in entities.entities:
            entity_label = ENTITY_LABEL_BY_TYPE[entity.entity_type]
            entity_key = "normalized_name"
            entity_value = entity.normalized_name
            relationship_properties = {
                "source_chunk_id": str(entity.source_chunk_id),
                "confidence": entity.confidence,
                "evidence": entity.evidence_quote,
                "date": self._serialize_value(entity.date),
            }
            self.graph.upsert_entity_node(
                label=entity_label,
                key=entity_key,
                value=entity_value,
                properties={
                    "normalized_name": entity.normalized_name,
                    "name": entity.name,
                    "entity_type": entity.entity_type.value,
                    "patient_id": str(chunk.patient_id),
                    "source_chunk_id": chunk_id,
                    "source_table": "document_chunks",
                    "last_evidence_quote": entity.evidence_quote,
                    "last_confidence": entity.confidence,
                    "last_seen_at": self._serialize_value(chunk.created_at),
                    "date": self._serialize_value(entity.date),
                },
            )
            self.graph.link_chunk_to_entity(
                chunk_id=chunk_id,
                entity_label=entity_label,
                entity_key=entity_key,
                entity_value=entity_value,
                properties=relationship_properties,
            )
            self.graph.link_entity_to_chunk(
                entity_label=entity_label,
                entity_key=entity_key,
                entity_value=entity_value,
                chunk_id=chunk_id,
                properties=relationship_properties,
            )

    def sync_relationships(
        self,
        entities: ExtractedClinicalEntities,
        relationships: ExtractedClinicalRelationships,
    ) -> None:
        entity_labels = {
            entity.normalized_name: ENTITY_LABEL_BY_TYPE[entity.entity_type]
            for entity in entities.entities
        }
        for relationship in relationships.relationships:
            source_label = entity_labels[relationship.source]
            target_label = entity_labels[relationship.target]
            self.graph.create_relationship(
                from_label=source_label,
                from_key="normalized_name",
                from_value=relationship.source,
                relationship_type=relationship.type.value,
                to_label=target_label,
                to_key="normalized_name",
                to_value=relationship.target,
                properties={
                    "source_chunk_id": str(relationship.source_chunk_id),
                    "evidence": relationship.evidence,
                    "confidence": relationship.confidence,
                },
            )

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, datetime | date):
            return value.isoformat()
        return value
