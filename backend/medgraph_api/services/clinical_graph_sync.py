from datetime import date, datetime
from typing import Any

from medgraph_api.models.document import Document
from medgraph_api.models.document_chunk import DocumentChunk
from medgraph_api.models.patient import Patient
from medgraph_api.repositories.clinical_graph_repository import ClinicalGraphRepository


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

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, datetime | date):
            return value.isoformat()
        return value
