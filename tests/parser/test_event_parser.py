"""Tests for HCI events used by LE RF PHY tests."""

import unittest

from hci_analyzer.parser.facade import HciParser


class HciEventParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = HciParser()

    def test_le_status_command_complete(self) -> None:
        result = self.parser.parse_hex_string("04 0E 04 01 34 20 00")

        self.assertTrue(result.success)
        self.assertEqual(result.decoded["rf_test_event"], "LE_Status")
        self.assertEqual(
            result.decoded["command_name"], "HCI_LE_Transmitter_Test[v2]"
        )
        self.assertEqual(result.decoded["status"], 0)

    def test_le_packet_report_test_end(self) -> None:
        result = self.parser.parse_hex_string("04 0E 06 01 1F 20 00 34 12")

        self.assertTrue(result.success)
        self.assertEqual(result.decoded["rf_test_event"], "LE_Packet_Report")
        self.assertEqual(result.decoded["num_packets"], 0x1234)

    def test_command_complete_unknown_opcode_is_error(self) -> None:
        result = self.parser.parse_hex_string("04 0E 04 01 01 20 00")

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "UNKNOWN_OPCODE")

    def test_command_status(self) -> None:
        result = self.parser.parse_hex_string("04 0F 04 00 01 34 20")

        self.assertTrue(result.success)
        self.assertEqual(result.decoded["event_name"], "HCI_Command_Status")
        self.assertEqual(
            result.decoded["command_name"], "HCI_LE_Transmitter_Test[v2]"
        )

    def test_command_complete_return_length_mismatch(self) -> None:
        result = self.parser.parse_hex_string("04 0E 05 01 34 20 00 01")

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "RETURN_PARAMETER_LENGTH_MISMATCH")

    def test_connectionless_iq_report(self) -> None:
        result = self.parser.parse_hex_string(
            "04 3E 11 15 34 12 13 D3 FF 02 00 01 00 78 56 02 01 FF 7F 80"
        )

        self.assertTrue(result.success)
        self.assertEqual(
            result.decoded["subevent_name"], "HCI_LE_Connectionless_IQ_Report"
        )
        params = result.decoded["parameters"]
        self.assertEqual(params["sync_handle"], 0x1234)
        self.assertEqual(params["rssi_dbm"], -4.5)
        self.assertEqual(params["sample_count"], 2)
        self.assertEqual(params["samples"][0], {"i": 1, "q": -1})
        self.assertEqual(params["samples"][1], {"i": 127, "q": -128})

    def test_unknown_event_is_preserved(self) -> None:
        result = self.parser.parse_hex_string("04 FF 02 AA BB")

        self.assertTrue(result.success)
        self.assertEqual(result.decoded["event_name"], "Unknown HCI Event")
        self.assertEqual(result.decoded["parameters_hex"], "AA BB")

    def test_supported_commands_v1_response(self) -> None:
        supported = bytearray(64)
        supported[28] = (1 << 4) | (1 << 5) | (1 << 6)
        supported[36] = 1 << 0
        frame = (
            bytes.fromhex("04 0E 44 01 02 10 00")
            + bytes(supported)
        )

        result = self.parser.parse_bytes(frame)

        self.assertTrue(result.success)
        self.assertEqual(
            result.decoded["command_name"],
            "HCI_Read_Local_Supported_Commands[v1]",
        )
        self.assertEqual(result.decoded["supported_commands_length"], 64)
        support = result.decoded["relevant_command_support"]
        self.assertTrue(support["HCI_LE_Receiver_Test[v1]"])
        self.assertTrue(support["HCI_LE_Transmitter_Test[v1]"])
        self.assertTrue(support["HCI_LE_Test_End"])
        self.assertTrue(support["HCI_LE_Transmitter_Test[v2]"])
        self.assertFalse(support["HCI_LE_Transmitter_Test[v4]"])
        self.assertEqual(result.decoded["set_bit_count"], 4)
        self.assertEqual(
            result.decoded["supported_commands_by_scope"]["PHY_TEST_CORE"],
            [
                "HCI_LE_Receiver_Test [v1]",
                "HCI_LE_Transmitter_Test [v1]",
                "HCI_LE_Test_End",
                "HCI_LE_Transmitter_Test [v2]",
            ],
        )

    def test_supported_commands_v2_response(self) -> None:
        supported = bytearray(251)
        supported[45] = 1 << 0
        supported[49] = 1 << 0
        frame = (
            bytes.fromhex("04 0E FF 01 10 10 00")
            + bytes(supported)
        )

        result = self.parser.parse_bytes(frame)

        self.assertTrue(result.success)
        self.assertEqual(
            result.decoded["command_name"],
            "HCI_Read_Local_Supported_Commands[v2]",
        )
        self.assertEqual(result.decoded["supported_commands_length"], 251)
        support = result.decoded["relevant_command_support"]
        self.assertTrue(support["HCI_LE_Transmitter_Test[v4]"])
        self.assertTrue(support["HCI_Read_Local_Supported_Commands[v2]"])
        self.assertEqual(
            result.decoded["application_command_support"][
                "HCI_LE_Transmitter_Test[v4]"
            ],
            True,
        )
        self.assertEqual(
            result.decoded["supported_commands_by_scope"]["CAPABILITY_QUERY"],
            ["HCI_Read_Local_Supported_Commands [v2]"],
        )

    def test_supported_commands_response_length_mismatch(self) -> None:
        frame = bytes.fromhex("04 0E 04 01 02 10 00")

        result = self.parser.parse_bytes(frame)

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "RETURN_PARAMETER_LENGTH_MISMATCH")


if __name__ == "__main__":
    unittest.main()
