"""Tests for the complete Supported Commands mapping."""

import unittest

from hci_analyzer.parser.supported_commands import (
    SUPPORTED_COMMAND_DEFINITIONS,
    SUPPORTED_COMMANDS_BY_POSITION,
    decode_supported_commands,
    support_for_commands,
)


class SupportedCommandsTests(unittest.TestCase):
    def test_mapping_covers_all_defined_positions_through_octet_49(self) -> None:
        self.assertEqual(len(SUPPORTED_COMMAND_DEFINITIONS), 400)
        self.assertEqual(
            SUPPORTED_COMMANDS_BY_POSITION[(28, 4)].command,
            "HCI_LE_Receiver_Test [v1]",
        )
        self.assertEqual(
            SUPPORTED_COMMANDS_BY_POSITION[(49, 0)].scope,
            "CAPABILITY_QUERY",
        )

    def test_set_bits_are_classified_by_scope(self) -> None:
        data = bytearray(251)
        data[0] = 1 << 0
        data[28] = 1 << 4
        data[49] = 1 << 0
        data[50] = 1 << 2

        report = decode_supported_commands(bytes(data))

        self.assertEqual(report["set_bit_count"], 4)
        by_scope = report["supported_commands_by_scope"]
        self.assertIn("HCI_Inquiry", by_scope["OTHER_STANDARD"])
        self.assertIn(
            "HCI_LE_Receiver_Test [v1]",
            by_scope["PHY_TEST_CORE"],
        )
        self.assertIn(
            "HCI_Read_Local_Supported_Commands [v2]",
            by_scope["CAPABILITY_QUERY"],
        )
        self.assertIn("Reserved for future use", by_scope["RESERVED"])

    def test_console_support_flags_include_always_available_v1_query(self) -> None:
        data = bytearray(64)
        data[28] = 1 << 4
        support = support_for_commands(
            bytes(data),
            (
                "HCI_LE_Receiver_Test[v1]",
                "HCI_LE_Transmitter_Test[v1]",
                "HCI_Read_Local_Supported_Commands[v1]",
                "HCI_Read_Local_Supported_Commands[v2]",
            ),
        )

        self.assertTrue(support["HCI_LE_Receiver_Test[v1]"])
        self.assertFalse(support["HCI_LE_Transmitter_Test[v1]"])
        self.assertTrue(support["HCI_Read_Local_Supported_Commands[v1]"])
        self.assertFalse(support["HCI_Read_Local_Supported_Commands[v2]"])


if __name__ == "__main__":
    unittest.main()
