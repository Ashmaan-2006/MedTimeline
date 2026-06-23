import re

from medgraph_api.services.model_fallback import ModelFallbackRunner


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


class FallbackAISummaryService:
    def __init__(
        self,
        primary: BasicAISummaryService,
        fallback: BasicAISummaryService,
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
