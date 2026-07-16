"""Tests for schema-driven HCI command encoding."""

import unittest

from hci_analyzer.command_builder.definitions import COMMAND_DEFINITIONS_BY_OPCODE
from hci_analyzer.command_builder.encoder import HciCommandEncoder


class HciCommandEncoderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.encoder = HciCommandEncoder()

    def test_known_default_vectors(self) -> None:
        cases = {
            0x201D: ("01 1D 20 01 13", {"RX_Channel": 19}),
            0x2033: (
                "01 33 20 03 13 01 00",
                {"RX_Channel": 19, "PHY": 1, "Modulation_Index": 0},
            ),
            0x204F: (
                "01 4F 20 09 13 01 00 02 00 01 02 01 02",
                {
                    "RX_Channel": 19,
                    "PHY": 1,
                    "Modulation_Index": 0,
                    "Expected_CTE_Length": 2,
                    "Expected_CTE_Type": 0,
                    "Slot_Durations": 1,
                    "Antenna_IDs": [1, 2],
                },
            ),
            0x201E: (
                "01 1E 20 03 13 25 00",
                {"TX_Channel": 19, "Test_Data_Length": 37, "Packet_Payload": 0},
            ),
            0x2034: (
                "01 34 20 04 13 25 00 01",
                {
                    "TX_Channel": 19,
                    "Test_Data_Length": 37,
                    "Packet_Payload": 0,
                    "PHY": 1,
                },
            ),
            0x2050: (
                "01 50 20 09 13 25 00 01 02 01 02 01 02",
                {
                    "TX_Channel": 19,
                    "Test_Data_Length": 37,
                    "Packet_Payload": 0,
                    "PHY": 1,
                    "CTE_Length": 2,
                    "CTE_Type": 1,
                    "Antenna_IDs": [1, 2],
                },
            ),
            0x207B: (
                "01 7B 20 0A 13 25 00 01 02 01 02 01 02 00",
                {
                    "TX_Channel": 19,
                    "Test_Data_Length": 37,
                    "Packet_Payload": 0,
                    "PHY": 1,
                    "CTE_Length": 2,
                    "CTE_Type": 1,
                    "Antenna_IDs": [1, 2],
                    "TX_Power_Mode": 0,
                    "TX_Power_Level": 0,
                },
            ),
            0x201F: ("01 1F 20 00", {}),
        }
        for opcode, (expected_hex, values) in cases.items():
            with self.subTest(opcode=f"0x{opcode:04X}"):
                encoded = self.encoder.encode(
                    COMMAND_DEFINITIONS_BY_OPCODE[opcode], values
                )
                self.assertEqual(encoded.frame, bytes.fromhex(expected_hex))

    def test_signed_tx_power(self) -> None:
        values = {
            "TX_Channel": 19,
            "Test_Data_Length": 37,
            "Packet_Payload": 0,
            "PHY": 1,
            "CTE_Length": 2,
            "CTE_Type": 1,
            "Antenna_IDs": [1, 2],
            "TX_Power_Mode": 0,
            "TX_Power_Level": -5,
        }
        encoded = self.encoder.encode(COMMAND_DEFINITIONS_BY_OPCODE[0x207B], values)
        self.assertEqual(encoded.frame[-1], 0xFB)

    def test_minimum_tx_power_mode(self) -> None:
        values = {
            "TX_Channel": 19,
            "Test_Data_Length": 37,
            "Packet_Payload": 0,
            "PHY": 1,
            "CTE_Length": 2,
            "CTE_Type": 1,
            "Antenna_IDs": [1, 2],
            "TX_Power_Mode": 1,
            "TX_Power_Level": 0,
        }
        encoded = self.encoder.encode(COMMAND_DEFINITIONS_BY_OPCODE[0x207B], values)
        self.assertEqual(encoded.frame[-1], 0x7E)


if __name__ == "__main__":
    unittest.main()

