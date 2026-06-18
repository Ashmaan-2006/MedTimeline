from sqlalchemy.exc import DisconnectionError, OperationalError

from medgraph_api.services.processing_errors import (
    PermanentDocumentProcessingError,
    TemporaryDocumentProcessingError,
)
from medgraph_api.tasks.document_tasks import is_retryable_processing_exception


def test_retryable_processing_exception_classification() -> None:
    assert is_retryable_processing_exception(TemporaryDocumentProcessingError("Temporary issue."))
    assert is_retryable_processing_exception(TimeoutError("provider timeout"))
    assert is_retryable_processing_exception(OperationalError("statement", {}, Exception("db down")))
    assert is_retryable_processing_exception(DisconnectionError("database disconnected"))


def test_permanent_and_unknown_processing_exceptions_are_not_retryable() -> None:
    assert not is_retryable_processing_exception(PermanentDocumentProcessingError("Permanent issue."))
    assert not is_retryable_processing_exception(ValueError("unsupported payload"))
