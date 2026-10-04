from medgraph_api.services.clinical_text import (
    clean_clinical_text,
    iter_passages,
    select_relevant_passages,
    split_sentences,
)

DISCHARGE_PDF_TEXT = """SAMPLE Page 1 of 2

Printed by: Snow, Mike on 15-OCT-2015
GENERAL INTERNAL MEDICINE DISCHARGE SUMMARY
Patient Name: Smith, John
Admission Date:  08-Oct-2015
Discharge Date:  14-Oct-2015
Discharge Diagnosis: Pyelonephritis

COURSE WHILE IN HOSPITAL
Relevant Complaint(s) and Concerns:
1. Upon arrival: Patient presented with five days of increased urinary frequency, urgency and
dysuria as well as 48 hours of fever and rigors. He was hypotensive on arrival.
Ensure Primary Care /
Referring Provider
information is correct
Be concise and itemize
descriptions of patient's
initial presentation

SAMPLE Page 2 of 2

Printed by: Snow, Mike on 15-OCT-2015
DISCHARGE PLAN
New Medications:
 Ciprofloxacin 500 mg twice daily for 7 days
 Tamsulosin 0.4mg po QHS
Discontinued Medications:
None
"""


def test_clean_clinical_text_removes_page_furniture_and_margin_notes() -> None:
    cleaned = clean_clinical_text(DISCHARGE_PDF_TEXT)

    assert "Page 1 of 2" not in cleaned
    assert "Printed by" not in cleaned
    assert "Ensure Primary Care" not in cleaned
    assert "initial presentation" not in cleaned
    assert "• Ciprofloxacin 500 mg twice daily for 7 days" in cleaned
    assert "None" in cleaned


def test_clean_clinical_text_rejoins_wrapped_lines() -> None:
    cleaned = clean_clinical_text(DISCHARGE_PDF_TEXT)

    assert (
        "1. Upon arrival: Patient presented with five days of increased urinary frequency, "
        "urgency and dysuria as well as 48 hours of fever and rigors. He was hypotensive on "
        "arrival."
    ) in cleaned.splitlines()
    assert "Admission Date: 08-Oct-2015" in cleaned.splitlines()


def test_clean_clinical_text_keeps_short_capitalized_lists() -> None:
    text = "Problem list:\nHypertension\nDiabetes\nAsthma\nDepression\nObesity\nGout\nAnemia"

    cleaned = clean_clinical_text(text)

    assert cleaned.splitlines()[1:] == [
        "Hypertension",
        "Diabetes",
        "Asthma",
        "Depression",
        "Obesity",
        "Gout",
        "Anemia",
    ]


def test_split_sentences_handles_abbreviations_and_list_numbers() -> None:
    sentences = split_sentences("1. Dear Dr. Jay: Repeat AST in 2 weeks. Referred to urology.")

    assert sentences == ["1. Dear Dr. Jay: Repeat AST in 2 weeks.", "Referred to urology."]


def test_relevant_passages_use_section_headings() -> None:
    passages = iter_passages(clean_clinical_text(DISCHARGE_PDF_TEXT))

    selected = select_relevant_passages(passages, "What new medications was he started on?", 2)

    assert [passage.display_text() for passage in selected] == [
        "New Medications: Ciprofloxacin 500 mg twice daily for 7 days",
        "New Medications: Tamsulosin 0.4mg po QHS",
    ]


def test_relevant_passages_continue_section_from_chunk_metadata() -> None:
    passages = iter_passages(
        "Tamsulosin 0.4mg po QHS",
        initial_section="DISCHARGE PLAN > New Medications",
    )

    selected = select_relevant_passages(passages, "discharge medications", 1)

    assert selected[0].display_text() == "New Medications: Tamsulosin 0.4mg po QHS"


def test_relevant_passages_fall_back_to_first_sentence_per_source() -> None:
    passages = [
        *iter_passages("Chest pain worsened after a dose change.", source_index=0),
        *iter_passages("Follow-up ECG described new ST depression.", source_index=1),
    ]

    selected = select_relevant_passages(passages, "Is the patient deteriorating?", 4)

    assert [passage.source_index for passage in selected] == [0, 1]
