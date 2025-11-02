from __future__ import annotations

from typing import Sequence, TypeVar

T = TypeVar("T")

_ESCAPES = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&apos;",
}


def escape_html(value: str) -> str:
    """Escape HTML entities in the provided string."""
    escaped = value
    for char, replacement in _ESCAPES.items():
        escaped = escaped.replace(char, replacement)
    return escaped


def get_scale_value(values: Sequence[T], scale: int) -> T:
    """Return the clamped scale index for a sequence."""
    if not values:
        raise ValueError("values must not be empty")
    idx = max(0, min(scale, len(values) - 1))
    return values[idx]
