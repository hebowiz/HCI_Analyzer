"""Logic tests for Command Console selection defaults."""

import unittest
from unittest.mock import Mock, patch

from hci_analyzer.command_builder.definitions import COMMAND_DEFINITIONS_BY_OPCODE
from hci_analyzer.gui.command_console import CommandConsoleWindow


class CommandConsoleWindowTests(unittest.TestCase):
    def test_v2_is_preferred_when_available(self) -> None:
        self.assertEqual(
            CommandConsoleWindow._preferred_version(
                "HCI_LE_Transmitter_Test",
                ["v1", "v2", "v3"],
            ),
            "v2",
        )

    def test_supported_commands_query_prefers_v1(self) -> None:
        self.assertEqual(
            CommandConsoleWindow._preferred_version(
                "HCI_Read_Local_Supported_Commands",
                ["v1", "v2"],
            ),
            "v1",
        )

    def test_first_version_is_used_when_v2_is_unavailable(self) -> None:
        self.assertEqual(
            CommandConsoleWindow._preferred_version(
                "HCI_LE_Test_End",
                ["none"],
            ),
            "none",
        )

    @patch("hci_analyzer.gui.command_console.messagebox.askyesno")
    def test_reset_send_requires_confirmation(self, ask_yes_no: Mock) -> None:
        window = object.__new__(CommandConsoleWindow)
        window._current_definition = COMMAND_DEFINITIONS_BY_OPCODE[0x0C03]
        window._root = Mock()
        window._on_send = Mock()
        window.get_parameter_values = Mock(return_value={})
        ask_yes_no.return_value = False

        window._request_send()

        window._on_send.assert_not_called()
        ask_yes_no.return_value = True
        window._request_send()
        window._on_send.assert_called_once_with({})


if __name__ == "__main__":
    unittest.main()
