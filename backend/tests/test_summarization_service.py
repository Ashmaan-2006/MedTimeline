from medgraph_api.services.summarization import (
    BasicAISummaryService,
    ClinicalDocumentSummaryService,
)


def test_basic_ai_summary_uses_first_clinical_sentences() -> None:
    text = (
        "Patient reports worsening chest discomfort. "
        "Troponin was mildly elevated. "
        "ECG showed nonspecific ST changes. "
        "Follow up was recommended."
    )

    summary = BasicAISummaryService(max_sentences=2).summarize(text)

    assert summary == "Patient reports worsening chest discomfort. Troponin was mildly elevated."


def test_basic_ai_summary_handles_empty_text() -> None:
    summary = BasicAISummaryService().summarize("   ")

    assert summary == "No extractable clinical text was found."


def test_basic_ai_summary_truncates_long_text() -> None:
    text = "Patient has a very long clinical note without much punctuation"

    summary = BasicAISummaryService(max_chars=20).summarize(text)

    assert summary == "Patient has a very..."


def test_clinical_document_summary_extracts_sections_from_discharge_summary() -> None:
    text = "\n".join(
        [
            "SAMPLE Page 1 of 1",
            "GENERAL INTERNAL MEDICINE DISCHARGE SUMMARY",
            "Admission Date: 08-Oct-2015",
            "Discharge Date: 14-Oct-2015",
            "Discharge Diagnosis: Pyelonephritis",
            "Relevant Complaint(s) and Concerns:",
            "1. Upon arrival: Patient presented with fever and dysuria. He was hypotensive.",
            "Summary Course in Hospital (Issues Addressed):",
            "2. Fever and urinary symptoms: Pyelonephritis was diagnosed. IV fluids were given.",
            "3. Elevated creatinine. This was related to hypoperfusion and improved.",
            "Allergies:",
            "- Latex",
            "Unchanged Medications:",
            "- Ramipril 10mg po daily",
            "Adjusted Medications:",
            "None",
            "New Medications:",
            "- Tamsulosin 0.4mg po QHS",
            "Follow-Up Plan Recommended for Receiving Providers:",
            "1. Please repeat his AST and ALT in two weeks. He is doing well.",
        ]
    )

    summary = ClinicalDocumentSummaryService().summarize(text)

    assert summary.splitlines() == [
        "General Internal Medicine Discharge Summary",
        "Diagnosis: Pyelonephritis",
        "Admission: 08-Oct-2015 to 14-Oct-2015",
        "Presentation: Patient presented with fever and dysuria.",
        "Hospital course:",
        "- Fever and urinary symptoms: Pyelonephritis was diagnosed.",
        "- Elevated creatinine: This was related to hypoperfusion and improved.",
        "Allergies: Latex",
        "New medications: Tamsulosin 0.4mg po QHS",
        "Continued medications: Ramipril 10mg po daily",
        "Follow-up:",
        "- Please repeat his AST and ALT in two weeks.",
    ]


def test_clinical_document_summary_falls_back_for_unstructured_notes() -> None:
    text = "Patient reports chest pain. Troponin was negative. ECG was ordered. Plan to recheck."

    summary = ClinicalDocumentSummaryService().summarize(text)

    assert summary == "Patient reports chest pain. Troponin was negative. ECG was ordered."
