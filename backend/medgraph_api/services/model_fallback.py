from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from dataclasses import dataclass
from typing import Generic, TypeVar


T = TypeVar("T")


class ModelProviderError(RuntimeError):
    pass


class ModelTimeoutError(TimeoutError):
    pass


@dataclass(frozen=True)
class ModelFallbackResult(Generic[T]):
    output: T
    used_fallback: bool
    warning: str | None = None


class ModelFallbackRunner:
    def __init__(self, timeout_seconds: int = 30) -> None:
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        primary: Callable[[], T],
        fallback: Callable[[], T],
        operation_name: str,
    ) -> ModelFallbackResult[T]:
        try:
            return ModelFallbackResult(
                output=self._run_with_timeout(primary),
                used_fallback=False,
            )
        except (FutureTimeoutError, TimeoutError, ModelProviderError) as exc:
            return ModelFallbackResult(
                output=fallback(),
                used_fallback=True,
                warning=(
                    f"{operation_name} used fallback model because the primary model "
                    f"was unavailable or timed out: {exc.__class__.__name__}."
                ),
            )

    def _run_with_timeout(self, func: Callable[[], T]) -> T:
        if self.timeout_seconds <= 0:
            raise ModelTimeoutError("Model call timed out before execution.")

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(func)
        try:
            return future.result(timeout=self.timeout_seconds)
        except FutureTimeoutError as exc:
            future.cancel()
            raise ModelTimeoutError(f"Model call exceeded {self.timeout_seconds} seconds.") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


class FallbackTextGenerationService:
    def __init__(
        self,
        primary: Callable[[str], str],
        fallback: Callable[[str], str],
        operation_name: str,
        timeout_seconds: int,
    ) -> None:
        self.primary = primary
        self.fallback = fallback
        self.operation_name = operation_name
        self.runner = ModelFallbackRunner(timeout_seconds)

    def generate(self, prompt: str) -> str:
        result = self.runner.run(
            primary=lambda: self.primary(prompt),
            fallback=lambda: self.fallback(prompt),
            operation_name=self.operation_name,
        )
        return result.output
