from sqlalchemy.orm import Session

from medgraph_api.models.timeline_event import TimelineEvent
from medgraph_api.schemas.timeline_event import TimelineEventCreate


class TimelineEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_many(self, payloads: list[TimelineEventCreate]) -> list[TimelineEvent]:
        events = [TimelineEvent(**payload.model_dump()) for payload in payloads]
        self.db.add_all(events)
        self.db.commit()

        for event in events:
            self.db.refresh(event)

        return events

