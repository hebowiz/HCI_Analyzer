"""Format Command Console transport events as readable log lines."""

from __future__ import annotations

import json

from hci_analyzer.presentation.summary import format_parse_summary
from hci_analyzer.presentation.text import ascii_safe_text
from hci_analyzer.serial.transport import TransportEvent


def format_transport_event(event: TransportEvent) -> list[str]:
    """Return the complete legacy and human-readable log representation."""
    timestamp = event.timestamp.isoformat(timespec="milliseconds")
    transaction = (
        f" [Transaction {event.transaction_id}]"
        if event.transaction_id is not None
        else ""
    )
    response_time = (
        f" [{event.response_time_ms:.1f} ms]"
        if event.response_time_ms is not None
        else ""
    )
    lines = [
        f"[{timestamp}] [{event.kind.value.upper()}]{transaction}{response_time}"
    ]
    if event.raw_data:
        lines.append(f"RAW: {event.raw_data.hex(' ').upper()}")
    if event.parsed is not None:
        detail = (
            event.parsed.decoded
            if event.parsed.success
            else event.parsed.error.to_dict()
            if event.parsed.error
            else {"error": "Unknown parser error"}
        )
        lines.append(json.dumps(detail, ensure_ascii=False, sort_keys=True))
        lines.extend(
            format_parse_summary(
                event.parsed,
                response_time_ms=event.response_time_ms,
            )
        )
    if event.message:
        lines.append(event.message)
    return [ascii_safe_text(line) for line in lines]
