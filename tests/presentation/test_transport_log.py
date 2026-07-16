"""Tests for the complete Command Console log representation."""

import unittest
from datetime import datetime, timezone

from hci_analyzer.parser.facade import HciParser
from hci_analyzer.presentation.transport_log import format_transport_event
from hci_analyzer.serial.transport import TransportEvent, TransportEventKind


class TransportLogFormattingTests(unittest.TestCase):
    def test_legacy_output_is_followed_by_summary(self) -> None:
        raw = bytes.fromhex("01 34 20 04 13 25 00 02")
        parsed = HciParser().parse_bytes(raw)
        event = TransportEvent(
            timestamp=datetime(2026, 7, 16, 22, 40, tzinfo=timezone.utc),
            kind=TransportEventKind.TRANSMITTED,
            source="Console:COM1",
            raw_data=raw,
            parsed=parsed,
            transaction_id=12,
        )

        lines = format_transport_event(event)

        raw_index = next(
            index for index, line in enumerate(lines) if line.startswith("RAW:")
        )
        json_index = next(
            index for index, line in enumerate(lines) if line.startswith("{")
        )
        summary_index = lines.index("SUMMARY")
        self.assertLess(raw_index, json_index)
        self.assertLess(json_index, summary_index)
        self.assertIn(
            "  Command                : HCI_LE_Transmitter_Test [v2]",
            lines,
        )


if __name__ == "__main__":
    unittest.main()
