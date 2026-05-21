import re
from datetime import UTC, datetime
from uuid import UUID

from medgraph_api.schemas.timeline_event import TimelineEventCreate


class BasicTimelineEventExtractionService:
    EVENT_KEYWORDS = {
        "symptom": ("pain", "discomfort", "dyspnea", "shortness of breath", "fatigue", "syncope"),
        "lab_result": ("troponin", "hemoglobin", "creatinine", "glucose", "potassium", "sodium"),
        "ecg": ("ecg", "ekg", "sinus", "st elevation", "st depression", "qrs", "qt"),
        "medication": ("started", "stopped", "dose", "mg", "medication", "metoprolol", "aspirin"),
        "diagnosis": ("diagnosed", "assessment", "impression", "diagnosis"),
        "encounter": ("admitted", "discharged", "follow up", "visit", "consult"),
    }
    DATE_PATTERN = re.compile(r"\b(?P<date>\d{4}-\d{2}-\d{2})\b")

    def extract_events(
        self,
        patient_id: UUID,
        source_document_id: UUID,
        text: str,
    ) -> list[TimelineEventCreate]:
        events: list[TimelineEventCreate] = []
        for sentence in self._split_sentences(text):
            event_type = self._classify_event_type(sentence)
            if event_type is None:
                continue

            events.append(
                TimelineEventCreate(
                    patient_id=patient_id,
                    source_document_id=source_document_id,
                    occurred_at=self._extract_date(sentence),
                    event_type=event_type,
                    title=self._build_title(sentence),
                    description=sentence,
                    evidence_text=sentence,
                    confidence=0.65,
                    event_metadata={"extractor": "basic_keyword_v1"},
                )
            )

        return events

    def _split_sentences(self, text: str) -> list[str]:
        normalized_text = " ".join(text.split())
        sentences = re.split(r"(?<=[.!?])\s+", normalized_text)
        return [sentence.strip() for sentence in sentences if sentence.strip()]

    def _classify_event_type(self, sentence: str) -> str | None:
        normalized_sentence = sentence.lower()
        for event_type, keywords in self.EVENT_KEYWORDS.items():
            if any(keyword in normalized_sentence for keyword in keywords):
                return event_type

        return None

    def _extract_date(self, sentence: str) -> datetime | None:
        match = self.DATE_PATTERN.search(sentence)
        if match is None:
            return None

        return datetime.fromisoformat(match.group("date")).replace(tzinfo=UTC)

    def _build_title(self, sentence: str) -> str:
        title = sentence.strip()
        if len(title) <= 120:
            return title

        return f"{title[:117].rstrip()}..."

