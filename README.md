# MedGraph AI

A multimodal clinical reasoning and patient timeline intelligence system.

## Apps

- `frontend`: Next.js clinical workspace
- `backend`: FastAPI API and ingestion service

## Phase 1

Build the MVP patient timeline app:

1. Upload patient documents.
2. Extract text from records.
3. Generate summaries.
4. Display longitudinal patient timeline events.

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

Start the frontend, backend, and PostgreSQL services:

```bash
docker compose up --build
```
