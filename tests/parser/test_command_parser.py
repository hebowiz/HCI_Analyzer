"""Tests for supported LE RF PHY Test commands."""

import unittest

from hci_analyzer.parser.facade import HciParser


class HciCommandParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = HciParser()

    def test_transmitter_test_v2(self) -> None:
        result = self.parser.parse_hex_string("01 34 20 04 13 25 00 02")

        self.assertTrue(result.success)
        self.assertEqual(result.decoded["opcode"], "0x2034")
        self.assertEqual(
            result.decoded["display_name"], "HCI_LE_Transmitter_Test[v2]"
        )
        self.assertEqual(result.decoded["parameters"]["frequency_mhz"], 2440)
        self.assertEqual(result.decoded["parameters"]["test_data_length"], 37)
        self.assertEqual(result.decoded["parameters"]["phy_name"], "LE 2M PHY")

    def test_all_fixed_length_command_versions(self) -> None:
        cases = (
            ("01 1D 20 01 13", "HCI_LE_Receiver_Test[v1]"),
            ("01 33 20 03 13 01 00", "HCI_LE_Receiver_Test[v2]"),
            ("01 1E 20 03 13 25 00", "HCI_LE_Transmitter_Test[v1]"),
        )
        for frame, expected_name in cases:
            with self.subTest(frame=frame):
                result = self.parser.parse_hex_string(frame)
                self.assertTrue(result.success)
                self.assertEqual(result.decoded["display_name"], expected_name)

    def test_transmitter_test_v3_variable_length(self) -> None:
        result = self.parser.parse_hex_string(
            "01 50 20 09 13 25 00 01 02 01 02 01 02"
        )

        self.assertTrue(result.success)
        self.assertEqual(result.decoded["parameters"]["antenna_ids"], [1, 2])

    def test_receiver_test_v3_variable_length(self) -> None:
        result = self.parser.parse_hex_string(
            "01 4F 20 09 13 01 00 02 00 01 02 01 02"
        )

        self.assertTrue(result.success)
        params = result.decoded["parameters"]
        self.assertEqual(params["switching_pattern_length"], 2)
        self.assertEqual(params["antenna_ids"], [1, 2])

    def test_transmitter_test_v4_variable_length_and_power(self) -> None:
        result = self.parser.parse_bytes(
            bytes.fromhex("01 7B 20 0A 13 25 00 01 02 01 02 01 02 FB")
        )

        self.assertTrue(result.success)
        params = result.decoded["parameters"]
        self.assertEqual(params["antenna_ids"], [1, 2])
        self.assertEqual(params["tx_power_level"], -5)

    def test_test_end(self) -> None:
        result = self.parser.parse_hex_string("01 1F 20 00")

        self.assertTrue(result.success)
        self.assertEqual(result.decoded["command_name"], "HCI_LE_Test_End")
        self.assertEqual(result.decoded["parameters"], {})

    def test_reset(self) -> None:
        result = self.parser.parse_hex_string("01 03 0C 00")

        self.assertTrue(result.success)
        self.assertEqual(result.decoded["display_name"], "HCI_Reset")
        self.assertEqual(result.decoded["parameters"], {})

    def test_read_local_supported_commands_versions(self) -> None:
        cases = (
            ("01 02 10 00", "HCI_Read_Local_Supported_Commands[v1]"),
            ("01 10 10 00", "HCI_Read_Local_Supported_Commands[v2]"),
        )
        for frame, expected_name in cases:
            with self.subTest(frame=frame):
                result = self.parser.parse_hex_string(frame)
                self.assertTrue(result.success)
                self.assertEqual(result.decoded["display_name"], expected_name)
                self.assertEqual(result.decoded["parameters"], {})

    def test_unknown_opcode_is_error(self) -> None:
        result = self.parser.parse_hex_string("01 01 20 00")

        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertEqual(result.error.code, "UNKNOWN_OPCODE")

    def test_header_length_mismatch_is_error(self) -> None:
        result = self.parser.parse_hex_string("01 34 20 04 13 25 00")

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "PACKET_LENGTH_MISMATCH")

    def test_variable_length_mismatch_is_error(self) -> None:
        result = self.parser.parse_hex_string(
            "01 50 20 08 13 25 00 01 02 01 02 01"
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "PARAMETER_LENGTH_MISMATCH")

    def test_invalid_hex_string_is_error(self) -> None:
        result = self.parser.parse_hex_string("01 34 ZZ")

        self.assertFalse(result.success)
        self.assertEqual(result.error.code, "INVALID_HEX_STRING")

    def test_public_parse_api_returns_dict(self) -> None:
        result = self.parser.parse(bytes.fromhex("01 1F 20 00"))

        self.assertIsInstance(result, dict)
        self.assertTrue(result["success"])
        self.assertEqual(result["raw_data"], "01 1F 20 00")


if __name__ == "__main__":
    unittest.main()
