from datetime import UTC, datetime
from uuid import uuid4

from medgraph_api.services.timeline_extraction import BasicTimelineEventExtractionService


def test_timeline_extraction_creates_clinical_events() -> None:
    patient_id = uuid4()
    document_id = uuid4()
    text = (
        "2026-01-14 Patient reports chest discomfort. "
        "Troponin was elevated. "
        "Administrative form scanned."
    )

    events = BasicTimelineEventExtractionService().extract_events(
        patient_id=patient_id,
        source_document_id=document_id,
        text=text,
    )

    assert len(events) == 2
    assert events[0].patient_id == patient_id
    assert events[0].source_document_id == document_id
    assert events[0].occurred_at == datetime(2026, 1, 14, tzinfo=UTC)
    assert events[0].event_type == "symptom"
    assert events[1].event_type == "lab_result"


def test_timeline_extraction_skips_nonclinical_text() -> None:
    events = BasicTimelineEventExtractionService().extract_events(
        patient_id=uuid4(),
        source_document_id=uuid4(),
        text="Insurance card scanned. Registration information updated.",
    )

    assert events == []


def test_timeline_extraction_truncates_long_titles() -> None:
    long_sentence = f"Patient reports pain {'very ' * 50}often."

    events = BasicTimelineEventExtractionService().extract_events(
        patient_id=uuid4(),
        source_document_id=uuid4(),
        text=long_sentence,
    )

    assert len(events) == 1
    assert len(events[0].title) == 120
    assert events[0].title.endswith("...")


def test_timeline_extraction_splits_lines_and_reads_day_month_year_dates() -> None:
    text = (
        "GENERAL INTERNAL MEDICINE DISCHARGE SUMMARY\n"
        "Patient Name: Smith, John\n"
        "Admission Date: 08-Oct-2015\n"
        "Labs\n"
        "7 Creatinine 08-Oct-2015 170 umol/L\n"
        "12 Creatinine 14-Oct-2015 66 umol/L"
    )

    events = BasicTimelineEventExtractionService().extract_events(
        patient_id=uuid4(),
        source_document_id=uuid4(),
        text=text,
    )

    assert [(event.title, event.occurred_at) for event in events] == [
        ("7 Creatinine 08-Oct-2015 170 umol/L", datetime(2015, 10, 8, tzinfo=UTC)),
        ("12 Creatinine 14-Oct-2015 66 umol/L", datetime(2015, 10, 14, tzinfo=UTC)),
    ]
