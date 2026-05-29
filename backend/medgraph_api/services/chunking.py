from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    content: str
    token_count: int
    metadata: dict[str, int]


class TextChunkingService:
    def __init__(self, max_chars: int = 1200, overlap_chars: int = 150) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be greater than 0.")
        if overlap_chars < 0:
            raise ValueError("overlap_chars must be greater than or equal to 0.")
        if overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be smaller than max_chars.")

        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk_text(self, text: str) -> list[TextChunk]:
        normalized_text = self._normalize_text(text)
        if not normalized_text:
            return []

        chunks: list[TextChunk] = []
        start = 0

        while start < len(normalized_text):
            end = self._find_chunk_end(normalized_text, start)
            content = normalized_text[start:end].strip()

            if content:
                chunks.append(
                    TextChunk(
                        chunk_index=len(chunks),
                        content=content,
                        token_count=self._estimate_token_count(content),
                        metadata={
                            "char_start": start,
                            "char_end": end,
                        },
                    )
                )

            if end == len(normalized_text):
                break

            start = self._find_next_chunk_start(normalized_text, end)

        return chunks

    def _normalize_text(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines()]
        paragraphs = [line for line in lines if line]
        return "\n".join(paragraphs)

    def _find_chunk_end(self, text: str, start: int) -> int:
        hard_end = min(start + self.max_chars, len(text))
        if hard_end == len(text):
            return hard_end

        paragraph_break = text.rfind("\n", start, hard_end)
        if paragraph_break > start:
            return paragraph_break

        sentence_breaks = [text.rfind(separator, start, hard_end) for separator in (". ", "! ", "? ")]
        sentence_break = max(sentence_breaks)
        if sentence_break > start:
            return sentence_break + 1

        word_break = text.rfind(" ", start, hard_end)
        if word_break > start:
            return word_break

        return hard_end

    def _find_next_chunk_start(self, text: str, previous_end: int) -> int:
        start = max(0, previous_end - self.overlap_chars)
        if start == 0:
            return start
        if text[start - 1].isspace():
            return start

        while start < len(text) and not text[start].isspace():
            start += 1
        while start < len(text) and text[start].isspace():
            start += 1

        return start

    def _estimate_token_count(self, text: str) -> int:
        return len(text.split())
