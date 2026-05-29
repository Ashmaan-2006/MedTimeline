import hashlib
import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextEmbedding:
    text: str
    embedding: list[float]
    embedding_model: str


class HashingEmbeddingService:
    def __init__(
        self,
        dimensions: int = 384,
        model_name: str = "local-hashing-embedding-v1",
    ) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be greater than 0.")

        self.dimensions = dimensions
        self.model_name = model_name

    def embed_text(self, text: str) -> TextEmbedding:
        normalized_text = self._normalize_text(text)
        return TextEmbedding(
            text=normalized_text,
            embedding=self._embed_normalized_text(normalized_text),
            embedding_model=self.model_name,
        )

    def embed_texts(self, texts: list[str]) -> list[TextEmbedding]:
        return [self.embed_text(text) for text in texts]

    def _embed_normalized_text(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = self._tokenize(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], byteorder="big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        return self._normalize_vector(vector)

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.split())

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)?", text.lower())

    def _normalize_vector(self, vector: list[float]) -> list[float]:
        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            return vector

        return [value / magnitude for value in vector]
