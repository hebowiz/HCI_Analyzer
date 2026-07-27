"""Logic tests for Command Console selection defaults."""

import tkinter as tk
import unittest

from types import SimpleNamespace
from unittest.mock import Mock

from hci_analyzer.command_builder.definitions import (
    COMMAND_DEFINITIONS_BY_OPCODE,
    ParameterDefinition,
    ParameterKind,
)
from hci_analyzer.gui.command_console import (
    CommandConsoleWindow,
    _format_parameter_description,
    _format_parameter_input,
    _parameter_grid_position,
    _parameter_label_width,
)


class CommandConsoleWindowTests(unittest.TestCase):
    def test_even_parameters_fill_left_column_then_right_column(self) -> None:
        self.assertEqual(
            [_parameter_grid_position(index, 6) for index in range(6)],
            [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)],
        )

    def test_odd_parameters_put_one_more_in_left_column(self) -> None:
        self.assertEqual(
            [_parameter_grid_position(index, 5) for index in range(5)],
            [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)],
        )

    def test_parameter_labels_share_the_longest_measured_width(self) -> None:
        parameters = (
            ParameterDefinition(
                name="short",
                label="PHY",
                kind=ParameterKind.INTEGER,
            ),
            ParameterDefinition(
                name="long",
                label="Modulation Index",
                kind=ParameterKind.INTEGER,
            ),
        )

        width = _parameter_label_width(
            parameters,
            lambda text: len(text) * 8,
        )

        self.assertEqual(width, len("Modulation Index") * 8)

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

    def test_command_selection_passes_the_exact_definition(self) -> None:
        definition = COMMAND_DEFINITIONS_BY_OPCODE[0x2034]
        window = object.__new__(CommandConsoleWindow)
        window._category_variable = Mock()
        window._command_variable = Mock()
        window._version_variable = Mock()
        window._category_variable.get.return_value = definition.category
        window._command_variable.get.return_value = definition.name
        window._version_variable.get.return_value = definition.version
        key = (definition.category, definition.name, definition.version)
        window._definition_lookup = {key: definition}
        window._on_command_selected = Mock()

        window._select_definition()

        window._on_command_selected.assert_called_once_with(definition)

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
        window._vendor_load_button = Mock()
        window._send_button = Mock()
        window._quick_reset_button = Mock()
        window._quick_test_end_button = Mock()

        window.set_busy_state(True)
        window._response_timeout_combo.configure.assert_called_with(
            state=tk.DISABLED
        )
        window._vendor_load_button.configure.assert_called_with(
            state=tk.DISABLED
        )

        window.set_busy_state(False)
        window._response_timeout_combo.configure.assert_called_with(
            state="readonly"
        )
        window._vendor_load_button.configure.assert_called_with(
            state=tk.NORMAL
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

    def test_hex_parameter_input_uses_type_size_and_prefix(self) -> None:
        parameter = ParameterDefinition(
            name="address",
            label="Address",
            kind=ParameterKind.INTEGER,
            size=6,
            default=0x00006BC6967E,
            number_format="hex",
        )

        self.assertEqual(
            _format_parameter_input(parameter, parameter.default),
            "0x00006BC6967E",
        )
        self.assertEqual(
            _format_parameter_input(parameter, "0x1234"),
            "0x000000001234",
        )

    def test_decimal_parameter_input_keeps_decimal_text(self) -> None:
        parameter = ParameterDefinition(
            name="channel",
            label="Channel",
            kind=ParameterKind.INTEGER,
            size=1,
            default=19,
        )

        self.assertEqual(_format_parameter_input(parameter, 19), "19")

    def test_parameter_description_calculates_from_current_value(self) -> None:
        self.assertEqual(
            _format_parameter_description(
                "Frequency = 2402 + value * 2",
                "19",
            ),
            "Frequency = 2402 + value * 2 \u2192 2440",
        )

    def test_parameter_description_supports_hexadecimal_input(self) -> None:
        self.assertEqual(
            _format_parameter_description("Result = value + 1", "0x0F"),
            "Result = value + 1 \u2192 16",
        )

    def test_parameter_description_does_not_execute_unsafe_expression(
        self,
    ) -> None:
        description = "Result = __import__('os').system(value)"

        self.assertEqual(
            _format_parameter_description(description, "1"),
            description,
        )

    def test_parameter_description_calculation_can_be_disabled(self) -> None:
        description = "Frequency = 2402 + value * 2"

        self.assertEqual(
            _format_parameter_description(
                description,
                "19",
                enable_calculation=False,
            ),
            description,
        )

if __name__ == "__main__":
    unittest.main()
