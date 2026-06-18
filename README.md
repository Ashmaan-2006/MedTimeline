# MedGraph AI

A multimodal clinical reasoning and patient timeline intelligence system.

## Apps

- `frontend`: Next.js clinical workspace
- `backend`: FastAPI API, ingestion service, and Celery worker

## Phase 1

Build the MVP patient timeline app:

1. Upload patient documents.
2. Queue asynchronous document processing.
3. Extract text from records.
4. Generate summaries.
5. Display longitudinal patient timeline events.

## Async Processing Architecture

MedGraph AI processes documents asynchronously so uploads return quickly while CPU or model work
runs in a worker.

```text
Frontend upload form
  -> Next.js API proxy
  -> FastAPI document upload endpoint
  -> PostgreSQL document row with processing_status = queued
  -> RabbitMQ broker
  -> Celery worker
  -> document processing service
     -> file extraction
     -> summary generation
     -> timeline extraction
     -> text chunking
     -> embedding generation
     -> pgvector chunk storage
  -> PostgreSQL document row with processing_status = completed or failed
  -> frontend status polling
```

Document processing lifecycle:

```text
uploaded -> queued -> processing -> completed
                              \-> failed
```

Status meanings:

- `uploaded`: the document row exists but has not been queued yet.
- `queued`: the API has queued a Celery task and stored the task ID.
- `processing`: a worker has started extraction, summary, timeline, chunking, and embedding work.
- `completed`: extracted text, summary, chunks, embeddings, and timeline events are ready.
- `failed`: processing stopped with a safe user-facing error message.

The frontend polls:

```http
GET /patients/{patient_id}/documents/{document_id}/status
```

Reprocessing failed or outdated records:

```http
POST /patients/{patient_id}/documents/{document_id}/reprocess
```

The reprocess endpoint rejects active documents, clears stale error/output state, deletes old chunks
and timeline events, queues a fresh task, and returns the new `celery_task_id`.

## Patient RAG Architecture

MedGraph AI includes a patient-specific retrieval augmented generation flow for asking questions
against uploaded clinical records. The current MVP uses deterministic local embeddings so the
pipeline can run in development without an external model provider.

```text
Clinical document upload
  -> text extraction
  -> text chunking
  -> local embedding generation
  -> document_chunks table with pgvector embeddings
  -> patient-scoped similarity search
  -> citation-aware answer generation
  -> frontend RAG chat panel
```

Key backend components:

- `TextChunkingService`: normalizes extracted text and splits it into overlapping chunks.
- `HashingEmbeddingService`: creates fixed-size deterministic embeddings for each chunk.
- `DocumentChunkRepository`: stores chunks and pgvector embeddings, then retrieves similar chunks.
- `PatientDocumentSimilaritySearchService`: embeds the user question and runs patient-scoped retrieval.
- `PatientRagQueryService`: builds an evidence-grounded answer with inline citation labels.

The RAG endpoint is:

```http
POST /patients/{patient_id}/rag/query
```

Example request:

```json
{
  "question": "Why did this patient's chest pain worsen?",
  "limit": 5,
  "document_id": "optional-document-uuid",
  "created_from": "2026-01-01T00:00:00Z",
  "created_to": "2026-01-31T23:59:59Z"
}
```

Retrieval is always scoped by `patient_id`. Optional filters can narrow results to a single
document or to chunks created within a date range.

Example response:

```json
{
  "patient_id": "patient-uuid",
  "question": "Why did this patient's chest pain worsen?",
  "answer": "Based on the retrieved patient documents: Chest pain worsened after medication change [1].",
  "sources": [
    {
      "citation_label": "[1]",
      "chunk_id": "chunk-uuid",
      "document_id": "document-uuid",
      "patient_id": "patient-uuid",
      "chunk_index": 0,
      "content": "Chest pain worsened after medication change. ECG follow-up was ordered.",
      "embedding_model": "local-hashing-embedding-v1",
      "token_count": 10,
      "chunk_metadata": {
        "char_start": 0,
        "char_end": 68
      },
      "created_at": "2026-01-15T14:30:00Z"
    }
  ]
}
```

The frontend patient profile page exposes this endpoint through the Clinical RAG Chat panel.
Each answer shows cited source snippets so the user can inspect the retrieved evidence.

## Example Clinical Queries

- Why did this patient's symptoms worsen over the last few visits?
- What changed before the abnormal ECG finding?
- Which documents mention chest pain, dizziness, or fatigue?
- Were there medication changes before the latest deterioration?
- Summarize evidence related to troponin elevation.
- What prior notes support the current discharge summary?
- Are there repeated symptoms across uploaded records?
- Which source document best explains the timeline event?

## Development

Copy the example environment file before starting local services:

```bash
cp .env.example .env
```

Start the full asynchronous system:

```bash
docker compose up --build
```

Services:

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- PostgreSQL: `localhost:5432`
- RabbitMQ broker: `localhost:5672`
- RabbitMQ management UI: `http://localhost:15672`

RabbitMQ development credentials:

- Username: `guest`
- Password: `guest`

The worker uses:

```bash
celery -A medgraph_api.core.celery_app:celery_app worker --loglevel=info
```

If you run services manually instead of Docker Compose, start them in this order:

1. PostgreSQL
2. RabbitMQ
3. FastAPI backend
4. Celery worker
5. Next.js frontend

Manual backend commands:

```bash
cd backend
python -m uvicorn medgraph_api.main:app --reload
```

Manual worker command:

```bash
cd backend
celery -A medgraph_api.core.celery_app:celery_app worker --loglevel=info
```

Manual frontend command:

```bash
cd frontend
npm run dev
```

## Troubleshooting

Port already allocated:

- `5432`: another PostgreSQL instance is running. Stop it or change the Compose port mapping.
- `5672` or `15672`: another RabbitMQ instance is running.
- `8000`: another backend server is running.
- `3000`: another frontend server is running.

Worker does not receive tasks:

- Confirm RabbitMQ is healthy in Docker Compose.
- Open `http://localhost:15672` and verify the broker is running.
- Confirm `CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//` in Docker.
- If running locally outside Docker, use a broker URL that points to your local RabbitMQ host.

Documents stay queued:

- Check worker logs with `docker compose logs worker`.
- Confirm the worker command includes `medgraph_api.core.celery_app:celery_app`.
- Confirm `medgraph_api.tasks.document_tasks` is imported by the Celery app.

Documents fail:

- Unsupported file formats fail permanently and are not retried.
- Missing uploaded files fail permanently.
- Corrupted PDFs or unreadable text files fail permanently.
- Temporary infrastructure/model errors retry automatically and store a safe frontend message.

Run backend tests:

```bash
python -m pytest backend/tests
python -m ruff check backend
```

Run frontend checks:

```bash
cd frontend
npm run lint
npm run build
```
