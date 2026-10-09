"""Tests for chronological real-time Discovery capture storage."""

import unittest
from datetime import datetime, timezone

from hci_analyzer.models import (
    LogRecord,
    RecordKind,
    TrafficDirection,
)
from hci_analyzer.parser.facade import HciParser
from hci_analyzer.vendor.live_capture import LiveCaptureStore


class LiveCaptureStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = HciParser()
        self.store = LiveCaptureStore()

    def test_vendor_commands_are_kept_as_individual_chronological_entries(self) -> None:
        first = self._record("01 41 FC 02 01 02", second=1)
        second = self._record("01 41 FC 02 01 02", second=2)

        self.store.add_record(first)
        self.store.add_record(second)

        self.assertEqual(len(self.store.entries), 2)
        self.assertLess(
            self.store.entries[0].timestamp,
            self.store.entries[1].timestamp,
        )
        self.assertEqual(
            [group.count for group in self.store.groups()],
            [1, 1],
        )

    def test_duplicate_grouping_is_optional_and_preserves_first_order(self) -> None:
        self.store.add_record(self._record("01 41 FC 01 AA", second=1))
        self.store.add_record(self._record("01 42 FC 01 BB", second=2))
        self.store.add_record(self._record("01 41 FC 01 AA", second=3))

        grouped = self.store.groups(group_duplicates=True)

        self.assertEqual([group.count for group in grouped], [2, 1])
        self.assertEqual(grouped[0].first.opcode, 0xFC41)
        self.assertEqual(grouped[1].first.opcode, 0xFC42)

    def test_race_is_displayed_but_not_analyzable(self) -> None:
        entry = self.store.add_record(
            self._record("05 02 04 00 34 12 AA BB", second=1)
        )

        self.assertIsNotNone(entry)
        assert entry is not None
        self.assertEqual(entry.protocol, "RACE")
        self.assertEqual(entry.identifier, "Type 0x02 / ID 0x1234")
        self.assertFalse(entry.analyzable)
        self.assertEqual(self.store.vendor_opcodes(), ())

    def test_standard_hci_command_is_analyzable(self) -> None:
        entry = self.store.add_record(
            self._record("01 1F 20 00", second=1)
        )

        self.assertTrue(entry.analyzable)
        self.assertEqual(entry.protocol, "HCI Command")
        self.assertEqual(self.store.vendor_opcodes(), (0x201F,))

    def test_unknown_standard_command_and_response_are_retained(self) -> None:
        command = self.store.add_record(self._record("01 01 20 02 AA BB", second=1))
        event = self.store.add_record(self._record("04 0E 04 01 01 20 00", second=2))
        self.assertEqual(command.parameters, bytes.fromhex("AA BB"))
        self.assertEqual(event.related_opcode, 0x2001)
        self.assertEqual(command.vendor_capture.responses, [event.raw_data])

    def test_invalid_h4_command_length_is_not_captured(self) -> None:
        self.assertIsNone(self.store.add_record(
            self._record("01 01 20 02 AA", second=1)
        ))

    def test_remove_and_restore_preserve_original_order(self) -> None:
        for second, frame in enumerate(
            ("01 41 FC 01 01", "01 42 FC 01 02", "01 43 FC 01 03"),
            start=1,
        ):
            self.store.add_record(self._record(frame, second=second))
        removed_id = self.store.entries[1].capture_id

        self.assertEqual(self.store.remove([removed_id]), 1)
        self.assertEqual(
            [entry.opcode for entry in self.store.entries],
            [0xFC41, 0xFC43],
        )

        self.assertEqual(self.store.restore_last_removed(), 1)
        self.assertEqual(
            [entry.opcode for entry in self.store.entries],
            [0xFC41, 0xFC42, 0xFC43],
        )

    def test_command_complete_is_associated_by_opcode(self) -> None:
        self.store.add_record(self._record("01 41 FC 01 AA", second=1))

        event = self.store.add_record(
            self._record("04 0E 04 01 41 FC 00", second=2)
        )

        captures = self.store.vendor_captures(0xFC41)
        self.assertEqual(len(captures[0].responses), 1)
        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.protocol, "HCI Event")
        self.assertEqual(event.related_opcode, 0xFC41)
        self.assertEqual(
            event.identifier,
            "HCI_Command_Complete / 0xFC41",
        )
        self.assertEqual(event.parameters, bytes.fromhex("01 41 FC 00"))
        self.assertFalse(event.analyzable)
        self.assertEqual(self.store.vendor_opcodes(), (0xFC41,))

    def test_vendor_specific_event_is_displayed_and_related_to_latest_command(
        self,
    ) -> None:
        self.store.add_record(self._record("01 41 FC 00", second=1))

        event = self.store.add_record(
            self._record("04 FF 02 55 AA", second=2)
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.protocol, "HCI Event")
        self.assertEqual(event.identifier, "HCI_Vendor_Specific_Event / 0xFC41")
        self.assertEqual(event.parameters, bytes.fromhex("55 AA"))
        self.assertEqual(
            self.store.vendor_captures(0xFC41)[0].responses,
            [bytes.fromhex("04 FF 02 55 AA")],
        )

    def test_hci_event_with_parser_error_is_still_displayed(self) -> None:
        event = self.store.add_record(
            self._record("04 0E 04 01 01 04 00", second=1)
        )

        self.assertIsNotNone(event)
        assert event is not None
        self.assertEqual(event.protocol, "HCI Event")
        self.assertEqual(event.related_opcode, 0x0401)
        self.assertFalse(event.analyzable)

    def _record(self, raw_hex: str, *, second: int) -> LogRecord:
        raw = bytes.fromhex(raw_hex)
        parsed = self.parser.parse_bytes(raw)
        return LogRecord(
            timestamp=datetime(2026, 7, 24, 12, 0, second, tzinfo=timezone.utc),
            source="Port1:COM1",
            direction=TrafficDirection.UNKNOWN,
            kind=RecordKind.PACKET if parsed.success else RecordKind.ERROR,
            raw_data=raw,
            result=parsed,
        )


if __name__ == "__main__":
    unittest.main()
