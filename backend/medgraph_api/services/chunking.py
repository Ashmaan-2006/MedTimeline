from dataclasses import dataclass

from medgraph_api.services.clinical_text import section_path_at


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    content: str
    token_count: int
    metadata: dict[str, int | str]


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
                metadata: dict[str, int | str] = {"char_start": start, "char_end": end}
                # Chunks that begin mid-section keep their heading for retrieval and display.
                section = section_path_at(normalized_text, start)
                if section:
                    metadata["section"] = section
                chunks.append(
                    TextChunk(
                        chunk_index=len(chunks),
                        content=content,
                        token_count=self._estimate_token_count(content),
                        metadata=metadata,
                    )
                )

            if end == len(normalized_text):
                break

            next_start = self._find_next_chunk_start(normalized_text, end)
            # Always make forward progress so pathological text cannot loop forever.
            start = next_start if start < next_start <= end else end

        return chunks

    def _normalize_text(self, text: str) -> str:
        lines = [line.strip() for line in text.splitlines()]
        paragraphs = [line for line in lines if line]
        return "\n".join(paragraphs)

    def _find_chunk_end(self, text: str, start: int) -> int:
        hard_end = min(start + self.max_chars, len(text))
        if hard_end == len(text):
            return hard_end

        # Breaks inside the overlap window would make the next chunk start before this one.
        min_break = start + self.overlap_chars + 1

        paragraph_break = text.rfind("\n", min_break, hard_end)
        if paragraph_break >= min_break:
            return paragraph_break

        sentence_breaks = [
            text.rfind(separator, min_break, hard_end) for separator in (". ", "! ", "? ")
        ]
        sentence_break = max(sentence_breaks)
        if sentence_break >= min_break:
            return sentence_break + 1

        word_break = text.rfind(" ", min_break, hard_end)
        if word_break >= min_break:
            return word_break

        return hard_end

    def _find_next_chunk_start(self, text: str, previous_end: int) -> int:
        window_start = max(0, previous_end - self.overlap_chars)

        # Start the overlap on a line or sentence boundary so chunks never open mid-sentence.
        boundary = self._first_boundary_in(text, window_start, previous_end)
        if boundary is not None:
            return self._skip_whitespace(text, boundary)

        ended_on_boundary = text[previous_end - 1] in ".!?" or text[previous_end] == "\n"
        if ended_on_boundary:
            return self._skip_whitespace(text, previous_end)

        # Mid-sentence break with no boundary in the window: fall back to word overlap.
        start = window_start
        if start == 0 or text[start - 1].isspace():
            return start
        while start < len(text) and not text[start].isspace():
            start += 1
        return self._skip_whitespace(text, start)

    def _first_boundary_in(self, text: str, window_start: int, window_end: int) -> int | None:
        candidates = []
        newline = text.find("\n", window_start, window_end)
        if newline != -1:
            candidates.append(newline + 1)
        for separator in (". ", "! ", "? "):
            index = text.find(separator, window_start, window_end)
            if index != -1:
                candidates.append(index + len(separator))
        candidates = [candidate for candidate in candidates if candidate < window_end]
        return min(candidates) if candidates else None

    @staticmethod
    def _skip_whitespace(text: str, position: int) -> int:
        while position < len(text) and text[position].isspace():
            position += 1
        return position

    def _estimate_token_count(self, text: str) -> int:
        return len(text.split())
