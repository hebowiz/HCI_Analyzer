"""Tests for vendor-specific command capture comparison."""

import json
import tempfile
import unittest
from pathlib import Path

from hci_analyzer.vendor.discovery import (
    VendorCapture,
    analyze_captures,
    build_definition_draft,
    load_vendor_captures,
    parse_annotations,
)


class VendorDiscoveryTests(unittest.TestCase):
    def test_loads_vendor_commands_from_new_and_legacy_jsonl(self) -> None:
        records = [
            _record("01 41 FC 04 13 F6 34 12", success=True),
            _record("04 0E 05 01 41 FC 00 AA", success=True),
            _record(
                "01 42 FC 02 01 00",
                success=False,
                error_code="UNKNOWN_OPCODE",
            ),
            _record("04 FF 02 55 AA", success=True),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.jsonl"
            path.write_text(
                "\n".join(json.dumps(item) for item in records) + "\n",
                encoding="utf-8",
            )

            captures, errors = load_vendor_captures([path])

        self.assertEqual(errors, [])
        self.assertEqual([item.opcode for item in captures], [0xFC41, 0xFC42])
        self.assertEqual(captures[0].parameters, bytes.fromhex("13 F6 34 12"))
        self.assertEqual(len(captures[0].responses), 1)
        self.assertEqual(len(captures[1].responses), 1)

    def test_annotations_accept_common_separators(self) -> None:
        self.assertEqual(
            parse_annotations("channel=19, power=-10\nmode=tx"),
            {"channel": "19", "power": "-10", "mode": "tx"},
        )

    def test_decimal_annotation_with_leading_zero_is_numeric(self) -> None:
        captures = [
            _capture(1, "01", channel="01"),
            _capture(2, "02", channel="02"),
        ]

        analysis = analyze_captures(captures)

        self.assertEqual(analysis.candidates["channel"][0].data_type, "uint8")

    def test_infers_numeric_offsets_types_and_changed_bytes(self) -> None:
        captures = [
            _capture(1, "13 F6 34 12", channel="19", power="-10", duration="4660"),
            _capture(2, "14 F6 78 56", channel="20", power="-10", duration="22136"),
            _capture(3, "15 FB BC 9A", channel="21", power="-5", duration="39612"),
            _capture(4, "16 00 EF BE", channel="22", power="0", duration="48879"),
        ]

        analysis = analyze_captures(captures)

        self.assertEqual(analysis.changed_offsets, (0, 1, 2, 3))
        self.assertEqual(analysis.candidates["channel"][0].offset, 0)
        self.assertEqual(analysis.candidates["channel"][0].data_type, "uint8")
        self.assertEqual(analysis.candidates["power"][0].offset, 1)
        self.assertEqual(analysis.candidates["power"][0].data_type, "int8")
        self.assertEqual(analysis.candidates["duration"][0].offset, 2)
        self.assertEqual(
            analysis.candidates["duration"][0].data_type,
            "uint16_le",
        )
        self.assertEqual(analysis.candidates["duration"][0].confidence, "high")

    def test_infers_text_enum_byte(self) -> None:
        captures = [
            _capture(1, "00 10", mode="idle"),
            _capture(2, "01 10", mode="tx"),
            _capture(3, "00 10", mode="idle"),
        ]

        analysis = analyze_captures(captures)

        self.assertEqual(analysis.candidates["mode"][0].offset, 0)
        self.assertEqual(analysis.candidates["mode"][0].data_type, "enum_u8")

    def test_definition_draft_requires_review_and_includes_candidates(self) -> None:
        captures = [
            _capture(1, "01", channel="1"),
            _capture(2, "02", channel="2"),
        ]
        analysis = analyze_captures(captures)

        draft = build_definition_draft(
            analysis,
            "Vendor_Set_Channel",
            captures,
        )

        command = draft["commands"][0]
        self.assertTrue(draft["review_required"])
        self.assertEqual(command["opcode"], "0xFC41")
        self.assertEqual(command["name"], "Vendor_Set_Channel")
        self.assertEqual(command["parameter_length"], 1)
        self.assertEqual(command["parameter_template_hex"], "01")
        self.assertEqual(command["parameters"][0]["offset"], 0)
        self.assertEqual(command["parameters"][0]["default"], 1)
        self.assertGreaterEqual(
            len(command["parameters"][0]["candidates"]),
            1,
        )


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
        timestamp=f"2026-07-23T00:00:0{line_number}+09:00",
        source="Port1:COM1",
        opcode=0xFC41,
        parameters=parameters,
        raw_data=bytes.fromhex("01 41 FC") + bytes([len(parameters)]) + parameters,
        annotations=dict(annotations),
    )


def _record(
    raw_hex: str,
    *,
    success: bool,
    error_code: str | None = None,
) -> dict[str, object]:
    return {
        "timestamp": "2026-07-23T00:00:00+09:00",
        "source": "Port1:COM1",
        "direction": "host_to_controller",
        "kind": "packet",
        "raw_data": raw_hex,
        "result": {
            "success": success,
            "packet_type": "HCI_Command",
            "raw_data": raw_hex,
            "decoded": {},
            "error": (
                {
                    "code": error_code,
                    "message": "unsupported",
                    "details": {},
                }
                if error_code
                else None
            ),
        },
        "message": None,
    }


if __name__ == "__main__":
    unittest.main()
