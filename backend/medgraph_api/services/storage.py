from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

from medgraph_api.core.config import get_settings


@dataclass(frozen=True)
class StoredUpload:
    filename: str
    content_type: str | None
    size_bytes: int
    storage_path: str


class LocalUploadStorage:
    def __init__(self, upload_dir: str | None = None) -> None:
        settings = get_settings()
        self.upload_dir = Path(upload_dir or settings.upload_dir)

    def save(self, patient_id: UUID, file: UploadFile) -> StoredUpload:
        original_filename = Path(file.filename or "upload.bin").name
        patient_dir = self.upload_dir / str(patient_id)
        patient_dir.mkdir(parents=True, exist_ok=True)

        destination = patient_dir / f"{uuid4()}_{original_filename}"
        size_bytes = 0

        with destination.open("wb") as output_file:
            while chunk := file.file.read(1024 * 1024):
                size_bytes += len(chunk)
                output_file.write(chunk)

        return StoredUpload(
            filename=original_filename,
            content_type=file.content_type,
            size_bytes=size_bytes,
            storage_path=str(destination),
        )

