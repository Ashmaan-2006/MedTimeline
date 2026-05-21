import re


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

        return f"{summary[: self.max_chars].rstrip()}..."

    def _split_sentences(self, text: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [sentence.strip() for sentence in sentences if sentence.strip()]
