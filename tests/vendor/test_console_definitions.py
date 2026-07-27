"""Tests for loading Vendor Discovery definitions into Command Console."""

import json
import tempfile
import unittest
from pathlib import Path

from hci_analyzer.command_builder.encoder import HciCommandEncoder
from hci_analyzer.vendor.console_definitions import (
    decode_vendor_command_complete,
    decode_vendor_parameters,
    encode_vendor_parameters,
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

    def test_allows_multiple_variants_with_the_same_opcode(self) -> None:
        payload = _definition_payload()
        second = dict(payload["commands"][0])
        second["name"] = "Vendor_Set_RF_Alternate"
        second["version"] = "B"
        payload["commands"].append(second)

        loaded = _load_payload(payload)

        self.assertEqual(len(loaded.definitions), 2)
        self.assertEqual(
            {item.opcode for item in loaded.definitions},
            {0xFC41},
        )
        self.assertEqual(
            loaded.definitions[1].display_name,
            "Vendor_Set_RF_Alternate[B]",
        )

    def test_rejects_duplicate_name_and_version_even_with_same_opcode(
        self,
    ) -> None:
        payload = _definition_payload()
        payload["commands"].append(dict(payload["commands"][0]))

        with self.assertRaisesRegex(ValueError, "selection name"):
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

    def test_uint48_little_endian_is_encoded_and_decoded(self) -> None:
        payload = {
            "schema_version": 1,
            "commands": [
                {
                    "opcode": "0xFC41",
                    "name": "Vendor_Set_Address",
                    "parameter_length": 7,
                    "parameter_template_hex": "00 00 00 00 00 00 AA",
                    "parameters": [
                        {
                            "name": "address",
                            "offset": 0,
                            "type": "uint48_le",
                            "default": 0x00006BC6967E,
                        }
                    ],
                    "response": {"kind": "unknown"},
                }
            ],
        }

        loaded = _load_payload(payload)
        definition = loaded.definitions[0]
        encoded = encode_vendor_parameters(
            definition,
            {"address": 0x123456789ABC},
        )
        decoded = decode_vendor_parameters(definition, encoded)

        self.assertEqual(encoded, bytes.fromhex("BC 9A 78 56 34 12 AA"))
        self.assertEqual(decoded["address"], 0x123456789ABC)

    def test_enum_types_from_one_to_four_bytes_are_encoded_and_decoded(
        self,
    ) -> None:
        cases = (
            ("enum_u8", 0x23, "23"),
            ("enum_u16_le", 0x0123, "23 01"),
            ("enum_u16_be", 0x0123, "01 23"),
            ("enum_u24_le", 0x123456, "56 34 12"),
            ("enum_u24_be", 0x123456, "12 34 56"),
            ("enum_u32_le", 0x12345678, "78 56 34 12"),
            ("enum_u32_be", 0x12345678, "12 34 56 78"),
        )
        for data_type, value, expected_hex in cases:
            with self.subTest(data_type=data_type):
                size = len(bytes.fromhex(expected_hex))
                payload = {
                    "schema_version": 1,
                    "commands": [
                        {
                            "opcode": "0xFC41",
                            "name": "Vendor_Set_Mode",
                            "parameter_length": size,
                            "parameter_template_hex": "00 " * size,
                            "parameters": [
                                {
                                    "name": "mode",
                                    "offset": 0,
                                    "type": data_type,
                                    "number_format": "hex",
                                    "default": hex(value),
                                    "choices": {
                                        hex(value): "A",
                                        hex(value + 1): "B",
                                    },
                                }
                            ],
                            "response": {"kind": "unknown"},
                        }
                    ],
                }

                loaded = _load_payload(payload)
                definition = loaded.definitions[0]
                encoded = encode_vendor_parameters(
                    definition,
                    {"mode": value},
                )
                decoded = decode_vendor_parameters(definition, encoded)

                self.assertEqual(encoded, bytes.fromhex(expected_hex))
                self.assertEqual(
                    decoded["mode"],
                    f"0x{value:0{size * 2}X}",
                )
                self.assertEqual(decoded["mode_name"], "A")

    def test_rejects_unknown_number_format(self) -> None:
        payload = _definition_payload()
        payload["commands"][0]["parameters"][0]["number_format"] = "binary"

        with self.assertRaisesRegex(ValueError, "number_format"):
            _load_payload(payload)

    def test_decimal_string_default_is_loaded_as_integer(self) -> None:
        payload = _definition_payload()
        payload["commands"][0]["parameters"][0]["default"] = "19"

        loaded = _load_payload(payload)

        self.assertEqual(
            loaded.definitions[0].parameters[0].default,
            19,
        )

    def test_signed_hexadecimal_string_default_is_loaded_as_integer(self) -> None:
        payload = _definition_payload()
        payload["commands"][0]["parameters"][1]["default"] = "-0x0A"

        loaded = _load_payload(payload)

        self.assertEqual(
            loaded.definitions[0].parameters[1].default,
            -10,
        )

    def test_loads_and_decodes_command_complete_parameters(self) -> None:
        payload = _definition_payload()
        payload["commands"][0]["response"] = {
            "kind": "command_complete",
            "parameter_length": 4,
            "parameters": [
                {
                    "name": "status_code",
                    "label": "Status",
                    "offset": 0,
                    "type": "enum_u8",
                    "number_format": "hex",
                    "choices": {
                        "0x00": "Success",
                        "0x01": "Failed",
                    },
                },
                {
                    "name": "result",
                    "offset": 1,
                    "type": "uint16_le",
                    "number_format": "hex",
                },
                {
                    "name": "count",
                    "offset": 3,
                    "type": "uint8",
                },
            ],
        }

        definition = _load_payload(payload).definitions[0]
        decoded = decode_vendor_command_complete(
            definition,
            bytes.fromhex("00 34 12 05"),
        )

        self.assertEqual(definition.response_parameter_length, 4)
        self.assertEqual(len(definition.response_parameters), 3)
        self.assertEqual(decoded["status_code"], "0x00")
        self.assertEqual(decoded["status_code_name"], "Success")
        self.assertEqual(decoded["result"], "0x1234")
        self.assertEqual(decoded["count"], 5)

    def test_command_complete_length_mismatch_is_preserved_as_error(self) -> None:
        payload = _definition_payload()
        payload["commands"][0]["response"] = {
            "kind": "command_complete",
            "parameter_length": 2,
            "parameters": [
                {"name": "status", "offset": 0, "type": "uint8"},
            ],
        }
        definition = _load_payload(payload).definitions[0]

        decoded = decode_vendor_command_complete(
            definition,
            bytes.fromhex("00"),
        )

        self.assertIn("length mismatch", decoded["decode_error"])
        self.assertEqual(decoded["raw_hex"], "00")

    def test_rejects_overlapping_command_complete_parameters(self) -> None:
        payload = _definition_payload()
        payload["commands"][0]["response"] = {
            "kind": "command_complete",
            "parameter_length": 3,
            "parameters": [
                {"name": "first", "offset": 0, "type": "uint16_le"},
                {"name": "second", "offset": 1, "type": "uint16_le"},
            ],
        }

        with self.assertRaisesRegex(ValueError, "response parameters.*overlap"):
            _load_payload(payload)


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
