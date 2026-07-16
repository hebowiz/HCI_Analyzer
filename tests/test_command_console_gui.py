"""Logic tests for Command Console selection defaults."""

import unittest

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


if __name__ == "__main__":
    unittest.main()
