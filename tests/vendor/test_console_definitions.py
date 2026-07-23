"""Tests for loading Vendor Discovery definitions into Command Console."""

import json
import tempfile
import unittest
from pathlib import Path

from hci_analyzer.command_builder.encoder import HciCommandEncoder
from hci_analyzer.vendor.console_definitions import (
    load_vendor_console_definitions,
)
from hci_analyzer.vendor.discovery import (
    VendorCapture,
    analyze_captures,
    build_definition_draft,
)


class VendorConsoleDefinitionTests(unittest.TestCase):
    def test_loads_reviewed_fields_and_encodes_over_template(self) -> None:
        payload = _definition_payload()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "vendor.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            loaded = load_vendor_console_definitions(path)
            definition = loaded.definitions[0]
            encoded = HciCommandEncoder().encode(
                definition,
                {
                    "channel": 20,
                    "power": -5,
                    "duration": 0x5678,
                    "mode": 1,
                },
            )

        self.assertTrue(loaded.review_required)
        self.assertTrue(definition.vendor_specific)
        self.assertEqual(definition.category, "Vendor Specific")
        self.assertEqual(
            encoded.frame,
            bytes.fromhex("01 41 FC 06 14 FB 78 56 01 AA"),
        )

    def test_rejects_non_vendor_opcode(self) -> None:
        payload = _definition_payload()
        payload["commands"][0]["opcode"] = "0x2034"

        with self.assertRaisesRegex(ValueError, "not Vendor Specific"):
            _load_payload(payload)

    def test_rejects_missing_template(self) -> None:
        payload = _definition_payload()
        del payload["commands"][0]["parameter_template_hex"]

        with self.assertRaisesRegex(ValueError, "parameter_template_hex"):
            _load_payload(payload)

    def test_rejects_overlapping_fields(self) -> None:
        payload = _definition_payload()
        payload["commands"][0]["parameters"].append(
            {
                "name": "overlap",
                "offset": 2,
                "type": "uint16_le",
                "default": 1,
            }
        )

        with self.assertRaisesRegex(ValueError, "overlap"):
            _load_payload(payload)

    def test_rejects_value_outside_loaded_field_range(self) -> None:
        loaded = _load_payload(_definition_payload())
        definition = loaded.definitions[0]

        validation = HciCommandEncoder()._validator.validate(
            definition,
            {
                "channel": 256,
                "power": 0,
                "duration": 1,
                "mode": 0,
            },
        )

        self.assertFalse(validation.valid)
        self.assertEqual(validation.issues[0].parameter_name, "channel")

    def test_discovery_draft_loads_and_encodes_end_to_end(self) -> None:
        captures = [
            _capture(1, "13 F6", channel="19", power="-10"),
            _capture(2, "14 FB", channel="20", power="-5"),
            _capture(3, "15 00", channel="21", power="0"),
        ]
        draft = build_definition_draft(
            analyze_captures(captures),
            "Vendor_Set_RF",
            captures,
        )

        loaded = _load_payload(draft)
        encoded = HciCommandEncoder().encode(
            loaded.definitions[0],
            {"channel": 22, "power": -1},
        )

        self.assertEqual(encoded.frame, bytes.fromhex("01 41 FC 02 16 FF"))


def _load_payload(payload: dict[str, object]):
    directory = tempfile.TemporaryDirectory()
    path = Path(directory.name) / "vendor.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    try:
        return load_vendor_console_definitions(path)
    finally:
        directory.cleanup()


def _definition_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "kind": "hci_vendor_command_definition_draft",
        "review_required": True,
        "commands": [
            {
                "opcode": "0xFC41",
                "ogf": 63,
                "ocf": 65,
                "name": "Vendor_Set_RF",
                "parameter_length": 6,
                "parameter_template_hex": "13 F6 34 12 00 AA",
                "parameters": [
                    {
                        "name": "channel",
                        "offset": 0,
                        "type": "uint8",
                        "default": 19,
                    },
                    {
                        "name": "power",
                        "offset": 1,
                        "type": "int8",
                        "default": -10,
                    },
                    {
                        "name": "duration",
                        "offset": 2,
                        "type": "uint16_le",
                        "default": 0x1234,
                    },
                    {
                        "name": "mode",
                        "offset": 4,
                        "type": "enum_u8",
                        "default": 0,
                        "choices": {"0": "idle", "1": "tx"},
                    },
                ],
                "response": {"kind": "unknown"},
            }
        ],
    }


def _capture(
    line_number: int,
    parameters_hex: str,
    **annotations: str,
) -> VendorCapture:
    parameters = bytes.fromhex(parameters_hex)
    return VendorCapture(
        capture_id=f"capture:{line_number}",
        source_path=Path("capture.jsonl"),
        line_number=line_number,
        timestamp="",
        source="",
        opcode=0xFC41,
        parameters=parameters,
        raw_data=bytes.fromhex("01 41 FC") + bytes([len(parameters)]) + parameters,
        annotations=dict(annotations),
    )


if __name__ == "__main__":
    unittest.main()
