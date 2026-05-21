from medgraph_api.services.summarization import BasicAISummaryService


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

    assert summary == "Patient has a very l..."
