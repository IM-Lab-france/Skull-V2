"""Business errors shared by Skull domain services and API adapters."""

from __future__ import annotations


class DomainError(Exception):
    """Base class for errors that describe a rejected domain operation."""


class NotFoundError(FileNotFoundError, DomainError):
    """A requested domain resource does not exist."""


class InvalidInputError(ValueError, DomainError):
    """A domain value is malformed or fails validation."""


class ConflictError(DomainError):
    """The requested operation conflicts with the current domain state."""


class DependencyUnavailableError(ConnectionError, DomainError):
    """A required external dependency is unavailable."""


class OperationNotAllowedError(PermissionError, DomainError):
    """The current state or policy forbids the requested operation."""


__all__ = [
    "ConflictError",
    "DependencyUnavailableError",
    "DomainError",
    "InvalidInputError",
    "NotFoundError",
    "OperationNotAllowedError",
]
