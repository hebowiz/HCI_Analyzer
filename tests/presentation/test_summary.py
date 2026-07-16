"""Tests for human-readable HCI log summaries."""

import unittest

from hci_analyzer.parser.facade import HciParser
from hci_analyzer.presentation.summary import format_parse_summary


class HciSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = HciParser()

    def test_transmitter_v2_summary(self) -> None:
        result = self.parser.parse_hex_string("01 34 20 04 13 25 00 02")

        summary = "\n".join(format_parse_summary(result))

        self.assertIn("Command                : HCI_LE_Transmitter_Test [v2]", summary)
        self.assertIn("TX Channel             : 19 (2440 MHz)", summary)
        self.assertIn("Data Length            : 37 bytes", summary)
        self.assertIn("Payload                : PRBS9 (0x00)", summary)
        self.assertIn("PHY                    : LE 2M PHY (0x02)", summary)

    def test_transmitter_v4_summary_includes_cte_antennas_and_power(self) -> None:
        result = self.parser.parse_hex_string(
            "01 7B 20 0B 13 25 00 03 02 01 03 01 02 03 7F"
        )

        summary = "\n".join(format_parse_summary(result))

        self.assertIn("CTE Length             : 16 us (value=2)", summary)
        self.assertIn("Switching Pattern      : 3 antennas", summary)
        self.assertIn("Antenna IDs          : 1, 2, 3", summary)
        self.assertIn("TX Power               : Maximum supported power (0x7F)", summary)

    def test_receiver_v2_summary(self) -> None:
        result = self.parser.parse_hex_string("01 33 20 03 13 01 00")

        summary = "\n".join(format_parse_summary(result))

        self.assertIn("Command                : HCI_LE_Receiver_Test [v2]", summary)
        self.assertIn("RX Channel             : 19 (2440 MHz)", summary)
        self.assertIn("Modulation Index       : standard modulation index (0x00)", summary)

    def test_packet_report_summary_includes_response_time(self) -> None:
        result = self.parser.parse_hex_string(
            "04 0E 06 01 1F 20 00 34 12"
        )

        summary = "\n".join(
            format_parse_summary(result, response_time_ms=18.4)
        )

        self.assertIn("Event                  : HCI_Command_Complete", summary)
        self.assertIn("For Command            : HCI_LE_Test_End (0x201F)", summary)
        self.assertIn("Status                 : Success (0x00)", summary)
        self.assertIn("Response Time          : 18.4 ms", summary)
        self.assertIn("Received Packets       : 4660", summary)

    def test_supported_commands_summary_is_compact(self) -> None:
        supported = bytearray(64)
        supported[28] = (1 << 4) | (1 << 6)
        frame = bytes.fromhex("04 0E 44 01 02 10 00") + bytes(supported)
        result = self.parser.parse_bytes(frame)

        summary = "\n".join(format_parse_summary(result))

        self.assertIn("Response               : Supported Commands, 64 octets", summary)
        self.assertIn("Set Bits               : 2", summary)
        self.assertIn("Supported   HCI_LE_Receiver_Test [v1]", summary)
        self.assertIn("Unsupported HCI_LE_Transmitter_Test [v1]", summary)
        self.assertNotIn(result.decoded["supported_commands_hex"], summary)

    def test_iq_report_summary_limits_sample_preview(self) -> None:
        result = self.parser.parse_hex_string(
            "04 3E 11 15 34 12 13 D3 FF 02 00 01 00 78 56 02 01 FF 7F 80"
        )

        summary = "\n".join(
            format_parse_summary(result, iq_sample_preview_limit=1)
        )

        self.assertIn("Event                  : HCI_LE_Connectionless_IQ_Report", summary)
        self.assertIn("Sync Handle            : 0x1234", summary)
        self.assertIn("RSSI                   : -4.5 dBm", summary)
        self.assertIn("#0   I=   1  Q=  -1", summary)
        self.assertIn("... 1 more samples", summary)

    def test_command_status_error_uses_readable_status_name(self) -> None:
        result = self.parser.parse_hex_string("04 0F 04 0C 01 34 20")

        summary = "\n".join(format_parse_summary(result))

        self.assertIn("ERROR - Command Disallowed (0x0C)", summary)
        self.assertIn("Completion             : Command was not started", summary)


if __name__ == "__main__":
    unittest.main()
