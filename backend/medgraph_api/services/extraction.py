from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from medgraph_api.services.processing_errors import PermanentDocumentProcessingError


class UnsupportedDocumentTypeError(PermanentDocumentProcessingError):
    def __init__(self) -> None:
        super().__init__("Unsupported document type.")


class CorruptedDocumentError(PermanentDocumentProcessingError):
    def __init__(self) -> None:
        super().__init__("Document could not be read. Upload a valid PDF or text file.")


class MissingDocumentFileError(PermanentDocumentProcessingError):
    def __init__(self) -> None:
        super().__init__("Uploaded document file could not be found.")


class DocumentExtractionService:
    def extract_text(self, storage_path: str, content_type: str | None = None) -> str:
        path = Path(storage_path)
        if not path.exists():
            raise MissingDocumentFileError()

        if self._is_pdf(path, content_type):
            return self._extract_pdf_text(path)

        if self._is_text(path, content_type):
            return self._extract_plain_text(path)

        raise UnsupportedDocumentTypeError()

    def _extract_plain_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError) as exc:
            raise CorruptedDocumentError from exc

    def _extract_pdf_text(self, path: Path) -> str:
        try:
            reader = PdfReader(path)
            pages = [page.extract_text() or "" for page in reader.pages]
        except (OSError, PdfReadError, KeyError, ValueError) as exc:
            raise CorruptedDocumentError from exc

        return "\n\n".join(page.strip() for page in pages if page.strip())

    def _is_pdf(self, path: Path, content_type: str | None) -> bool:
        return content_type == "application/pdf" or path.suffix.lower() == ".pdf"

    def _is_text(self, path: Path, content_type: str | None) -> bool:
        if content_type is not None:
            return content_type.startswith("text/")

        return path.suffix.lower() in {".txt", ".text", ".md"}
