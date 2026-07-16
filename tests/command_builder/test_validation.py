"""Tests for command form validation and normalization."""

import unittest

from hci_analyzer.command_builder.definitions import COMMAND_DEFINITIONS_BY_OPCODE
from hci_analyzer.command_builder.validation import CommandValidator


class CommandValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = CommandValidator()

    def test_hex_integer_input_is_normalized(self) -> None:
        result = self.validator.validate(
            COMMAND_DEFINITIONS_BY_OPCODE[0x2034],
            {
                "TX_Channel": "0x13",
                "Test_Data_Length": "0x25",
                "Packet_Payload": "0",
                "PHY": "1",
            },
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.normalized_values["TX_Channel"], 19)
        self.assertEqual(result.normalized_values["Test_Data_Length"], 37)

    def test_leading_zero_decimal_input_is_normalized(self) -> None:
        result = self.validator.validate(
            COMMAND_DEFINITIONS_BY_OPCODE[0x2034],
            {
                "TX_Channel": "08",
                "Test_Data_Length": "037",
                "Packet_Payload": "0",
                "PHY": "1",
            },
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.normalized_values["TX_Channel"], 8)
        self.assertEqual(result.normalized_values["Test_Data_Length"], 37)

    def test_cte_length_one_is_rejected(self) -> None:
        result = self.validator.validate(
            COMMAND_DEFINITIONS_BY_OPCODE[0x204F],
            {
                "RX_Channel": 19,
                "PHY": 1,
                "Modulation_Index": 0,
                "Expected_CTE_Length": 1,
                "Expected_CTE_Type": 0,
                "Slot_Durations": 1,
                "Antenna_IDs": [1, 2],
            },
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].parameter_name, "Expected_CTE_Length")

    def test_short_antenna_array_is_rejected(self) -> None:
        result = self.validator.validate(
            COMMAND_DEFINITIONS_BY_OPCODE[0x2050],
            {
                "TX_Channel": 19,
                "Test_Data_Length": 37,
                "Packet_Payload": 0,
                "PHY": 1,
                "CTE_Length": 2,
                "CTE_Type": 1,
                "Antenna_IDs": [1],
            },
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "ARRAY_LENGTH")

    def test_maximum_power_mode_generates_special_value(self) -> None:
        result = self.validator.validate(
            COMMAND_DEFINITIONS_BY_OPCODE[0x207B],
            {
                "TX_Channel": 19,
                "Test_Data_Length": 37,
                "Packet_Payload": 0,
                "PHY": 1,
                "CTE_Length": 2,
                "CTE_Type": 1,
                "Antenna_IDs": [1, 2],
                "TX_Power_Mode": 2,
                "TX_Power_Level": 0,
            },
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.normalized_values["TX_Power_Level"], 0x7F)

    def test_special_power_mode_ignores_numeric_field(self) -> None:
        result = self.validator.validate(
            COMMAND_DEFINITIONS_BY_OPCODE[0x207B],
            {
                "TX_Channel": 19,
                "Test_Data_Length": 37,
                "Packet_Payload": 0,
                "PHY": 1,
                "CTE_Length": 2,
                "CTE_Type": 1,
                "Antenna_IDs": [1, 2],
                "TX_Power_Mode": 1,
                "TX_Power_Level": "not-used",
            },
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.normalized_values["TX_Power_Level"], 0x7E)


if __name__ == "__main__":
    unittest.main()
