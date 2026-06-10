from sqlalchemy import text

from medgraph_api.db.base import Base
from medgraph_api.db.session import engine


def initialize_database() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                ALTER TABLE documents
                    ADD COLUMN IF NOT EXISTS processing_status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
                    ADD COLUMN IF NOT EXISTS processing_error TEXT,
                    ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ,
                    ADD COLUMN IF NOT EXISTS processing_completed_at TIMESTAMPTZ,
                    ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR(255),
                    ADD COLUMN IF NOT EXISTS processing_attempts INTEGER NOT NULL DEFAULT 0
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_documents_processing_status
                    ON documents (processing_status)
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_documents_celery_task_id
                    ON documents (celery_task_id)
                """
            )
        )
