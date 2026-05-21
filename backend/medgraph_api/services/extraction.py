from pathlib import Path

from pypdf import PdfReader


class UnsupportedDocumentTypeError(ValueError):
    pass


class DocumentExtractionService:
    def extract_text(self, storage_path: str, content_type: str | None = None) -> str:
        path = Path(storage_path)
        if self._is_pdf(path, content_type):
            return self._extract_pdf_text(path)

        if self._is_text(path, content_type):
            return self._extract_plain_text(path)

        raise UnsupportedDocumentTypeError(f"Unsupported document type: {content_type or path.suffix}")

    def _extract_plain_text(self, path: Path) -> str:
        return path.read_text(encoding="utf-8").strip()

    def _extract_pdf_text(self, path: Path) -> str:
        reader = PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(page.strip() for page in pages if page.strip())

    def _is_pdf(self, path: Path, content_type: str | None) -> bool:
        return content_type == "application/pdf" or path.suffix.lower() == ".pdf"

    def _is_text(self, path: Path, content_type: str | None) -> bool:
        if content_type is not None:
            return content_type.startswith("text/")

        return path.suffix.lower() in {".txt", ".text", ".md"}

