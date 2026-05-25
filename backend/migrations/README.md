# Database Migrations

SQL migrations for MedGraph AI.

Apply the pgvector document chunk migration against a running database:

```bash
psql "$DATABASE_URL" -f backend/migrations/0001_add_document_chunks_pgvector.sql
```

The current MVP also initializes tables at application startup for local development.

