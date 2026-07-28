"""Shared validation and conversion helpers."""

from collections.abc import Callable
from typing import Any

from .errors import NotFoundError, OperationError


def require[T](value: T | None, message: str) -> T:
    if value is None:
        raise NotFoundError(message)
    return value


def checked(call: Callable[..., Any], *args: Any, operation: str, **kwargs: Any) -> Any:
    try:
        result = call(*args, **kwargs)
    except Exception as exc:
        raise OperationError(f"{operation} failed: {exc}") from exc
    if result is False or result is None:
        raise OperationError(f"Resolve rejected operation: {operation}")
    return result


def serializable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(v) for v in value]
    return str(value)
