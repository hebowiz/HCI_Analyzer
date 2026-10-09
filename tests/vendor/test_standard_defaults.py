"""Standard HCI capture -> editable project -> Console JSON round trips."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from hci_analyzer.command_builder.definitions import CONSOLE_COMMAND_DEFINITIONS
from hci_analyzer.command_builder.encoder import HciCommandEncoder
from hci_analyzer.models import LogRecord, RecordKind, TrafficDirection
from hci_analyzer.parser.facade import HciParser
from hci_analyzer.serial.monitor import SerialPortWorker
from hci_analyzer.models import SerialPortConfig
from hci_analyzer.vendor.console_definitions import load_vendor_console_definitions
from hci_analyzer.vendor.discovery import load_vendor_captures
from hci_analyzer.vendor.live_capture import LiveCaptureStore
from hci_analyzer.vendor.project import (
    build_console_definition, load_project, save_project, parse_parameter_choices,
)
from hci_analyzer.vendor.standard_defaults import create_discovery_project


def capture_entry(raw: bytes):
    return LiveCaptureStore().add_record(LogRecord(
        timestamp=datetime.now(timezone.utc), source="Test",
        direction=TrafficDirection.HOST_TO_CONTROLLER, kind=RecordKind.PACKET,
        raw_data=raw, result=HciParser().parse_bytes(raw),
    ))


def load_payload(payload):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "definition.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return load_vendor_console_definitions(path).definitions[0]


class StandardDefaultsTests(unittest.TestCase):
    def test_all_builtin_commands_round_trip_including_variable_arrays(self):
        for builtin in CONSOLE_COMMAND_DEFINITIONS:
            with self.subTest(opcode=hex(builtin.opcode)):
                frame = HciCommandEncoder().encode(builtin, {}).frame
                capture = capture_entry(frame).vendor_capture
                project = create_discovery_project(capture)
                payload = build_console_definition(project, [capture])
                definition = load_payload(payload)
                self.assertEqual(definition.name, builtin.display_name)
                self.assertEqual(payload["commands"][0]["ogf"], builtin.opcode >> 10)
                self.assertEqual(HciCommandEncoder().encode(definition, {}).frame, frame)

    def test_enum_includes_uncaptured_choices_and_defaults_can_be_customized(self):
        entry = capture_entry(bytes.fromhex("01 34 20 04 13 25 00 02"))
        project = create_discovery_project(entry.vendor_capture)
        phy = project.parameter("PHY")
        self.assertEqual(phy.default, "2")
        self.assertEqual(phy.choice_values["LE Coded PHY with S=2"], 4)
        phy.default = "0x04"
        phy.number_format = "hex"
        phy.description = "My PHY"
        project.parameter("TX_Channel").default = "21"
        payload = build_console_definition(project, [entry.vendor_capture])
        fields = {field["name"]: field for field in payload["commands"][0]["parameters"]}
        self.assertEqual(fields["PHY"]["default"], "0x04")
        self.assertEqual(fields["PHY"]["choices"]["0x03"], "LE Coded PHY with S=8")
        definition = load_payload(payload)
        self.assertEqual(HciCommandEncoder().encode(definition, {}).frame,
                         bytes.fromhex("01 34 20 04 15 25 00 04"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            save_project(path, project, [entry])
            restored, entries = load_project(path)
        self.assertEqual(restored.parameter("PHY").default, "0x04")
        self.assertEqual(restored.parameter("PHY").choice_values, phy.choice_values)
        self.assertEqual(build_console_definition(restored, [entries[0].vendor_capture]), payload)

    def test_unknown_standard_opcode_gets_raw_editable_fields(self):
        frame = bytes.fromhex("01 01 20 02 00 80")
        capture = capture_entry(frame).vendor_capture
        project = create_discovery_project(capture)
        self.assertEqual(project.command_name, "HCI_Command_0x2001")
        self.assertEqual([p.default for p in project.parameters], ["0x00", "0x80"])
        project.command_name = "Custom_Standard"
        project.parameters[1].default = "0xFF"
        loaded = load_payload(build_console_definition(project, [capture]))
        self.assertEqual(HciCommandEncoder().encode(loaded, {}).frame,
                         bytes.fromhex("01 01 20 02 00 FF"))

    def test_legacy_jsonl_includes_standard_unknown_and_vendor_commands(self):
        frames = ["01 03 0C 00", "04 0E 04 01 03 0C 00", "01 01 20 01 AA",
                  "04 0F 04 00 01 01 20", "01 41 FC 00"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.jsonl"
            path.write_text("\n".join(json.dumps({"raw_data": raw}) for raw in frames),
                            encoding="utf-8")
            captures, errors = load_vendor_captures([path])
        self.assertEqual(errors, [])
        self.assertEqual([c.opcode for c in captures], [0x0C03, 0x2001, 0xFC41])
        self.assertEqual([len(c.responses) for c in captures], [1, 1, 0])

    def test_monitor_fragmented_standard_and_unknown_frames_reach_discovery(self):
        store = LiveCaptureStore()
        worker = SerialPortWorker(SerialPortConfig("COM1", 115200, "Test"), store.add_record)
        worker._process_bytes(bytes.fromhex("99 88 01 34 20"))
        worker._process_bytes(bytes.fromhex("04 13 25 00 02 01 01 20 01 AA"))
        self.assertEqual(store.vendor_opcodes(), (0x2001, 0x2034))

    def test_editable_enum_values_and_invalid_defaults(self):
        labels, values = parse_parameter_choices("0x01=One, 03=Three")
        self.assertEqual(labels, ["One", "Three"])
        self.assertEqual(values, {"One": 1, "Three": 3})
        capture = capture_entry(bytes.fromhex("01 34 20 04 13 25 00 02")).vendor_capture
        project = create_discovery_project(capture)
        project.parameter("PHY").default = "255"
        with self.assertRaisesRegex(ValueError, "enum choice"):
            build_console_definition(project, [capture])
        project.parameter("PHY").default = "256"
        with self.assertRaisesRegex(ValueError, "outside"):
            build_console_definition(project, [capture])

    def test_explicit_enum_value_replaces_captured_value_for_the_same_label(self):
        capture = capture_entry(bytes.fromhex("01 34 20 04 13 25 00 02")).vendor_capture
        project = create_discovery_project(capture)
        phy = project.parameter("PHY")
        capture.annotations["PHY"] = "LE 2M PHY"
        phy.choice_values["LE 2M PHY"] = 10
        phy.default = "10"
        definition = load_payload(build_console_definition(project, [capture]))
        field = next(p for p in definition.parameters if p.name == "PHY")
        self.assertNotIn(2, field.choices)
        self.assertEqual(field.choices[10], "LE 2M PHY")
        self.assertEqual(HciCommandEncoder().encode(definition, {}).frame[-1], 10)

    def test_v4_special_power_and_array_tail_keep_correct_wire_offsets(self):
        frame = bytes.fromhex("01 7B 20 0B 13 25 00 01 02 01 03 04 05 06 7F")
        capture = capture_entry(frame).vendor_capture
        project = create_discovery_project(capture)
        self.assertIsNone(project.parameter("TX_Power_Mode"))
        self.assertEqual(project.parameter("TX_Power_Level").confirmed_candidate["offset"], 10)
        self.assertEqual(project.parameter("Antenna_IDs_2").default, "6")
        loaded = load_payload(build_console_definition(project, [capture]))
        self.assertEqual(HciCommandEncoder().encode(loaded, {}).frame, frame)

    def test_malformed_known_layout_falls_back_to_raw_without_crashing(self):
        capture = capture_entry(bytes.fromhex("01 4F 20 01 13")).vendor_capture
        project = create_discovery_project(capture)
        self.assertEqual(project.parameters[0].name, "Parameter_0")

    def test_external_parser_fallback_is_opt_in_and_preserves_h4_validation(self):
        parser = HciParser()
        command = bytes.fromhex("01 01 20 01 AA")
        self.assertFalse(parser.parse_bytes(command).success)
        parser.set_external_opcodes({0x2001})
        for raw in (command, bytes.fromhex("04 0E 04 01 01 20 00"),
                    bytes.fromhex("04 0F 04 00 01 01 20")):
            self.assertTrue(parser.parse_bytes(raw).success)
            self.assertFalse(parser.parse_bytes(raw[:-1]).success)
        self.assertFalse(parser.parse_hex_string("01 02 20 00").success)
        parser.set_external_opcodes(set())
        self.assertFalse(parser.parse_bytes(command).success)
