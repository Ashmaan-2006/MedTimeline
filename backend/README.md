# MedGraph AI Backend

FastAPI service for patient records, asynchronous document processing, timeline extraction, hybrid RAG, and Neo4j-backed clinical graph retrieval.

## Local Services

Run the full stack from the repository root:

```powershell
docker compose up --build
```

Service URLs:

| Service | URL | Notes |
| --- | --- | --- |
| Frontend | `http://localhost:3001` | Next.js clinical workspace |
| Backend API | `http://localhost:8001` | FastAPI, proxied into frontend routes |
| RabbitMQ UI | `http://localhost:15672` | Username `guest`, password `guest` |
| Neo4j Browser | `http://localhost:7474` | Username `neo4j`, password from `.env` |

The backend runs inside Docker on port `8000` and is exposed locally as `8001` to avoid common host port conflicts.

## Environment

Expected local variables:

```env
DATABASE_URL=postgresql+psycopg://medgraph:medgraph@postgres:5432/medgraph
CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
CELERY_RESULT_BACKEND=rpc://
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password
```

Neo4j is configured in `docker-compose.yml` as:

```yaml
neo4j:
  image: neo4j:5-community
  ports:
    - "7474:7474"
    - "7687:7687"
```

## Document Processing Lifecycle

Upload flow:

```text
FastAPI upload endpoint
  -> store file metadata in Postgres
  -> queue Celery task through RabbitMQ
  -> worker extracts text
  -> creates summary
  -> chunks text
  -> creates embeddings in pgvector
  -> extracts timeline events
  -> extracts clinical entities
  -> extracts clinical relationships
  -> writes Neo4j graph nodes and relationships
```

Processing status values:

- `uploaded`
- `queued`
- `processing`
- `completed`
- `failed`

Reprocessing flow:

```text
POST /patients/{patient_id}/documents/{document_id}/reprocess
  -> reject active queued/processing documents
  -> delete old Postgres chunks
  -> delete old timeline events
  -> delete old Neo4j document subgraph
  -> preserve Patient node
  -> queue fresh Celery processing task
```

The graph cleanup uses a document-scoped deletion. It removes the old `Document`, old `Chunk` nodes, and relationships with old `source_chunk_id` values, then rebuilds from current document output.

## Clinical Graph Schema

The complete graph schema is documented in:

```text
docs/clinical-graph-schema.md
```

Core nodes:

- `Patient`
- `Document`
- `Chunk`
- `ClinicalEvent`
- `Symptom`
- `Medication`
- `Diagnosis`
- `Procedure`
- `LabTest`
- `ECGFinding`

Core relationships:

- `(:Patient)-[:PATIENT_HAS_DOCUMENT]->(:Document)`
- `(:Document)-[:DOCUMENT_HAS_CHUNK]->(:Chunk)`
- `(:Chunk)-[:CHUNK_MENTIONS_ENTITY]->(:Symptom|Medication|Diagnosis|...)`
- `(:Entity)-[:ENTITY_EVIDENCED_BY_CHUNK]->(:Chunk)`
- `(:Medication)-[:WORSENED_AFTER|ASSOCIATED_WITH|STARTED_AT]->(:Symptom|ClinicalEvent)`

Graph writes use `MERGE` for idempotency where possible. Reprocessing additionally clears the document-specific subgraph before rebuilding.

## Example Cypher Queries

Open Neo4j Browser at `http://localhost:7474`.

List documents for a patient:

```cypher
MATCH (p:Patient {id: "PATIENT_UUID"})-[:PATIENT_HAS_DOCUMENT]->(d:Document)
RETURN p.id, d.id, d.filename, d.processing_status
ORDER BY d.created_at DESC;
```

Show chunks and mentioned entities:

```cypher
MATCH (:Patient {id: "PATIENT_UUID"})-[:PATIENT_HAS_DOCUMENT]->(:Document)
  -[:DOCUMENT_HAS_CHUNK]->(c:Chunk)-[:CHUNK_MENTIONS_ENTITY]->(e)
RETURN c.chunk_index, labels(e)[0] AS entity_type, e.normalized_name, c.content
ORDER BY c.chunk_index;
```

Inspect extracted medication-symptom relationships:

```cypher
MATCH (m:Medication)-[r]->(s:Symptom)
RETURN m.normalized_name, type(r), s.normalized_name, r.evidence, r.confidence
ORDER BY r.confidence DESC;
```

Find evidence chunks for an entity:

```cypher
MATCH (e)-[r:ENTITY_EVIDENCED_BY_CHUNK]->(c:Chunk)<-[:DOCUMENT_HAS_CHUNK]-(d:Document)
WHERE e.normalized_name = "metoprolol"
RETURN labels(e)[0], e.normalized_name, d.filename, c.chunk_index, r.evidence, c.content;
```

Find paths between two entities:

```cypher
MATCH (source {normalized_name: "metoprolol"})
MATCH (target {normalized_name: "shortness of breath"})
MATCH path = shortestPath((source)-[*1..4]-(target))
RETURN path;
```

## Graph API

Patient-scoped graph endpoints:

```text
GET /patients/{patient_id}/graph/summary
GET /patients/{patient_id}/graph/entities
GET /patients/{patient_id}/graph/relationships
GET /patients/{patient_id}/graph/entity/{entity_name}/evidence
GET /patients/{patient_id}/graph/path?source=...&target=...
```

These endpoints power the frontend `Clinical Graph` tab.

## Graph RAG Architecture

Hybrid RAG flow:

```text
Question
  -> pgvector similarity search
  -> Neo4j relationship retrieval
  -> merge chunk evidence + graph evidence
  -> generate answer with document citations and graph citations
```

Example question:

```text
Did symptoms worsen after the medication change?
```

The answer context can include:

- Chunks mentioning symptoms and medication changes
- Graph relationships such as `Medication -[:WORSENED_AFTER]-> Symptom`
- Evidence snippets from `ENTITY_EVIDENCED_BY_CHUNK`
- Timeline events exposed separately through patient timeline APIs

RAG responses include:

- `sources`: document chunk citations like `[1]`
- `graph_evidence`: graph relationship citations like `[G1]`

## LangSmith Tracing

LangSmith tracing is disabled by default. To inspect clinical reasoning runs step by step, set:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_PROJECT=medgraph-ai
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

The clinical reasoning workflow traces these node names:

- `clinical_agent.intent_classifier`
- `clinical_agent.evidence_planner`
- `clinical_agent.vector_retriever`
- `clinical_agent.graph_retriever`
- `clinical_agent.timeline_reasoner`
- `clinical_agent.contradiction_checker`
- `clinical_agent.risk_flagger`
- `clinical_agent.answer_generator`

The `post_retrieval` routing node is also traced so branching decisions can be inspected around retrieval fan-out and merge behavior.

## OpenTelemetry

OpenTelemetry instrumentation is disabled by default. To emit system-level spans, set:

```env
OTEL_ENABLED=true
OTEL_SERVICE_NAME=medgraph-ai
OTEL_CONSOLE_EXPORTER=true
```

Instrumented boundaries include:

- FastAPI requests, with method, route, status code, latency, and failures
- Celery document-processing tasks, with retry count, task duration, and failures
- pgvector similarity search, with patient ID, limit, query duration, and failures
- Neo4j graph queries, with query duration and parameter count
- RAG answer generation and graph retrieval assembly
- Clinical entity and relationship extraction calls treated as LLM spans

The default exporter is the console exporter because this project runs locally through Docker. Production deployments can replace this with an OTLP exporter without changing the span names.

## Model Fallbacks

Model-backed workflow steps use a timeout-aware fallback wrapper. If a primary model call times out or raises a provider availability error, the workflow falls back to a cheaper or deterministic backup path and returns conservative output.

Fallback-covered steps:

- grounded answer generation
- document summarization
- clinical entity extraction
- clinical relationship extraction

Fallback answers are marked low confidence and include a warning in the answer limitations. Fallback summaries append a review warning. This keeps document processing and clinical reasoning from crashing when one model provider is slow or unavailable.

## Test Coverage

Run backend tests:

```powershell
python -m pytest backend\tests
python -m ruff check backend
```

Graph pipeline coverage includes:

| Area | Test file |
| --- | --- |
| Neo4j driver/session/health query | `backend/tests/test_neo4j_core.py` |
| Patient/document/chunk graph sync | `backend/tests/test_clinical_graph_sync_service.py` |
| Entity extraction validation | `backend/tests/test_entity_extraction_service.py` |
| Relationship extraction validation | `backend/tests/test_relationship_extraction_service.py` |
| Idempotent graph writes with `MERGE` | `backend/tests/test_clinical_graph_repository.py` |
| Document reprocessing graph cleanup | `backend/tests/test_document_upload_api.py` |
| Graph build during document processing | `backend/tests/test_document_processing_service.py` |
| Hybrid vector + graph RAG | `backend/tests/test_rag_service.py` |
| Graph API relationship responses | `backend/tests/test_graph_api.py` |

## Known Limitations

- The default entity and relationship extraction uses a local deterministic extractor for demo reliability. It is intentionally conservative and should be replaced with a provider-backed structured-output LLM for richer clinical extraction.
- Entity normalization is string-based. It does not yet map ICD, SNOMED, RxNorm, LOINC, or UMLS identifiers.
- Medication dose, route, frequency, negation, and temporal onset are not fully modeled yet.
- Graph relationships are evidence-focused and should not be treated as clinical truth without human review.
- Hybrid RAG uses lightweight answer synthesis. It cites retrieved context but does not yet use a production LLM with full prompt tracing.
- Timeline events are stored in Postgres and displayed in the frontend; full event-to-entity graph linking is still an extension point.
- This project is for engineering demonstration only and is not a medical device or clinical decision support system.
