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

## Development

Copy the example environment file before starting local services:

```bash
cp .env.example .env
```

Start the frontend, backend, and PostgreSQL services:

```bash
docker compose up --build
```
