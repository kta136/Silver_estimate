"""Typed persistence outcomes for operations that previously returned sentinel values."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

ValueT = TypeVar("ValueT")


class RepositoryFailureKind(str, Enum):
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    VALIDATION = "validation"
    STORAGE = "storage"


@dataclass(frozen=True)
class RepositoryFailure:
    kind: RepositoryFailureKind
    message: str


class RepositoryOperationError(RuntimeError):
    def __init__(self, failure: RepositoryFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


@dataclass(frozen=True)
class RepositoryResult(Generic[ValueT]):
    value: ValueT | None = None
    failure: RepositoryFailure | None = None

    def __post_init__(self) -> None:
        if (self.value is None) == (self.failure is None):
            raise ValueError("RepositoryResult must contain exactly one outcome.")

    @property
    def succeeded(self) -> bool:
        return self.failure is None

    def unwrap(self) -> ValueT:
        if self.failure is not None:
            raise RepositoryOperationError(self.failure)
        assert self.value is not None
        return self.value

    @classmethod
    def success(cls, value: ValueT) -> RepositoryResult[ValueT]:
        return cls(value=value)

    @classmethod
    def failed(
        cls,
        kind: RepositoryFailureKind,
        message: str,
    ) -> RepositoryResult[ValueT]:
        return cls(failure=RepositoryFailure(kind, message))


__all__ = [
    "RepositoryFailure",
    "RepositoryFailureKind",
    "RepositoryOperationError",
    "RepositoryResult",
]
