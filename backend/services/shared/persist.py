"""Deprecated file-backed persistence module.

This module is intentionally retained only so older imports fail loudly if they are
still used. Production persistence now flows through the shared relational and
Mongo-backed repositories.
"""

from __future__ import annotations

from typing import Any


class DeprecatedPersistenceError(RuntimeError):
    pass


MESSAGE = (
    "services.shared.persist is deprecated. Use services.shared.repositories "
    "with relational/document stores instead of file-backed JSON persistence."
)


def load_service_data(name: str, defaults: dict[str, Any]) -> dict[str, Any]:
    raise DeprecatedPersistenceError(MESSAGE)


def save_service_data(name: str, data: dict[str, Any]) -> None:
    raise DeprecatedPersistenceError(MESSAGE)


def reset_service_data(name: str, defaults: dict[str, Any]) -> None:
    raise DeprecatedPersistenceError(MESSAGE)
