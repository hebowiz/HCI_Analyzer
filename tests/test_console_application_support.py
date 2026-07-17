"""Tests for applying Controller capability results to the console."""

import unittest
from datetime import datetime
from unittest.mock import Mock

from hci_analyzer.command_builder.encoder import HciCommandEncoder
from hci_analyzer.console_application import HciCommandConsoleApplication
from hci_analyzer.command_builder.definitions import COMMAND_DEFINITIONS_BY_OPCODE
from hci_analyzer.models import ParseResult
from hci_analyzer.serial.transport import TransportEvent, TransportEventKind


class _WindowStub:
    def __init__(self) -> None:
        self.support: dict[int, bool] = {}
        self.values: dict[str, object] = {}
        self.on_form_shown = lambda _definition, _values: None
        self.busy = False
        self.response_timeout_seconds = 3.0

    def set_command_support(self, support: dict[int, bool]) -> None:
        self.support = dict(support)

    def append_transport_event(self, _event: object) -> None:
        return None

    def set_connected_state(self, _connected: bool) -> None:
        return None

    def set_busy_state(self, busy: bool) -> None:
        self.busy = busy

    def get_response_timeout_seconds(self) -> float:
        return self.response_timeout_seconds

    def get_parameter_values(self) -> dict[str, object]:
        return dict(self.values)

    def show_parameter_form(self, definition: object) -> None:
        parameters = getattr(definition, "parameters")
        self.values = {
            parameter.name: (
                list(parameter.default)
                if isinstance(parameter.default, tuple)
                else parameter.default
            )
            for parameter in parameters
        }
        self.on_form_shown(definition, dict(self.values))

    def set_parameter_values(self, values: dict[str, object]) -> None:
        self.values = dict(values)


class CommandConsoleSupportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = object.__new__(HciCommandConsoleApplication)
        self.application._command_support = {}
        self.application._parameter_value_cache = {}
        self.application._shared_parameter_values = {}
        self.application._selected_definition = None
        self.application._window = _WindowStub()

    def test_successful_capability_response_updates_console_commands(self) -> None:
        supported = bytearray(64)
        supported[5] = 1 << 7
        supported[28] = (1 << 4) | (1 << 6)
        parsed = ParseResult(
            True,
            "HCI_Event",
            b"",
            decoded={
                "response_type": "Supported_Commands",
                "status": 0,
                "supported_commands": list(supported),
            },
        )

        self.application._apply_supported_commands(parsed)

        self.assertTrue(self.application._command_support[0x201D])
        self.assertTrue(self.application._command_support[0x0C03])
        self.assertFalse(self.application._command_support[0x201E])
        self.assertTrue(self.application._command_support[0x201F])
        self.assertTrue(self.application._command_support[0x1002])
        self.assertFalse(self.application._command_support[0x1010])
        self.assertEqual(
            self.application._window.support,
            self.application._command_support,
        )

    def test_explicit_reset_removes_previous_capability_result(self) -> None:
        self.application._command_support = {0x201D: False}
        self.application._clear_command_support()

        self.assertEqual(self.application._command_support, {})
        self.assertEqual(self.application._window.support, {})

    def test_quick_reset_is_sent_without_changing_selected_command(self) -> None:
        self.application._encoder = HciCommandEncoder()
        self.application._transport = Mock()
        selected = COMMAND_DEFINITIONS_BY_OPCODE[0x2034]
        self.application._selected_definition = selected

        self.application._send_quick_command(0x0C03)

        self.application._transport.send.assert_called_once_with(
            bytes.fromhex("01 03 0C 00"),
            expected_opcode=0x0C03,
            response_timeout_seconds=3.0,
        )
        self.assertIs(self.application._selected_definition, selected)
        self.assertTrue(self.application._window.busy)

    def test_quick_test_end_sends_parameterless_command(self) -> None:
        self.application._encoder = HciCommandEncoder()
        self.application._transport = Mock()

        self.application._send_quick_command(0x201F)

        self.application._transport.send.assert_called_once_with(
            bytes.fromhex("01 1F 20 00"),
            expected_opcode=0x201F,
            response_timeout_seconds=3.0,
        )
        self.assertTrue(self.application._window.busy)

    def test_selected_timeout_is_applied_immediately_to_next_send(self) -> None:
        self.application._encoder = HciCommandEncoder()
        self.application._transport = Mock()
        self.application._window.response_timeout_seconds = 1.0

        self.application._send_quick_command(0x0C03)

        self.application._transport.send.assert_called_once_with(
            bytes.fromhex("01 03 0C 00"),
            expected_opcode=0x0C03,
            response_timeout_seconds=1.0,
        )

    def test_port_connection_events_do_not_reset_capability_result(self) -> None:
        self.application._command_support = {0x201D: False}
        for kind in (
            TransportEventKind.CONNECTED,
            TransportEventKind.DISCONNECTED,
        ):
            self.application._handle_transport_event(
                TransportEvent(
                    timestamp=datetime.now().astimezone(),
                    kind=kind,
                    source="Test",
                )
            )

        self.assertEqual(self.application._command_support, {0x201D: False})

    def test_command_parameters_are_restored_after_switching_commands(self) -> None:
        self.application._window.on_form_shown = (
            self.application._remember_parameter_values
        )
        transmitter_v3 = COMMAND_DEFINITIONS_BY_OPCODE[0x2050]
        self.application._select_command(transmitter_v3.opcode)
        self.application._window.values.update(
            {
                "TX_Channel": "7",
                "PHY": 0x03,
                "Antenna_IDs": ["3", "4", "5"],
            }
        )

        self.application._select_command(0x2033)
        self.application._select_command(transmitter_v3.opcode)

        self.assertEqual(self.application._window.values["TX_Channel"], "7")
        self.assertEqual(self.application._window.values["PHY"], 0x03)
        self.assertEqual(
            self.application._window.values["Antenna_IDs"],
            ["3", "4", "5"],
        )

    def test_common_parameters_are_shared_between_transmitter_versions(self) -> None:
        self.application._select_command(0x2034)
        self.application._window.values.update(
            {
                "TX_Channel": "7",
                "Test_Data_Length": "100",
                "Packet_Payload": 0x03,
                "PHY": 0x02,
            }
        )

        self.application._select_command(0x207B)

        self.assertEqual(self.application._window.values["TX_Channel"], "7")
        self.assertEqual(
            self.application._window.values["Test_Data_Length"], "100"
        )
        self.assertEqual(self.application._window.values["Packet_Payload"], 0x03)
        self.assertEqual(self.application._window.values["PHY"], 0x02)
        self.assertEqual(self.application._window.values["TX_Power_Mode"], 0)

    def test_common_parameters_are_shared_between_receiver_versions(self) -> None:
        self.application._select_command(0x2033)
        self.application._window.values.update(
            {
                "RX_Channel": "12",
                "PHY": 0x03,
                "Modulation_Index": 0x01,
            }
        )

        self.application._select_command(0x204F)

        self.assertEqual(self.application._window.values["RX_Channel"], "12")
        self.assertEqual(self.application._window.values["PHY"], 0x03)
        self.assertEqual(
            self.application._window.values["Modulation_Index"], 0x01
        )

    def test_same_parameter_name_is_not_shared_between_command_families(self) -> None:
        self.application._select_command(0x2034)
        self.application._window.values["PHY"] = 0x02

        self.application._select_command(0x2033)

        self.assertEqual(self.application._window.values["PHY"], 0x01)

    def test_version_specific_values_survive_shared_parameter_updates(self) -> None:
        self.application._select_command(0x207B)
        self.application._window.values.update(
            {
                "CTE_Length": "10",
                "Antenna_IDs": ["1", "2", "3"],
                "TX_Power_Mode": 0x02,
                "TX_Power_Level": "-5",
            }
        )

        self.application._select_command(0x2050)
        self.assertEqual(self.application._window.values["CTE_Length"], "10")
        self.assertEqual(
            self.application._window.values["Antenna_IDs"],
            ["1", "2", "3"],
        )
        self.application._window.values["CTE_Length"] = "4"

        self.application._select_command(0x207B)

        self.assertEqual(self.application._window.values["CTE_Length"], "4")
        self.assertEqual(self.application._window.values["TX_Power_Mode"], 0x02)
        self.assertEqual(self.application._window.values["TX_Power_Level"], "-5")


if __name__ == "__main__":
    unittest.main()
