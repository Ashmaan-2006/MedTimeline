from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from medgraph_api.services.extraction import (
    CorruptedDocumentError,
    DocumentExtractionService,
    MissingDocumentFileError,
    UnsupportedDocumentTypeError,
)


def test_extract_plain_text_file(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("Patient reports intermittent chest pain.\n", encoding="utf-8")

    extracted_text = DocumentExtractionService().extract_text(
        storage_path=str(path),
        content_type="text/plain",
    )

    assert extracted_text == "Patient reports intermittent chest pain."


def test_extract_pdf_text_file(tmp_path: Path) -> None:
    path = tmp_path / "report.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=200, height=200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 36 120 Td (Normal sinus rhythm) Tj ET")
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    page[NameObject("/Contents")] = writer._add_object(content)

    with path.open("wb") as pdf_file:
        writer.write(pdf_file)

    extracted_text = DocumentExtractionService().extract_text(
        storage_path=str(path),
        content_type="application/pdf",
    )

    assert extracted_text == "Normal sinus rhythm"


def test_extract_rejects_unsupported_document_type(tmp_path: Path) -> None:
    path = tmp_path / "image.png"
    path.write_bytes(b"not real image data")

    with pytest.raises(UnsupportedDocumentTypeError):
        DocumentExtractionService().extract_text(
            storage_path=str(path),
            content_type="image/png",
        )


def test_extract_reports_missing_files_safely(tmp_path: Path) -> None:
    with pytest.raises(MissingDocumentFileError) as exc_info:
        DocumentExtractionService().extract_text(
            storage_path=str(tmp_path / "missing.pdf"),
            content_type="application/pdf",
        )

    assert exc_info.value.safe_message == "Uploaded document file could not be found."


def test_extract_reports_corrupted_text_safely(tmp_path: Path) -> None:
    path = tmp_path / "bad.txt"
    path.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(CorruptedDocumentError) as exc_info:
        DocumentExtractionService().extract_text(
            storage_path=str(path),
            content_type="text/plain",
        )

    assert exc_info.value.safe_message == "Document could not be read. Upload a valid PDF or text file."
