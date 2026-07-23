"""Tests for generic RACE packet parsing."""

import unittest

from hci_analyzer.parser.facade import HciParser
from hci_analyzer.parser.race import RaceParser


class RaceParserTests(unittest.TestCase):
    def test_decodes_race_envelope_and_payload(self) -> None:
        result = HciParser().parse_hex_string("05 01 04 00 34 12 AA BB")

        self.assertTrue(result.success)
        self.assertEqual(result.packet_type, "RACE")
        self.assertEqual(result.decoded["type"], 0x01)
        self.assertEqual(result.decoded["length"], 4)
        self.assertEqual(result.decoded["command_id"], 0x1234)
        self.assertEqual(result.decoded["payload_hex"], "AA BB")

    def test_accepts_frame_without_payload(self) -> None:
        result = HciParser().parse_hex_string("05 02 02 00 78 56")

        self.assertTrue(result.success)
        self.assertEqual(result.decoded["payload_length"], 0)
        self.assertEqual(result.decoded["command_id_hex"], "0x5678")

    def test_rejects_length_mismatch(self) -> None:
        result = RaceParser().parse(bytes.fromhex("05 01 04 00 34 12 AA"))

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "PACKET_LENGTH_MISMATCH")

    def test_rejects_length_above_temporary_maximum(self) -> None:
        result = RaceParser().parse(bytes.fromhex("05 01 01 02 34 12"))

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "RACE_LENGTH_OUT_OF_RANGE")

    def test_can_disable_race_priority_for_future_iso_use(self) -> None:
        frame = bytes.fromhex("05 01 04 04 00 AA BB CC DD")

        result = HciParser(prefer_race=False).parse_bytes(frame)

        self.assertTrue(result.success)
        self.assertEqual(result.packet_type, "HCI_ISO_Data")


if __name__ == "__main__":
    unittest.main()
