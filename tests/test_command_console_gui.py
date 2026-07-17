"""Logic tests for Command Console selection defaults."""

import tkinter as tk
import unittest

from types import SimpleNamespace
from unittest.mock import Mock

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

    def test_quick_buttons_do_not_require_a_valid_selected_preview(self) -> None:
        window = object.__new__(CommandConsoleWindow)
        window._connected = True
        window._busy = False
        window._preview_valid = False
        window._selected_command_supported = None
        window._command_support = {}
        window._send_button = Mock()
        window._quick_reset_button = Mock()
        window._quick_test_end_button = Mock()

        window._update_send_state()

        window._send_button.configure.assert_called_once_with(
            state=tk.DISABLED
        )
        window._quick_reset_button.configure.assert_called_once_with(
            state=tk.NORMAL
        )
        window._quick_test_end_button.configure.assert_called_once_with(
            state=tk.NORMAL
        )

    def test_timeout_selection_is_disabled_only_while_busy(self) -> None:
        window = object.__new__(CommandConsoleWindow)
        window._connected = True
        window._busy = False
        window._preview_valid = True
        window._selected_command_supported = None
        window._command_support = {}
        window._response_timeout_combo = Mock()
        window._send_button = Mock()
        window._quick_reset_button = Mock()
        window._quick_test_end_button = Mock()

        window.set_busy_state(True)
        window._response_timeout_combo.configure.assert_called_with(
            state=tk.DISABLED
        )

        window.set_busy_state(False)
        window._response_timeout_combo.configure.assert_called_with(
            state="readonly"
        )

    def test_mouse_wheel_scrolls_parameter_canvas_from_blank_area(self) -> None:
        window = object.__new__(CommandConsoleWindow)
        window._parameter_canvas = Mock()

        result = window._scroll_parameter_canvas(
            SimpleNamespace(num=None, delta=-120)
        )

        window._parameter_canvas.yview_scroll.assert_called_once_with(
            1,
            "units",
        )
        self.assertEqual(result, "break")

    def test_linux_wheel_button_scrolls_parameter_canvas(self) -> None:
        window = object.__new__(CommandConsoleWindow)
        window._parameter_canvas = Mock()

        window._scroll_parameter_canvas(SimpleNamespace(num=4, delta=0))

        window._parameter_canvas.yview_scroll.assert_called_once_with(
            -1,
            "units",
        )

if __name__ == "__main__":
    unittest.main()
