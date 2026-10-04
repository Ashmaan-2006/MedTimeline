import re
from typing import Protocol

from medgraph_api.services.clinical_text import (
    ClinicalSection,
    clean_clinical_text,
    is_empty_value,
    is_list_item,
    parse_key_values,
    parse_sections,
    split_sentences,
    strip_list_marker,
)
from medgraph_api.services.model_fallback import ModelFallbackRunner
from medgraph_api.services.text_snippets import build_source_snippet

TITLE_KEYWORDS = ("SUMMARY", "NOTE", "REPORT", "CONSULT", "LETTER", "RECORD", "ASSESSMENT")
DIAGNOSIS_FIELDS = (
    "discharge diagnosis",
    "final diagnosis",
    "primary diagnosis",
    "diagnosis",
    "impression",
    "assessment",
)
PRESENTATION_HEADINGS = ("complaint", "presentation", "present illness", "hpi", "reason for")
PRESENTATION_FIELDS = ("chief complaint", "reason for admission", "reason for visit")
COURSE_HEADINGS = ("course", "issues addressed", "hospital stay")
CONDITION_HEADINGS = (
    ("Background conditions", ("pre-existing", "past medical history", "medical history", "pmh")),
    ("Developed during stay", ("developed", "complication")),
)
MEDICATION_HEADINGS = (
    ("New medications", ("new medication", "started medication")),
    ("Changed medications", ("adjusted", "changed medication", "modified")),
    ("Stopped medications", ("discontinued", "stopped")),
    ("Continued medications", ("unchanged", "continued", "continue")),
)
FOLLOW_UP_HEADING_PRIORITY = (("plan", "recommend"), ("referral",), ("follow",), ("instruction",))
FOLLOW_UP_ACTION_PATTERN = re.compile(
    r"\b(repeat|refer|follow[- ]?up|arrange|appointment|recheck|monitor|schedul)",
    re.IGNORECASE,
)
TOPIC_PREFIX_PATTERN = re.compile(r"^[A-Z][^:.]{1,40}:\s+(?=\S)")
MAX_LINE_CHARS = 240


class SummaryService(Protocol):
    def summarize(self, text: str) -> str:
        pass


class BasicAISummaryService:
    def __init__(self, max_sentences: int = 3, max_chars: int = 600) -> None:
        self.max_sentences = max_sentences
        self.max_chars = max_chars

    def summarize(self, text: str) -> str:
        normalized_text = " ".join(text.split())
        if not normalized_text:
            return "No extractable clinical text was found."

        sentences = self._split_sentences(normalized_text)
        summary = " ".join(sentences[: self.max_sentences])

        if len(summary) <= self.max_chars:
            return summary

        truncated = summary[: self.max_chars]
        word_boundary = truncated.rfind(" ")
        if word_boundary > self.max_chars // 2:
            truncated = truncated[:word_boundary]
        return f"{truncated.rstrip(' ,;:')}..."

    def _split_sentences(self, text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [sentence.strip() for sentence in sentences if sentence.strip()]


class ClinicalDocumentSummaryService:
    """Builds a scannable, sectioned summary from structured clinical documents.

    Discharge summaries, consult notes, and similar records use labelled fields and section
    headings. Pulling the diagnosis, course, medications, and follow-up out of those sections
    reads far better than the first few sentences, which are usually header boilerplate.
    Unstructured notes fall back to the sentence-based summary.
    """

    def __init__(
        self,
        fallback: BasicAISummaryService | None = None,
        max_list_items: int = 4,
    ) -> None:
        self.fallback = fallback or BasicAISummaryService()
        self.max_list_items = max_list_items

    def summarize(self, text: str) -> str:
        cleaned_text = clean_clinical_text(text)
        if not cleaned_text:
            return "No extractable clinical text was found."

        sections = parse_sections(cleaned_text)
        fields = parse_key_values(cleaned_text)
        entries = [
            self._labelled("Diagnosis", self._diagnosis(fields, sections)),
            self._labelled("Admission", self._stay_dates(fields)),
            self._labelled("Presentation", self._presentation(fields, sections)),
            self._bulleted("Hospital course", self._course(sections)),
            *[
                self._labelled(label, "; ".join(self._section_items(sections, keywords)))
                for label, keywords in CONDITION_HEADINGS
            ],
            self._labelled("Allergies", self._allergies(fields, sections)),
            *self._medications(sections),
            self._bulleted("Follow-up", self._follow_up(sections)),
        ]
        entries = [entry for entry in entries if entry]
        if len(entries) < 2:
            return self.fallback.summarize(cleaned_text)

        title = self._title(sections)
        return "\n".join([title, *entries] if title else entries)

    def _title(self, sections: list[ClinicalSection]) -> str | None:
        for section in sections[:3]:
            heading = section.heading or ""
            if heading.isupper() and any(keyword in heading for keyword in TITLE_KEYWORDS):
                return " ".join(word.capitalize() for word in heading.split())
        return None

    def _diagnosis(self, fields: dict[str, str], sections: list[ClinicalSection]) -> str:
        value = _first_field(fields, DIAGNOSIS_FIELDS)
        if value:
            return value
        return "; ".join(self._section_items(sections, ("diagnos", "impression", "assessment")))

    def _stay_dates(self, fields: dict[str, str]) -> str:
        admitted = _first_field(fields, ("admission date", "date of admission", "admit date"))
        discharged = _first_field(fields, ("discharge date", "date of discharge"))
        if admitted and discharged:
            return f"{admitted} to {discharged}"
        return admitted

    def _presentation(self, fields: dict[str, str], sections: list[ClinicalSection]) -> str:
        for section in _matching_sections(sections, PRESENTATION_HEADINGS):
            for line in section.lines:
                sentences = split_sentences(strip_list_marker(line))
                if sentences:
                    return TOPIC_PREFIX_PATTERN.sub("", sentences[0])
        return _first_field(fields, PRESENTATION_FIELDS)

    def _course(self, sections: list[ClinicalSection]) -> list[str]:
        items: list[str] = []
        for section in _matching_sections(sections, COURSE_HEADINGS):
            numbered_lines = [line for line in section.lines if is_list_item(line)]
            for line in numbered_lines or section.lines[:1]:
                sentences = split_sentences(strip_list_marker(line))
                if not sentences:
                    continue
                first = sentences[0]
                # "Elevated liver enzymes and creatinine." is a topic; pair it with its finding.
                if ":" not in first and len(first.split()) <= 8 and len(sentences) > 1:
                    first = f"{first.rstrip('.')}: {sentences[1]}"
                items.append(first)
        return items[: self.max_list_items]

    def _allergies(self, fields: dict[str, str], sections: list[ClinicalSection]) -> str:
        items = self._section_items(sections, ("allerg",))
        if items:
            return "; ".join(items)
        return _first_field(fields, ("allergies", "allergy"))

    def _medications(self, sections: list[ClinicalSection]) -> list[str]:
        entries = []
        matched_any = False
        for label, keywords in MEDICATION_HEADINGS:
            matching = _matching_sections(sections, keywords)
            matched_any = matched_any or bool(matching)
            items = [item for section in matching for item in _section_list(section)]
            entries.append(self._labelled(label, "; ".join(items[:6])))
        if not matched_any:
            items = self._section_items(sections, ("medication",))
            entries.append(self._labelled("Medications", "; ".join(items[:6])))
        return entries

    def _follow_up(self, sections: list[ClinicalSection]) -> list[str]:
        candidates: list[tuple[int, int, str]] = []
        for position, section in enumerate(sections):
            heading = (section.heading or "").lower()
            priority = next(
                (
                    rank
                    for rank, keywords in enumerate(FOLLOW_UP_HEADING_PRIORITY)
                    if any(keyword in heading for keyword in keywords)
                ),
                None,
            )
            if priority is None:
                continue
            for line in section.lines:
                for sentence in split_sentences(strip_list_marker(line)):
                    if FOLLOW_UP_ACTION_PATTERN.search(sentence):
                        candidates.append((priority, position, sentence))
        candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
        follow_up: list[str] = []
        for _, _, sentence in candidates:
            if sentence not in follow_up:
                follow_up.append(sentence)
        return follow_up[: min(3, self.max_list_items)]

    def _section_items(
        self,
        sections: list[ClinicalSection],
        keywords: tuple[str, ...],
    ) -> list[str]:
        matching = _matching_sections(sections, keywords)
        return [item for section in matching for item in _section_list(section)]

    @staticmethod
    def _labelled(label: str, value: str) -> str:
        value = value.strip()
        if not value or is_empty_value(value):
            return ""
        return f"{label}: {build_source_snippet(value, max_length=MAX_LINE_CHARS)}"

    @staticmethod
    def _bulleted(label: str, items: list[str]) -> str:
        if not items:
            return ""
        bullets = [f"- {build_source_snippet(item, max_length=MAX_LINE_CHARS)}" for item in items]
        return "\n".join([f"{label}:", *bullets])


def _first_field(fields: dict[str, str], labels: tuple[str, ...]) -> str:
    for wanted in labels:
        for label, value in fields.items():
            if wanted in label and not is_empty_value(value):
                return value
    return ""


def _matching_sections(
    sections: list[ClinicalSection],
    keywords: tuple[str, ...],
) -> list[ClinicalSection]:
    # Word-start matching so "changed" does not match "Unchanged Medications".
    patterns = [re.compile(rf"\b{re.escape(keyword)}") for keyword in keywords]
    return [
        section
        for section in sections
        if section.heading and any(pattern.search(section.heading.lower()) for pattern in patterns)
    ]


def _section_list(section: ClinicalSection) -> list[str]:
    items = [strip_list_marker(line) for line in section.lines]
    return [item for item in items if item and not is_empty_value(item)]


class FallbackAISummaryService:
    def __init__(
        self,
        primary: SummaryService,
        fallback: SummaryService,
        timeout_seconds: int,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.runner = ModelFallbackRunner(timeout_seconds)

    def summarize(self, text: str) -> str:
        result = self.runner.run(
            primary=lambda: self.primary.summarize(text),
            fallback=lambda: self.fallback.summarize(text),
            operation_name="summarization",
        )
        if not result.used_fallback:
            return result.output
        return f"{result.output} Fallback summary used; review with lower confidence."
