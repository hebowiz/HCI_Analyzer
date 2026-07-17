"""Text normalization shared by GUI and file log output."""

from __future__ import annotations

import re


_NON_ASCII_RUN = re.compile(r"[^\x00-\x7F]+")
_OS_ERROR_CODES = re.compile(
    r"OSError\(\s*(?P<errno>\d+).*?,\s*None,\s*(?P<winerror>\d+)\s*\)",
    re.DOTALL,
)
_WINERROR_CODE = re.compile(r"\[WinError\s+(?P<winerror>\d+)\]")


def ascii_safe_text(value: object) -> str:
    """Return readable ASCII text without leaking localized OS prose."""
    return _NON_ASCII_RUN.sub("[localized message omitted]", str(value))


def format_exception_for_log(exc: BaseException) -> str:
    """Format an exception using stable ASCII metadata and numeric OS codes."""
    errno: int | None = None
    winerror: int | None = None
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        current_errno = getattr(current, "errno", None)
        current_winerror = getattr(current, "winerror", None)
        if errno is None and isinstance(current_errno, int):
            errno = current_errno
        if winerror is None and isinstance(current_winerror, int):
            winerror = current_winerror
        current = current.__cause__ or current.__context__

    message = str(exc)
    match = _OS_ERROR_CODES.search(message)
    if match is not None:
        if errno is None:
            errno = int(match.group("errno"))
        if winerror is None:
            winerror = int(match.group("winerror"))
    if winerror is None:
        match = _WINERROR_CODE.search(message)
        if match is not None:
            winerror = int(match.group("winerror"))

    parts = [type(exc).__name__]
    if errno is not None:
        parts.append(f"errno={errno}")
    if winerror is not None:
        parts.append(f"winerror={winerror}")
    if errno is None and winerror is None and message and message.isascii():
        parts.append(message)
    return "; ".join(parts)
