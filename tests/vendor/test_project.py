"""Tests for incremental user-defined Discovery projects."""

import tempfile
import unittest
from pathlib import Path

from hci_analyzer.vendor.console_definitions import (
    load_vendor_console_definitions,
)
from hci_analyzer.vendor.discovery import analyze_captures
from hci_analyzer.vendor.live_capture import DiscoveryCapture
from hci_analyzer.vendor.project import (
    UserParameter,
    VendorDiscoveryProject,
    build_console_definition,
    load_project,
    save_project,
)
from tests.vendor.test_discovery import _capture


class VendorDiscoveryProjectTests(unittest.TestCase):
    def test_user_parameter_is_analyzed_and_confirmed_incrementally(self) -> None:
        captures = [
            _capture(1, "00 10", phy="LE_1M"),
            _capture(2, "01 10", phy="LE_2M"),
            _capture(3, "02 10", phy="LE_CODED"),
            _capture(4, "00 10", phy="LE_1M"),
        ]
        parameter = UserParameter(
            name="phy",
            display_name="PHY",
            kind="enum",
            choices=["LE_1M", "LE_2M", "LE_CODED"],
        )

        analysis = analyze_captures(captures)
        parameter.set_candidates(analysis.candidates["phy"])
        parameter.confirm_first_candidate()

        self.assertEqual(parameter.status, "confirmed")
        self.assertEqual(parameter.confirmed_candidate["offset"], 0)
        self.assertEqual(parameter.confirmed_candidate["type"], "enum_u8")

    def test_project_round_trip_keeps_parameters_captures_and_annotations(self) -> None:
        vendor = _capture(1, "01 10", phy="LE_2M")
        entry = DiscoveryCapture(
            capture_id=vendor.capture_id,
            timestamp=vendor.timestamp,
            source=vendor.source,
            protocol="HCI Vendor",
            raw_data=vendor.raw_data,
            vendor_capture=vendor,
        )
        project = VendorDiscoveryProject(
            opcode=0xFC41,
            command_name="Vendor_Set_PHY",
        )
        project.add_parameter(
            UserParameter(
                name="phy",
                display_name="PHY",
                kind="enum",
                number_format="hex",
                choices=["LE_1M", "LE_2M"],
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.json"
            save_project(path, project, [entry])
            loaded_project, loaded_captures = load_project(path)

        self.assertEqual(loaded_project.opcode, 0xFC41)
        self.assertEqual(loaded_project.parameters[0].choices, ["LE_1M", "LE_2M"])
        self.assertEqual(loaded_project.parameters[0].number_format, "hex")
        self.assertEqual(
            loaded_captures[0].vendor_capture.annotations["phy"],
            "LE_2M",
        )

    def test_confirmed_project_exports_console_compatible_definition(self) -> None:
        captures = [
            _capture(1, "00 10", phy="LE_1M"),
            _capture(2, "01 10", phy="LE_2M"),
        ]
        analysis = analyze_captures(captures)
        parameter = UserParameter(
            name="phy",
            display_name="PHY",
            kind="enum",
            choices=["LE_1M", "LE_2M"],
        )
        parameter.set_candidates(analysis.candidates["phy"])
        parameter.confirm_first_candidate()
        project = VendorDiscoveryProject(
            opcode=0xFC41,
            command_name="Vendor_Set_PHY",
            parameters=[parameter],
        )

        definition = build_console_definition(project, captures)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "definition.json"
            import json

            path.write_text(
                json.dumps(definition, ensure_ascii=False),
                encoding="utf-8",
            )
            loaded = load_vendor_console_definitions(path)

        self.assertEqual(loaded.definitions[0].name, "Vendor_Set_PHY")
        self.assertEqual(loaded.definitions[0].parameters[0].choices[1], "LE_2M")
        self.assertFalse(loaded.review_required)

    def test_manual_48_bit_layout_is_saved_and_exported(self) -> None:
        captures = [
            _capture(
                1,
                "27 27 04 1B 00 00 30 00 7E 96 C6 6B 00 00 07",
                address="0x00006BC6967E",
            )
        ]
        parameter = UserParameter(
            name="address",
            display_name="Address",
            kind="unsigned",
            number_format="hex",
        )
        parameter.set_manual_candidate(8, "uint48_le")
        project = VendorDiscoveryProject(
            opcode=0xFC41,
            command_name="Vendor_Set_Address",
            parameters=[parameter],
        )

        definition = build_console_definition(project, captures)

        field = definition["commands"][0]["parameters"][0]
        self.assertEqual(field["offset"], 8)
        self.assertEqual(field["type"], "uint48_le")
        self.assertEqual(field["size"], 6)
        self.assertEqual(field["default"], "0x00006BC6967E")
        self.assertEqual(
            parameter.confirmed_candidate["source"],
            "manual",
        )

    def test_manual_two_byte_enum_exports_non_contiguous_choices(self) -> None:
        captures = [
            _capture(1, "23 01 AA", mode="A"),
            _capture(2, "12 25 AA", mode="B"),
        ]
        parameter = UserParameter(
            name="mode",
            display_name="Mode",
            kind="enum",
            number_format="hex",
            choices=["A", "B"],
        )
        project = VendorDiscoveryProject(
            opcode=0xFC41,
            command_name="Vendor_Set_Mode",
            parameters=[parameter],
        )

        project.set_manual_layout("mode", 0, "enum_u16_le", 3)
        definition = build_console_definition(project, captures)

        field = definition["commands"][0]["parameters"][0]
        self.assertEqual(field["type"], "enum_u16_le")
        self.assertEqual(field["size"], 2)
        self.assertEqual(field["number_format"], "hex")
        self.assertEqual(field["default"], "0x0123")
        self.assertEqual(field["choices"]["0x0123"], "A")
        self.assertEqual(field["choices"]["0x2512"], "B")

    def test_manual_layout_rejects_type_incompatible_with_parameter_kind(self) -> None:
        parameter = UserParameter(
            name="power",
            display_name="Power",
            kind="signed",
        )

        with self.assertRaisesRegex(ValueError, "Signed"):
            parameter.set_manual_candidate(1, "uint48_le")

    def test_project_rejects_manual_layout_outside_template(self) -> None:
        parameter = UserParameter(
            name="address",
            display_name="Address",
            kind="unsigned",
        )
        project = VendorDiscoveryProject(
            opcode=0xFC41,
            parameters=[parameter],
        )

        with self.assertRaisesRegex(ValueError, "exceeds"):
            project.set_manual_layout(
                "address",
                10,
                "uint48_le",
                parameter_length=15,
            )

        self.assertIsNone(parameter.confirmed_candidate)
        self.assertEqual(parameter.status, "not_analyzed")

    def test_project_rejects_overlapping_manual_layout(self) -> None:
        first = UserParameter(
            name="address",
            display_name="Address",
            kind="unsigned",
        )
        second = UserParameter(
            name="mode",
            display_name="Mode",
            kind="unsigned",
        )
        project = VendorDiscoveryProject(
            opcode=0xFC41,
            parameters=[first, second],
        )
        project.set_manual_layout("address", 8, "uint48_le", 15)

        with self.assertRaisesRegex(ValueError, "overlap"):
            project.set_manual_layout("mode", 13, "uint8", 15)

        self.assertIsNone(second.confirmed_candidate)


if __name__ == "__main__":
    unittest.main()
