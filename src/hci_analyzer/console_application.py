"""Top-level coordination for the HCI Command Console."""

from __future__ import annotations

import queue
from datetime import datetime
from typing import Any, Mapping

from hci_analyzer.command_builder.definitions import (
    COMMAND_DEFINITIONS_BY_OPCODE,
    CONSOLE_COMMAND_DEFINITIONS,
    SELECTABLE_COMMAND_DEFINITIONS,
    ConsoleCommandDefinition,
)
from hci_analyzer.command_builder.encoder import EncodedCommand, HciCommandEncoder
from hci_analyzer.command_builder.validation import CommandValidator
from hci_analyzer.console_settings import (
    CommandConsoleSettings,
    CommandConsoleSettingsStore,
)
from hci_analyzer.gui.command_console import CommandConsoleWindow
from hci_analyzer.models import ParseResult, SerialPortConfig
from hci_analyzer.parser.facade import HciParser
from hci_analyzer.parser.supported_commands import support_for_commands
from hci_analyzer.presentation.text import format_exception_for_log
from hci_analyzer.serial.ports import list_serial_ports
from hci_analyzer.serial.transport import (
    HciSerialTransport,
    TransportEvent,
    TransportEventKind,
)
from hci_analyzer.vendor.console_definitions import (
    decode_vendor_parameters,
    load_vendor_console_definitions,
)


class HciCommandConsoleApplication:
    """Compose command selection, encoding, serial transport, and logging UI."""

    def __init__(self) -> None:
        self._parser = HciParser()
        self._validator = CommandValidator()
        self._encoder = HciCommandEncoder(self._validator, self._parser)
        self._transport_events: queue.Queue[TransportEvent] = queue.Queue()
        self._transport = HciSerialTransport(self._transport_events.put, self._parser)
        self._settings_store = CommandConsoleSettingsStore()
        self._saved_settings = self._settings_store.load()
        self._window = CommandConsoleWindow(
            on_connect=self._connect,
            on_disconnect=self._disconnect,
            on_command_selected=self._select_command,
            on_preview=self._preview,
            on_send=self._send,
            on_quick_send=self._send_quick_command,
            on_clear_log=lambda: None,
            on_reset=self._reset_current_values,
            on_reset_command_support=self._clear_command_support,
            on_load_vendor_definitions=self._load_vendor_definitions,
        )
        self._window.set_refresh_handler(self._refresh_ports)
        self._window.set_close_handler(self._close)
        self._selected_definition: ConsoleCommandDefinition | None = None
        self._parameter_value_cache: dict[int, dict[str, Any]] = {}
        self._shared_parameter_values: dict[str, dict[str, Any]] = {}
        self._latest_encoded: EncodedCommand | None = None
        self._command_support: dict[int, bool] = {}
        self._definitions_by_opcode = dict(COMMAND_DEFINITIONS_BY_OPCODE)
        self._selectable_definitions = list(SELECTABLE_COMMAND_DEFINITIONS)

    def run(self) -> None:
        """Start the Command Console event loop."""
        self._refresh_ports(self._saved_settings.port)
        self._window.set_baud_rate(self._saved_settings.baud_rate)
        self._window.set_response_timeout_seconds(
            self._saved_settings.response_timeout_seconds
        )
        self._window.set_window_size(
            self._saved_settings.window_width,
            self._saved_settings.window_height,
        )
        self._window.set_command_definitions(tuple(self._selectable_definitions))
        self._window.after(50, self._drain_transport_events)
        self._window.run()

    def _refresh_ports(self, preferred_port: str | None = None) -> None:
        try:
            self._window.set_serial_ports(list_serial_ports(), preferred_port)
        except Exception as exc:
            self._append_application_error(
                f"Port enumeration failed: {format_exception_for_log(exc)}"
            )

    def _select_command(self, opcode: int) -> None:
        self._cache_current_values()
        definition = self._definitions_by_opcode[opcode]
        values = self._values_for_definition(definition)
        self._selected_definition = definition
        self._window.show_parameter_form(definition)
        self._window.set_parameter_values(values)

    def _preview(self, values: Mapping[str, Any]) -> None:
        definition = self._selected_definition
        if definition is None:
            return
        self._remember_parameter_values(definition, values)
        validation = self._validator.validate(definition, values)
        issues: dict[str, str] = {}
        for issue in validation.issues:
            key = issue.parameter_name or "__command__"
            issues.setdefault(key, issue.message)
        self._window.show_validation_issues(issues)
        if not validation.valid:
            self._latest_encoded = None
            self._window.show_packet_preview(b"")
            return
        try:
            encoded = self._encoder.encode(definition, validation.normalized_values)
        except ValueError as exc:
            self._latest_encoded = None
            self._window.show_validation_issues({"__command__": str(exc)})
            self._window.show_packet_preview(b"")
            return
        self._latest_encoded = encoded
        self._window.show_packet_preview(encoded.frame)

    def _connect(self) -> None:
        port = ""
        try:
            port, baud_rate = self._window.get_connection_settings()
            if not port:
                raise ValueError("シリアルポートを選択してください")
            self._transport.connect(
                SerialPortConfig(port, baud_rate, f"Console:{port}")
            )
        except Exception as exc:
            target = port or "no port selected"
            self._append_application_error(
                f"Connection failed: {target}; {format_exception_for_log(exc)}"
            )

    def _disconnect(self) -> None:
        self._transport.disconnect()

    def _send(self, values: Mapping[str, Any]) -> None:
        definition = self._selected_definition
        if definition is None:
            return
        self._preview(values)
        encoded = self._latest_encoded
        if encoded is None:
            return
        self._submit_encoded(definition, encoded)

    def _send_quick_command(self, opcode: int) -> None:
        definition = self._definitions_by_opcode.get(opcode)
        if definition is None or opcode not in (0x0C03, 0x201F):
            self._append_application_error(
                f"Unknown quick command opcode 0x{opcode:04X}"
            )
            return
        try:
            encoded = self._encoder.encode(definition, {})
        except ValueError as exc:
            self._append_application_error(
                f"Quick command encoding failed: {format_exception_for_log(exc)}"
            )
            return
        self._submit_encoded(definition, encoded)

    def _submit_encoded(
        self,
        definition: ConsoleCommandDefinition,
        encoded: EncodedCommand,
    ) -> None:
        if self._command_support.get(definition.opcode) is False:
            self._append_application_error(
                f"{definition.display_name} is not supported by the Controller"
            )
            return
        try:
            timeout_seconds = self._window.get_response_timeout_seconds()
            self._transport.send(
                encoded.frame,
                expected_opcode=definition.opcode,
                response_timeout_seconds=timeout_seconds,
            )
        except Exception as exc:
            self._append_application_error(
                f"Send request failed: {format_exception_for_log(exc)}"
            )
            return
        self._window.set_busy_state(True)

    def _reset_current_values(self) -> None:
        definition = self._selected_definition
        if definition is None:
            return
        defaults = self._defaults(definition)
        self._remember_parameter_values(definition, defaults)
        self._window.set_parameter_values(defaults)

    def _cache_current_values(self) -> None:
        definition = self._selected_definition
        if definition is None:
            return
        self._remember_parameter_values(
            definition,
            self._window.get_parameter_values(),
        )

    def _values_for_definition(
        self, definition: ConsoleCommandDefinition
    ) -> dict[str, Any]:
        values = self._defaults(definition)
        values.update(
            self._copy_parameter_values(
                self._parameter_value_cache.get(definition.opcode, {})
            )
        )
        shared = self._shared_parameter_values.get(definition.name, {})
        parameter_names = {parameter.name for parameter in definition.parameters}
        values.update(
            self._copy_parameter_values(
                {
                    name: value
                    for name, value in shared.items()
                    if name in parameter_names
                }
            )
        )
        return values

    def _remember_parameter_values(
        self,
        definition: ConsoleCommandDefinition,
        values: Mapping[str, Any],
    ) -> None:
        copied = self._copy_parameter_values(values)
        self._parameter_value_cache[definition.opcode] = copied
        parameter_names = {parameter.name for parameter in definition.parameters}
        shared = self._shared_parameter_values.setdefault(definition.name, {})
        shared.update(
            self._copy_parameter_values(
                {
                    name: value
                    for name, value in copied.items()
                    if name in parameter_names
                }
            )
        )

    def _drain_transport_events(self) -> None:
        while True:
            try:
                event = self._transport_events.get_nowait()
            except queue.Empty:
                break
            self._handle_transport_event(event)
        self._window.after(50, self._drain_transport_events)

    def _handle_transport_event(self, event: TransportEvent) -> None:
        if event.parsed is not None:
            self._apply_external_command_name(event.parsed)
        self._window.append_transport_event(event)
        if event.kind == TransportEventKind.CONNECTED:
            self._window.set_connected_state(True)
        elif event.kind == TransportEventKind.DISCONNECTED:
            self._window.set_connected_state(False)
            self._window.set_busy_state(False)
        elif event.kind == TransportEventKind.RESPONSE_TIMEOUT:
            self._window.set_busy_state(False)
        elif event.kind == TransportEventKind.ERROR and event.transaction_id is not None:
            self._window.set_busy_state(False)
        elif event.kind == TransportEventKind.RECEIVED and event.transaction_id is not None:
            parsed = event.parsed
            if parsed is None:
                return
            self._apply_supported_commands(parsed)
            event_name = parsed.decoded.get("event_name")
            status = parsed.decoded.get("status")
            if event_name == "HCI_Command_Complete" or (
                event_name == "HCI_Command_Status" and status != 0
            ):
                self._window.set_busy_state(False)

    def _apply_external_command_name(self, parsed: ParseResult) -> None:
        if not parsed.success:
            return
        decoded = parsed.decoded
        raw_opcode = decoded.get("opcode_value")
        if not isinstance(raw_opcode, int):
            raw_opcode = decoded.get("command_opcode_value")
        if not isinstance(raw_opcode, int):
            return
        definition = self._definitions_by_opcode.get(raw_opcode)
        if definition is None or not definition.vendor_specific:
            return
        decoded["command_name"] = definition.display_name
        if parsed.packet_type == "HCI_Command":
            decoded["display_name"] = definition.display_name
            parameters = parsed.raw_data[4:]
            decoded["parameters"] = decode_vendor_parameters(
                definition,
                parameters,
            )

    def _apply_supported_commands(self, parsed: ParseResult) -> None:
        if not parsed.success:
            return
        decoded = parsed.decoded
        if (
            decoded.get("response_type") != "Supported_Commands"
            or decoded.get("status") != 0
        ):
            return
        raw_values = decoded.get("supported_commands")
        if not isinstance(raw_values, list):
            return
        supported_commands = bytes(raw_values)
        names = [
            definition.display_name
            for definition in CONSOLE_COMMAND_DEFINITIONS
        ]
        by_name = support_for_commands(supported_commands, names)
        self._command_support = {
            definition.opcode: by_name[definition.display_name]
            for definition in CONSOLE_COMMAND_DEFINITIONS
        }
        self._window.set_command_support(self._command_support)

    def _clear_command_support(self) -> None:
        self._command_support.clear()
        self._window.set_command_support({})

    def _load_vendor_definitions(self) -> None:
        paths = self._window.choose_vendor_definition_files()
        if not paths:
            return
        loaded_definitions: list[ConsoleCommandDefinition] = []
        review_names: list[str] = []
        seen_opcodes: set[int] = set()
        try:
            for path in paths:
                loaded = load_vendor_console_definitions(path)
                for definition in loaded.definitions:
                    if definition.opcode in COMMAND_DEFINITIONS_BY_OPCODE:
                        raise ValueError(
                            f"Vendor definition cannot replace built-in opcode "
                            f"0x{definition.opcode:04X}"
                        )
                    if definition.opcode in seen_opcodes:
                        raise ValueError(
                            f"Duplicate vendor opcode 0x{definition.opcode:04X} "
                            "across selected files"
                        )
                    seen_opcodes.add(definition.opcode)
                    loaded_definitions.append(definition)
                    if definition.review_required:
                        review_names.append(
                            f"{definition.display_name} "
                            f"(0x{definition.opcode:04X})"
                        )
            retained = [
                item
                for item in self._selectable_definitions
                if item.opcode not in seen_opcodes
            ]
            selection_keys: set[tuple[str, str, str | None]] = set()
            for definition in (*retained, *loaded_definitions):
                key = (
                    definition.category,
                    definition.name,
                    definition.version,
                )
                if key in selection_keys:
                    raise ValueError(
                        "Duplicate command selection name: "
                        f"{definition.display_name}"
                    )
                selection_keys.add(key)
        except ValueError as exc:
            self._append_application_error(
                f"Vendor definition load failed: {format_exception_for_log(exc)}"
            )
            return
        if review_names and not self._window.confirm_review_required_definitions(
            review_names
        ):
            self._append_application_message(
                "Vendor definition loading was cancelled"
            )
            return

        replaced_opcodes = {item.opcode for item in loaded_definitions}
        self._selectable_definitions = [
            item
            for item in self._selectable_definitions
            if item.opcode not in replaced_opcodes
        ]
        self._selectable_definitions.extend(loaded_definitions)
        for definition in loaded_definitions:
            self._definitions_by_opcode[definition.opcode] = definition
            self._parameter_value_cache.pop(definition.opcode, None)
            self._shared_parameter_values.pop(definition.name, None)
        self._window.set_command_definitions(tuple(self._selectable_definitions))
        self._append_application_message(
            f"Loaded {len(loaded_definitions)} vendor command definition(s)"
        )

    def _append_application_error(self, message: str) -> None:
        self._window.append_transport_event(
            TransportEvent(
                timestamp=datetime.now().astimezone(),
                kind=TransportEventKind.ERROR,
                source="Application",
                message=message,
            )
        )

    def _append_application_message(self, message: str) -> None:
        self._window.append_transport_event(
            TransportEvent(
                timestamp=datetime.now().astimezone(),
                kind=TransportEventKind.SYSTEM,
                source="Application",
                message=message,
            )
        )

    def _close(self) -> None:
        try:
            port, baud_rate = self._window.get_connection_settings()
            response_timeout_seconds = int(
                self._window.get_response_timeout_seconds()
            )
            width, height = self._window.get_window_size()
            self._settings_store.save(
                CommandConsoleSettings(
                    port=port,
                    baud_rate=baud_rate,
                    response_timeout_seconds=response_timeout_seconds,
                    window_width=width,
                    window_height=height,
                )
            )
        except Exception as exc:
            self._append_application_error(
                f"Settings save failed: {format_exception_for_log(exc)}"
            )
        self._transport.disconnect()
        self._window.destroy()

    @staticmethod
    def _defaults(definition: ConsoleCommandDefinition) -> dict[str, Any]:
        return {
            parameter.name: (
                list(parameter.default)
                if isinstance(parameter.default, tuple)
                else parameter.default
            )
            for parameter in definition.parameters
        }

    @staticmethod
    def _copy_parameter_values(values: Mapping[str, Any]) -> dict[str, Any]:
        return {
            name: list(value) if isinstance(value, (list, tuple)) else value
            for name, value in values.items()
        }
