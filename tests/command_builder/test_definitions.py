"""Tests for Command Console command schemas."""

import unittest

from hci_analyzer.command_builder.definitions import (
    COMMAND_DEFINITIONS_BY_OPCODE,
    CONSOLE_COMMAND_DEFINITIONS,
    QUICK_COMMAND_DEFINITIONS,
    SELECTABLE_COMMAND_DEFINITIONS,
)


class CommandDefinitionTests(unittest.TestCase):
    def test_scope_contains_eleven_commands(self) -> None:
        self.assertEqual(len(CONSOLE_COMMAND_DEFINITIONS), 11)
        self.assertEqual(
            set(COMMAND_DEFINITIONS_BY_OPCODE),
            {
                0x201D,
                0x2033,
                0x204F,
                0x201E,
                0x2034,
                0x2050,
                0x207B,
                0x201F,
                0x0C03,
                0x1002,
                0x1010,
            },
        )

    def test_every_parameter_has_a_default(self) -> None:
        for definition in CONSOLE_COMMAND_DEFINITIONS:
            with self.subTest(command=definition.display_name):
                for parameter in definition.parameters:
                    self.assertIsNotNone(parameter.default)

    def test_reset_and_test_end_are_quick_commands_not_selectable(self) -> None:
        self.assertEqual(
            {item.opcode for item in QUICK_COMMAND_DEFINITIONS},
            {0x0C03, 0x201F},
        )
        selectable_opcodes = {
            item.opcode for item in SELECTABLE_COMMAND_DEFINITIONS
        }
        self.assertNotIn(0x0C03, selectable_opcodes)
        self.assertNotIn(0x201F, selectable_opcodes)

    def test_command_order_starts_with_transmitter_then_receiver(self) -> None:
        command_order = list(
            dict.fromkeys(
                definition.name for definition in SELECTABLE_COMMAND_DEFINITIONS
            )
        )
        self.assertEqual(
            command_order,
            [
                "HCI_LE_Transmitter_Test",
                "HCI_LE_Receiver_Test",
                "HCI_Read_Local_Supported_Commands",
            ],
        )


if __name__ == "__main__":
    unittest.main()
