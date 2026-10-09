"""Fixed-length RAW fields from Discovery through Console encoding."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from hci_analyzer.command_builder.encoder import HciCommandEncoder
from hci_analyzer.command_builder.raw_bytes import parse_raw_bytes
from hci_analyzer.gui.command_console import _format_parameter_input
from hci_analyzer.gui.vendor_discovery import VendorDiscoveryWindow
from hci_analyzer.vendor.console_definitions import (
    decode_vendor_command_complete, decode_vendor_parameters,
)
from hci_analyzer.vendor.project import (
    UserParameter, VendorDiscoveryProject, build_console_definition,
    load_project, save_project,
)
from tests.vendor.test_console_definitions import _capture, _load_payload


def raw_project(default=""):
    field = UserParameter("blob", "Blob", kind="raw_bytes", default=default)
    return VendorDiscoveryProject(0xFC41, "Vendor_Bytes", [field])


def raw_payload(size=4):
    project = raw_project()
    project.set_manual_layout("blob", 1, "raw_bytes", size + 2, size=size)
    return build_console_definition(project, [_capture(1, "AA " + "00 " * size + "FF")])


class RawBytesTests(unittest.TestCase):
    def test_manual_export_encode_and_decode_preserve_wire_order(self):
        project = raw_project("00abcdef")
        project.set_manual_layout("blob", 1, "raw_bytes", 6, size=4)
        payload = build_console_definition(project, [_capture(1, "AA 01 02 03 04 FF")])
        field = payload["commands"][0]["parameters"][0]
        self.assertEqual(field["default"], "00 AB CD EF")
        self.assertEqual(field["size"], 4)
        definition = _load_payload(payload).definitions[0]
        encoded = HciCommandEncoder().encode(definition, {})
        self.assertEqual(encoded.frame, bytes.fromhex("01 41 FC 06 AA 00 AB CD EF FF"))
        self.assertEqual(encoded.parameter_values["blob"], "00 AB CD EF")
        self.assertEqual(decode_vendor_parameters(definition, encoded.parameters)["blob"], "00 AB CD EF")
        edited = HciCommandEncoder().encode(definition, {"blob": "10 20 00 ff"})
        self.assertEqual(edited.parameters, bytes.fromhex("AA 10 20 00 FF FF"))

    def test_empty_default_uses_captured_bytes(self):
        project = raw_project()
        project.set_manual_layout("blob", 1, "raw_bytes", 4, size=2)
        payload = build_console_definition(project, [_capture(1, "AA 00 10 FF")])
        self.assertEqual(payload["commands"][0]["parameters"][0]["default"], "00 10")
        del payload["commands"][0]["parameters"][0]["default"]
        self.assertEqual(_load_payload(payload).definitions[0].parameters[0].default, "00 10")

    def test_single_byte_hex_is_not_reinterpreted_as_decimal(self):
        definition = _load_payload(raw_payload(1)).definitions[0]
        field = definition.parameters[0]
        self.assertEqual(_format_parameter_input(field, "10"), "10")
        self.assertEqual(HciCommandEncoder().encode(definition, {"blob": "10"}).parameters, b"\xAA\x10\xFF")

    def test_large_byte_array_and_maximum_hci_length(self):
        for size in (16, 32, 255):
            with self.subTest(size=size):
                project = raw_project()
                project.set_manual_layout("blob", 0, "raw_bytes", size, size=size)
                raw = bytes(range(size))
                payload = build_console_definition(project, [_capture(1, raw.hex())])
                definition = _load_payload(payload).definitions[0]
                self.assertEqual(HciCommandEncoder().encode(definition, {}).parameters, raw)

    def test_invalid_sizes_are_rejected_in_project_and_json(self):
        for size in (None, 0, -1, True, 1.5, "4", 256):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    raw_project().set_manual_layout("blob", 0, "raw_bytes", 255, size=size)
                payload = raw_payload()
                payload["commands"][0]["parameters"][0]["size"] = size
                with self.assertRaises(ValueError):
                    _load_payload(payload)

    def test_invalid_hex_and_wrong_length_are_rejected(self):
        definition = _load_payload(raw_payload()).definitions[0]
        for value in ("01", "00 01 02 03 04", "0x00112233", "G0 00 00 00", "0011223", "", 123, [0, 1, 2, 3]):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    HciCommandEncoder().encode(definition, {"blob": value})
        self.assertEqual(parse_raw_bytes("00ab\tcd\nef", 4), b"\x00\xAB\xCD\xEF")
        self.assertEqual(parse_raw_bytes(b"\x00\xFF", 2), b"\x00\xFF")
        with self.assertRaises(ValueError):
            raw_project("00 01").set_manual_layout("blob", 0, "raw_bytes", 4, size=4)

    def test_bounds_and_overlap_rejection_restore_previous_layout(self):
        project = raw_project()
        project.set_manual_layout("blob", 1, "raw_bytes", 6, size=4)
        old = dict(project.parameters[0].confirmed_candidate)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            project.set_manual_layout("blob", 3, "raw_bytes", 6, size=4)
        self.assertEqual(project.parameters[0].confirmed_candidate, old)
        project.add_parameter(UserParameter("mode", "Mode", kind="unsigned"))
        with self.assertRaisesRegex(ValueError, "overlap"):
            project.set_manual_layout("mode", 2, "uint8", 6)
        self.assertIsNone(project.parameters[1].confirmed_candidate)
        for offset in (2, 5):
            payload = raw_payload()
            payload["commands"][0]["parameters"].append({"name": "other", "offset": offset, "type": "raw_bytes", "size": 2})
            with self.assertRaises(ValueError):
                _load_payload(payload)

    def test_project_round_trip_keeps_size_and_default(self):
        project = raw_project("00 ab cd ef")
        project.set_manual_layout("blob", 1, "raw_bytes", 6, size=4)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            save_project(path, project, [])
            loaded, _ = load_project(path)
        self.assertEqual(loaded.parameters[0], project.parameters[0])

    def test_raw_command_complete_response_and_overlap_validation(self):
        payload = raw_payload()
        payload["commands"][0]["response"] = {
            "kind": "command_complete", "parameter_length": 5,
            "parameters": [
                {"name": "status", "offset": 0, "type": "uint8"},
                {"name": "result", "offset": 1, "type": "raw_bytes", "size": 4},
            ],
        }
        definition = _load_payload(payload).definitions[0]
        decoded = decode_vendor_command_complete(definition, bytes.fromhex("00 00 AB CD EF"))
        self.assertEqual(decoded["result"], "00 AB CD EF")
        self.assertEqual(decoded["status"], 0)
        self.assertIn("decode_error", decode_vendor_command_complete(definition, b"\x00"))
        payload["commands"][0]["response"]["parameters"][1]["offset"] = 0
        with self.assertRaisesRegex(ValueError, "overlap"):
            _load_payload(payload)

    def test_gui_manual_layout_passes_size_and_analysis_preserves_it(self):
        project = raw_project()
        window = object.__new__(VendorDiscoveryWindow)
        window._root = Mock()
        window._current_project = Mock(return_value=project)
        window._selected_parameter = Mock(return_value=project.parameters[0])
        window._store = Mock()
        window._store.vendor_captures.return_value = [_capture(1, "AA 00 01 02 03 FF")]
        window._refresh_parameter_tree = Mock()
        window._status_variable = Mock()
        window._set_report = Mock()
        with patch("hci_analyzer.gui.vendor_discovery._ManualLayoutDialog") as dialog:
            dialog.return_value.show.return_value = (1, "raw_bytes", 4)
            window._set_manual_layout()
        self.assertEqual(project.parameters[0].confirmed_candidate["size"], 4)
        previous = dict(project.parameters[0].confirmed_candidate)
        window._analyze_parameter()
        self.assertEqual(project.parameters[0].confirmed_candidate, previous)
        self.assertTrue(window._set_report.call_args.args[0].isascii())

    def test_gui_draft_preserves_confirmed_raw_field(self):
        project = raw_project()
        project.set_manual_layout("blob", 1, "raw_bytes", 6, size=4)
        window = object.__new__(VendorDiscoveryWindow)
        window._current_project = Mock(return_value=project)
        window._store = Mock()
        window._store.vendor_captures.return_value = [_capture(1, "AA 00 01 02 03 FF")]
        window._sync_project_name = Mock()
        window._save_definition_payload = Mock()
        window._export_draft()
        payload = window._save_definition_payload.call_args.args[0]
        definition = _load_payload(payload).definitions[0]
        self.assertEqual(HciCommandEncoder().encode(definition, {}).parameters, bytes.fromhex("AA 00 01 02 03 FF"))
