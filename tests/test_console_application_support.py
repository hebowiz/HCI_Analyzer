"""Tests for applying Controller capability results to the console."""

import unittest
from datetime import datetime

from hci_analyzer.console_application import HciCommandConsoleApplication
from hci_analyzer.models import ParseResult
from hci_analyzer.serial.transport import TransportEvent, TransportEventKind


class _WindowStub:
    def __init__(self) -> None:
        self.support: dict[int, bool] = {}

    def set_command_support(self, support: dict[int, bool]) -> None:
        self.support = dict(support)

    def append_transport_event(self, _event: object) -> None:
        return None

    def set_connected_state(self, _connected: bool) -> None:
        return None

    def set_busy_state(self, _busy: bool) -> None:
        return None


class CommandConsoleSupportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = object.__new__(HciCommandConsoleApplication)
        self.application._command_support = {}
        self.application._window = _WindowStub()

    def test_successful_capability_response_updates_console_commands(self) -> None:
        supported = bytearray(64)
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


if __name__ == "__main__":
    unittest.main()
