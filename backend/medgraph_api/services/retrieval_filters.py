from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class RetrievalFilters:
    document_id: UUID | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
