import re
from datetime import UTC, datetime
from uuid import UUID

from medgraph_api.schemas.timeline_event import TimelineEventCreate
from medgraph_api.services.clinical_text import is_heading, split_sentences, strip_list_marker


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
    DAY_MONTH_YEAR_PATTERN = re.compile(
        r"\b(\d{1,2})-(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*-(\d{4})\b",
        re.IGNORECASE,
    )

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
        # Split per line so header fields and list items do not merge into one giant "event".
        sentences = []
        for line in text.splitlines():
            if not line.strip() or is_heading(line):
                continue
            sentences.extend(split_sentences(strip_list_marker(line)))
        return sentences

    def _classify_event_type(self, sentence: str) -> str | None:
        normalized_sentence = sentence.lower()
        for event_type, keywords in self.EVENT_KEYWORDS.items():
            if any(keyword in normalized_sentence for keyword in keywords):
                return event_type

        return None

    def _extract_date(self, sentence: str) -> datetime | None:
        match = self.DATE_PATTERN.search(sentence)
        if match is not None:
            return datetime.fromisoformat(match.group("date")).replace(tzinfo=UTC)

        # Discharge summaries and lab tables write dates as 08-Oct-2015.
        day_month_year = self.DAY_MONTH_YEAR_PATTERN.search(sentence)
        if day_month_year is None:
            return None
        day, month, year = day_month_year.groups()
        parsed = datetime.strptime(f"{day}-{month.title()}-{year}", "%d-%b-%Y")
        return parsed.replace(tzinfo=UTC)

    def _build_title(self, sentence: str) -> str:
        title = sentence.strip()
        if len(title) <= 120:
            return title

        return f"{title[:117].rstrip()}..."

