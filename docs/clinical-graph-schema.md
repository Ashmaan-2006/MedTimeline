# Clinical Graph Schema

This document defines the first Neo4j graph model for MedGraph AI. The goal is to keep graph
extraction, retrieval, and future reasoning work consistent as the project grows.

## Modeling Principles

- Use stable IDs from PostgreSQL where available.
- Store source text in chunks, not duplicated across every graph node.
- Every extracted clinical entity should be traceable back to at least one `Chunk`.
- Prefer event-centered relationships for temporal reasoning.
- Keep raw extraction confidence and source metadata on nodes or evidence relationships.
- Do not store protected real patient data in demo data. Use synthetic records.

## Node Types

### Patient

Represents a patient profile.

Required properties:

- `id`: UUID from PostgreSQL patients table
- `medical_record_number`: synthetic or demo MRN
- `created_at`

Optional properties:

- `first_name`
- `last_name`
- `date_of_birth`
- `sex`

### Document

Represents an uploaded clinical document.

Required properties:

- `id`: UUID from PostgreSQL documents table
- `patient_id`
- `filename`
- `processing_status`
- `created_at`

Optional properties:

- `content_type`
- `summary`
- `storage_path`

### Chunk

Represents a text chunk generated from an uploaded document.

Required properties:

- `id`: UUID from PostgreSQL document_chunks table
- `patient_id`
- `document_id`
- `chunk_index`
- `content`
- `created_at`

Optional properties:

- `embedding_model`
- `token_count`
- `char_start`
- `char_end`

### ClinicalEvent

Represents a timeline event derived from records.

Required properties:

- `id`: UUID from PostgreSQL timeline_events table
- `patient_id`
- `event_type`
- `title`
- `created_at`

Optional properties:

- `occurred_at`
- `description`
- `confidence`
- `source_document_id`

### Symptom

Represents a symptom or complaint.

Required properties:

- `name`
- `normalized_name`

Optional properties:

- `severity`
- `onset`
- `status`

### Medication

Represents a medication.

Required properties:

- `name`
- `normalized_name`

Optional properties:

- `dose`
- `route`
- `frequency`
- `status`

### Diagnosis

Represents a diagnosis, impression, or differential item.

Required properties:

- `name`
- `normalized_name`

Optional properties:

- `code_system`
- `code`
- `certainty`
- `status`

### Procedure

Represents a clinical procedure or intervention.

Required properties:

- `name`
- `normalized_name`

Optional properties:

- `performed_at`
- `status`

### LabTest

Represents a lab test type.

Required properties:

- `name`
- `normalized_name`

Optional properties:

- `loinc_code`
- `specimen`

### LabResult

Represents a measured lab result.

Required properties:

- `id`
- `test_name`
- `value`

Optional properties:

- `unit`
- `reference_range`
- `flag`
- `measured_at`

### ImagingStudy

Represents imaging studies such as chest X-ray, CT, MRI, or ultrasound.

Required properties:

- `id`
- `modality`
- `name`

Optional properties:

- `performed_at`
- `impression`
- `body_region`

### ECGFinding

Represents ECG-specific findings.

Required properties:

- `name`
- `normalized_name`

Optional properties:

- `rhythm`
- `rate`
- `interval`
- `lead`
- `severity`

### Provider

Represents a clinician or care team member referenced in records.

Required properties:

- `name`

Optional properties:

- `role`
- `department`
- `organization`

## Relationship Types

### PATIENT_HAS_DOCUMENT

Pattern:

```cypher
(:Patient)-[:PATIENT_HAS_DOCUMENT]->(:Document)
```

Use when a document belongs to a patient.

### DOCUMENT_HAS_CHUNK

Pattern:

```cypher
(:Document)-[:DOCUMENT_HAS_CHUNK]->(:Chunk)
```

Use for chunk retrieval and citation paths.

### CHUNK_MENTIONS_ENTITY

Pattern:

```cypher
(:Chunk)-[:CHUNK_MENTIONS_ENTITY {confidence, extractor}]->(:Symptom|:Medication|:Diagnosis|:Procedure|:LabTest|:LabResult|:ImagingStudy|:ECGFinding|:Provider)
```

Use when an entity is mentioned in chunk text.

### PATIENT_HAS_EVENT

Pattern:

```cypher
(:Patient)-[:PATIENT_HAS_EVENT]->(:ClinicalEvent)
```

Use for patient timeline traversal.

### EVENT_MENTIONS_SYMPTOM

Pattern:

```cypher
(:ClinicalEvent)-[:EVENT_MENTIONS_SYMPTOM {confidence}]->(:Symptom)
```

Use when an event discusses a symptom.

### EVENT_MENTIONS_MEDICATION

Pattern:

```cypher
(:ClinicalEvent)-[:EVENT_MENTIONS_MEDICATION {confidence}]->(:Medication)
```

Use when an event discusses a medication.

### EVENT_HAS_LAB_RESULT

Pattern:

```cypher
(:ClinicalEvent)-[:EVENT_HAS_LAB_RESULT]->(:LabResult)
```

Use when a lab result is tied to a timeline event.

### EVENT_ASSOCIATED_WITH_DIAGNOSIS

Pattern:

```cypher
(:ClinicalEvent)-[:EVENT_ASSOCIATED_WITH_DIAGNOSIS {confidence}]->(:Diagnosis)
```

Use when a diagnosis is assessed, confirmed, ruled out, or discussed at an event.

### MEDICATION_STARTED_AT_EVENT

Pattern:

```cypher
(:Medication)-[:MEDICATION_STARTED_AT_EVENT]->(:ClinicalEvent)
```

Use when a medication begins at a documented event.

### MEDICATION_STOPPED_AT_EVENT

Pattern:

```cypher
(:Medication)-[:MEDICATION_STOPPED_AT_EVENT]->(:ClinicalEvent)
```

Use when a medication is discontinued at a documented event.

### SYMPTOM_WORSENED_AFTER

Pattern:

```cypher
(:Symptom)-[:SYMPTOM_WORSENED_AFTER {confidence, rationale}]->(:ClinicalEvent)
```

Use when evidence suggests symptom worsening after a prior event, such as a medication change,
procedure, or abnormal finding.

### FINDING_SUPPORTS_DIAGNOSIS

Pattern:

```cypher
(:LabResult|:ImagingStudy|:ECGFinding)-[:FINDING_SUPPORTS_DIAGNOSIS {confidence}]->(:Diagnosis)
```

Use when an objective finding supports a diagnosis.

### ENTITY_EVIDENCED_BY_CHUNK

Pattern:

```cypher
(:Symptom|:Medication|:Diagnosis|:Procedure|:LabTest|:LabResult|:ImagingStudy|:ECGFinding|:Provider|:ClinicalEvent)-[:ENTITY_EVIDENCED_BY_CHUNK {quote, confidence}]->(:Chunk)
```

Use for citation and grounding. Keep `quote` short and source-local.

## Suggested Constraints

```cypher
CREATE CONSTRAINT patient_id IF NOT EXISTS FOR (p:Patient) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT clinical_event_id IF NOT EXISTS FOR (e:ClinicalEvent) REQUIRE e.id IS UNIQUE;
CREATE CONSTRAINT lab_result_id IF NOT EXISTS FOR (r:LabResult) REQUIRE r.id IS UNIQUE;
CREATE CONSTRAINT imaging_study_id IF NOT EXISTS FOR (i:ImagingStudy) REQUIRE i.id IS UNIQUE;
```

Entity nodes that do not have upstream UUIDs should use normalized keys:

```cypher
CREATE CONSTRAINT symptom_normalized_name IF NOT EXISTS
FOR (s:Symptom) REQUIRE s.normalized_name IS UNIQUE;

CREATE CONSTRAINT medication_normalized_name IF NOT EXISTS
FOR (m:Medication) REQUIRE m.normalized_name IS UNIQUE;

CREATE CONSTRAINT diagnosis_normalized_name IF NOT EXISTS
FOR (d:Diagnosis) REQUIRE d.normalized_name IS UNIQUE;
```

## Example Subgraph

```cypher
(:Patient {id: "patient-uuid"})
  -[:PATIENT_HAS_DOCUMENT]->
(:Document {id: "document-uuid", filename: "discharge-summary.pdf"})
  -[:DOCUMENT_HAS_CHUNK]->
(:Chunk {id: "chunk-uuid", chunk_index: 0})
  -[:CHUNK_MENTIONS_ENTITY]->
(:Medication {normalized_name: "metoprolol"})

(:Patient {id: "patient-uuid"})
  -[:PATIENT_HAS_EVENT]->
(:ClinicalEvent {id: "event-uuid", event_type: "medication"})
  -[:EVENT_MENTIONS_MEDICATION]->
(:Medication {normalized_name: "metoprolol"})

(:Medication {normalized_name: "metoprolol"})
  -[:MEDICATION_STARTED_AT_EVENT]->
(:ClinicalEvent {id: "event-uuid"})
```

## Extraction Rules

- Create or merge `Patient`, `Document`, and `Chunk` nodes from existing database records.
- Create `ClinicalEvent` nodes from timeline event records.
- Extract entity nodes from chunks and event descriptions.
- Always create evidence links from extracted entities back to chunks.
- Use `occurred_at` on `ClinicalEvent` for temporal traversal when available.
- Use relationship properties for confidence, extractor name, and rationale.
- Do not infer causality unless evidence explicitly supports it; use lower confidence when inferred.

## Open Questions

- Whether medication nodes should be patient-scoped or globally normalized.
- Whether diagnoses should be globally normalized by code when ICD/SNOMED mapping is added.
- How to represent negation such as "no chest pain" or "MI ruled out".
- How to version graph extraction when documents are reprocessed.
