from dataclasses import dataclass
from datetime import date
from typing import Any

from neo4j import Session

@dataclass(frozen=True)
class PatientGraphSummary:
    patient_id: str
    document_count: int
    chunk_count: int
    entity_count: int
    relationship_count: int


@dataclass(frozen=True)
class GraphEntity:
    label: str
    normalized_name: str
    name: str | None
    mention_count: int
    evidence_count: int
    latest_seen_at: str | None


@dataclass(frozen=True)
class GraphRelationship:
    source_label: str
    source_name: str
    relationship_type: str
    target_label: str
    target_name: str
    evidence: str | None
    confidence: float | None
    source_chunk_id: str | None


@dataclass(frozen=True)
class MedicationRelatedEvent:
    event_id: str
    event_type: str | None
    title: str | None
    occurred_at: str | None
    relationship_type: str
    confidence: float | None


@dataclass(frozen=True)
class SymptomNearDate:
    normalized_name: str
    name: str | None
    chunk_id: str
    document_id: str
    created_at: str | None
    evidence: str | None
    confidence: float | None


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    document_id: str
    chunk_index: int | None
    content: str
    evidence: str | None
    confidence: float | None
    filename: str | None
    created_at: str | None


@dataclass(frozen=True)
class EntityPathStep:
    source: dict[str, Any]
    relationship_type: str
    relationship: dict[str, Any]
    target: dict[str, Any]


class ClinicalGraphQueryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_patient_graph_summary(self, patient_id: str) -> PatientGraphSummary:
        query = """
        MATCH (patient:Patient {id: $patient_id})
        OPTIONAL MATCH (patient)-[:PATIENT_HAS_DOCUMENT]->(document:Document)
        OPTIONAL MATCH (document)-[:DOCUMENT_HAS_CHUNK]->(chunk:Chunk)
        OPTIONAL MATCH (chunk)-[:CHUNK_MENTIONS_ENTITY]->(entity)
        OPTIONAL MATCH (patient)-[patient_relationship]-()
        OPTIONAL MATCH (document)-[document_relationship]-()
        OPTIONAL MATCH (chunk)-[chunk_relationship]-()
        OPTIONAL MATCH (entity)-[entity_relationship]-()
        RETURN
          count(DISTINCT document) AS document_count,
          count(DISTINCT chunk) AS chunk_count,
          count(DISTINCT entity) AS entity_count,
          count(DISTINCT patient_relationship)
            + count(DISTINCT document_relationship)
            + count(DISTINCT chunk_relationship)
            + count(DISTINCT entity_relationship) AS relationship_count
        """
        record = self._single_record(query, patient_id=patient_id)
        return PatientGraphSummary(
            patient_id=patient_id,
            document_count=record.get("document_count", 0),
            chunk_count=record.get("chunk_count", 0),
            entity_count=record.get("entity_count", 0),
            relationship_count=record.get("relationship_count", 0),
        )

    def get_entities_for_patient(self, patient_id: str) -> list[GraphEntity]:
        query = """
        MATCH (:Patient {id: $patient_id})-[:PATIENT_HAS_DOCUMENT]->(:Document)
          -[:DOCUMENT_HAS_CHUNK]->(chunk:Chunk)-[:CHUNK_MENTIONS_ENTITY]->(entity)
        WITH entity, labels(entity) AS labels, collect(DISTINCT chunk) AS chunks
        OPTIONAL MATCH (entity)-[evidence:ENTITY_EVIDENCED_BY_CHUNK]->(:Chunk)
        RETURN
          labels[0] AS label,
          entity.normalized_name AS normalized_name,
          entity.name AS name,
          size(chunks) AS mention_count,
          count(DISTINCT evidence) AS evidence_count,
          entity.last_seen_at AS latest_seen_at
        ORDER BY mention_count DESC, normalized_name ASC
        """
        return [
            GraphEntity(
                label=record["label"],
                normalized_name=record["normalized_name"],
                name=record.get("name"),
                mention_count=record["mention_count"],
                evidence_count=record["evidence_count"],
                latest_seen_at=record.get("latest_seen_at"),
            )
            for record in self._records(query, patient_id=patient_id)
        ]

    def get_relationships_for_patient(self, patient_id: str) -> list[GraphRelationship]:
        query = """
        MATCH (:Patient {id: $patient_id})-[:PATIENT_HAS_DOCUMENT]->(:Document)
          -[:DOCUMENT_HAS_CHUNK]->(:Chunk)-[:CHUNK_MENTIONS_ENTITY]->(source)
        MATCH (source)-[relationship]->(target)
        WHERE target.normalized_name IS NOT NULL
          AND type(relationship) <> "ENTITY_EVIDENCED_BY_CHUNK"
        RETURN DISTINCT
          labels(source)[0] AS source_label,
          coalesce(source.normalized_name, source.name) AS source_name,
          type(relationship) AS relationship_type,
          labels(target)[0] AS target_label,
          coalesce(target.normalized_name, target.name) AS target_name,
          relationship.evidence AS evidence,
          relationship.confidence AS confidence,
          relationship.source_chunk_id AS source_chunk_id
        ORDER BY source_name ASC, relationship_type ASC, target_name ASC
        """
        return [
            GraphRelationship(
                source_label=record["source_label"],
                source_name=record["source_name"],
                relationship_type=record["relationship_type"],
                target_label=record["target_label"],
                target_name=record["target_name"],
                evidence=record.get("evidence"),
                confidence=record.get("confidence"),
                source_chunk_id=record.get("source_chunk_id"),
            )
            for record in self._records(query, patient_id=patient_id)
        ]

    def get_events_related_to_medication(
        self,
        patient_id: str,
        medication: str,
    ) -> list[MedicationRelatedEvent]:
        query = """
        MATCH (:Patient {id: $patient_id})-[:PATIENT_HAS_EVENT]->(event:ClinicalEvent)
        MATCH (medication:Medication {normalized_name: $medication})
        MATCH (event)-[relationship]-(medication)
        RETURN
          event.id AS event_id,
          event.event_type AS event_type,
          event.title AS title,
          event.occurred_at AS occurred_at,
          type(relationship) AS relationship_type,
          relationship.confidence AS confidence
        ORDER BY occurred_at ASC, event_id ASC
        """
        return [
            MedicationRelatedEvent(
                event_id=record["event_id"],
                event_type=record.get("event_type"),
                title=record.get("title"),
                occurred_at=record.get("occurred_at"),
                relationship_type=record["relationship_type"],
                confidence=record.get("confidence"),
            )
            for record in self._records(
                query,
                patient_id=patient_id,
                medication=self._normalize_entity_name(medication),
            )
        ]

    def get_symptoms_near_date(
        self,
        patient_id: str,
        date_range: tuple[date, date],
    ) -> list[SymptomNearDate]:
        start_date, end_date = date_range
        query = """
        MATCH (:Patient {id: $patient_id})-[:PATIENT_HAS_DOCUMENT]->(document:Document)
          -[:DOCUMENT_HAS_CHUNK]->(chunk:Chunk)-[mention:CHUNK_MENTIONS_ENTITY]->(symptom:Symptom)
        WHERE date(chunk.created_at) >= date($start_date)
          AND date(chunk.created_at) <= date($end_date)
        RETURN
          symptom.normalized_name AS normalized_name,
          symptom.name AS name,
          chunk.id AS chunk_id,
          document.id AS document_id,
          chunk.created_at AS created_at,
          mention.evidence AS evidence,
          mention.confidence AS confidence
        ORDER BY created_at ASC, normalized_name ASC
        """
        return [
            SymptomNearDate(
                normalized_name=record["normalized_name"],
                name=record.get("name"),
                chunk_id=record["chunk_id"],
                document_id=record["document_id"],
                created_at=record.get("created_at"),
                evidence=record.get("evidence"),
                confidence=record.get("confidence"),
            )
            for record in self._records(
                query,
                patient_id=patient_id,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )
        ]

    def get_evidence_chunks_for_entity(
        self,
        patient_id: str,
        entity: str,
    ) -> list[EvidenceChunk]:
        query = """
        MATCH (:Patient {id: $patient_id})-[:PATIENT_HAS_DOCUMENT]->(document:Document)
          -[:DOCUMENT_HAS_CHUNK]->(chunk:Chunk)
        MATCH (entity)-[evidence:ENTITY_EVIDENCED_BY_CHUNK]->(chunk)
        WHERE entity.normalized_name = $entity
        RETURN
          chunk.id AS chunk_id,
          document.id AS document_id,
          chunk.chunk_index AS chunk_index,
          chunk.content AS content,
          evidence.evidence AS evidence,
          evidence.confidence AS confidence,
          document.filename AS filename,
          chunk.created_at AS created_at
        ORDER BY confidence DESC, chunk_index ASC
        """
        return [
            EvidenceChunk(
                chunk_id=record["chunk_id"],
                document_id=record["document_id"],
                chunk_index=record.get("chunk_index"),
                content=record["content"],
                evidence=record.get("evidence"),
                confidence=record.get("confidence"),
                filename=record.get("filename"),
                created_at=record.get("created_at"),
            )
            for record in self._records(
                query,
                patient_id=patient_id,
                entity=self._normalize_entity_name(entity),
            )
        ]

    def get_paths_between_entities(
        self,
        patient_id: str,
        source: str,
        target: str,
        max_hops: int = 4,
    ) -> list[list[EntityPathStep]]:
        if max_hops < 1 or max_hops > 6:
            raise ValueError("max_hops must be between 1 and 6.")

        query = f"""
        MATCH (:Patient {{id: $patient_id}})-[:PATIENT_HAS_DOCUMENT]->(:Document)
          -[:DOCUMENT_HAS_CHUNK]->(:Chunk)-[:CHUNK_MENTIONS_ENTITY]->(source)
        MATCH (:Patient {{id: $patient_id}})-[:PATIENT_HAS_DOCUMENT]->(:Document)
          -[:DOCUMENT_HAS_CHUNK]->(:Chunk)-[:CHUNK_MENTIONS_ENTITY]->(target)
        WHERE source.normalized_name = $source
          AND target.normalized_name = $target
        MATCH path = shortestPath((source)-[*1..{max_hops}]-(target))
        RETURN path
        LIMIT 10
        """
        paths = []
        for record in self._records(
            query,
            patient_id=patient_id,
            source=self._normalize_entity_name(source),
            target=self._normalize_entity_name(target),
        ):
            paths.append(self._serialize_path(record["path"]))
        return paths

    def _records(self, query: str, **parameters: Any) -> list[Any]:
        return list(self.session.run(query, **parameters))

    def _single_record(self, query: str, **parameters: Any) -> Any:
        record = self.session.run(query, **parameters).single()
        if record is None:
            return {}
        return record

    def _normalize_entity_name(self, entity: str) -> str:
        normalized_entity = " ".join(entity.split()).strip().lower()
        if not normalized_entity:
            raise ValueError("Entity name cannot be blank.")
        return normalized_entity

    def _serialize_path(self, path: Any) -> list[EntityPathStep]:
        steps = []
        nodes_by_element_id = {
            node.element_id: node for node in path.nodes
        } if not isinstance(path.nodes, dict) else path.nodes
        for relationship in path.relationships:
            source_node = self._relationship_node(
                relationship=relationship,
                node_attribute="start_node",
                nodes_by_element_id=nodes_by_element_id,
            )
            target_node = self._relationship_node(
                relationship=relationship,
                node_attribute="end_node",
                nodes_by_element_id=nodes_by_element_id,
            )
            steps.append(
                EntityPathStep(
                    source=self._serialize_node(source_node),
                    relationship_type=relationship.type,
                    relationship=dict(relationship),
                    target=self._serialize_node(target_node),
                )
            )
        return steps

    def _relationship_node(
        self,
        relationship: Any,
        node_attribute: str,
        nodes_by_element_id: dict[str, Any],
    ) -> Any:
        node = getattr(relationship, node_attribute, None)
        if node is not None:
            return node

        node_id_attribute = f"{node_attribute}_id"
        node_id = getattr(relationship, node_id_attribute)
        return nodes_by_element_id[node_id]

    def _serialize_node(self, node: Any) -> dict[str, Any]:
        return {
            "labels": list(node.labels),
            "properties": dict(node),
        }
