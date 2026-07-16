"""Tests for JSONL-to-sequence-diagram conversion and export."""

import json
import tempfile
import unittest
from pathlib import Path

from hci_analyzer.sequence.diagram import load_hci_sequence


class HciSequenceDiagramTests(unittest.TestCase):
    def test_commands_events_meta_and_vendor_records_are_preserved(self) -> None:
        records = [
            _record(
                "HOST_TO_CTRL",
                "01 34 20 04 13 25 00 02",
                packet_type="HCI_Command",
                decoded={
                    "display_name": "HCI_LE_Transmitter_Test[v2]",
                    "opcode_value": 0x2034,
                    "parameters": {
                        "tx_channel": 19,
                        "frequency_mhz": 2440,
                        "phy_name": "LE 2M PHY",
                    },
                },
            ),
            _record(
                "CTRL_TO_HOST",
                "04 0F 04 00 01 34 20",
                packet_type="HCI_Event",
                decoded={
                    "event_name": "HCI_Command_Status",
                    "command_name": "HCI_LE_Transmitter_Test[v2]",
                    "command_opcode_value": 0x2034,
                    "status": 0,
                },
            ),
            _record(
                "controller_to_host",
                "04 3E 02 15 00",
                packet_type="HCI_Event",
                decoded={
                    "event_name": "HCI_LE_Meta_Event",
                    "subevent_code": "0x15",
                    "subevent_name": "HCI_LE_Connectionless_IQ_Report",
                },
            ),
            _record(
                "host_to_controller",
                "01 41 FC 00",
                success=False,
                packet_type="HCI_Command",
                error={
                    "code": "UNKNOWN_OPCODE",
                    "message": "unsupported",
                    "details": {
                        "opcode": "0xFC41",
                        "opcode_value": 0xFC41,
                    },
                },
            ),
            _record(
                "controller_to_host",
                "04 FF 02 AA BB",
                packet_type="HCI_Event",
                decoded={
                    "event_name": "Unknown HCI Event",
                    "parameters_hex": "AA BB",
                },
            ),
        ]

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hci.jsonl"
            _write_records(path, records)

            diagram = load_hci_sequence(path)

        self.assertEqual(len(diagram.messages), 5)
        self.assertEqual(diagram.messages[0].direction, "host_to_controller")
        self.assertIn("HCI_LE_Transmitter_Test [v2]", diagram.messages[0].label)
        self.assertEqual(diagram.messages[1].response_to_index, 0)
        self.assertIn("HCI_Command_Status", diagram.messages[1].label)
        self.assertIn(
            "for HCI_LE_Transmitter_Test [v2]",
            diagram.messages[1].label,
        )
        self.assertEqual(
            diagram.messages[2].label,
            "HCI_LE_Connectionless_IQ_Report",
        )
        self.assertIn("Vendor Command 0xFC41", diagram.messages[3].label)
        self.assertIn("01 41 FC 00", diagram.messages[3].label)
        self.assertIn("Vendor Event", diagram.messages[4].label)
        self.assertIn("04 FF 02 AA BB", diagram.messages[4].label)

    def test_command_complete_is_linked_using_raw_opcode_on_parser_error(self) -> None:
        records = [
            _record(
                "host_to_controller",
                "01 41 FC 00",
                success=False,
                packet_type="HCI_Command",
                error={
                    "code": "UNKNOWN_OPCODE",
                    "message": "unsupported",
                    "details": {"opcode_value": 0xFC41},
                },
            ),
            _record(
                "controller_to_host",
                "04 0E 04 01 41 FC 00",
                success=False,
                packet_type="HCI_Event",
                error={
                    "code": "UNKNOWN_OPCODE",
                    "message": "unsupported",
                    "details": {"command_opcode": "0xFC41"},
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hci.jsonl"
            _write_records(path, records)
            diagram = load_hci_sequence(path)

        self.assertEqual(diagram.messages[1].response_to_index, 0)
        self.assertIn("HCI_Command_Complete", diagram.messages[1].label)
        self.assertIn("opcode 0xFC41", diagram.messages[1].label)

    def test_exports_mermaid_markdown_and_svg(self) -> None:
        records = [
            _record(
                "host_to_controller",
                "01 1F 20 00",
                packet_type="HCI_Command",
                decoded={
                    "display_name": "HCI_LE_Test_End",
                    "opcode_value": 0x201F,
                    "parameters": {},
                },
            ),
            _record(
                "controller_to_host",
                "04 0E 06 01 1F 20 00 34 12",
                packet_type="HCI_Event",
                decoded={
                    "event_name": "HCI_Command_Complete",
                    "command_name": "HCI_LE_Test_End",
                    "command_opcode_value": 0x201F,
                    "status": 0,
                },
            ),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "hci.jsonl"
            _write_records(path, records)
            diagram = load_hci_sequence(path)

            outputs = diagram.save(
                root,
                write_mmd=True,
                write_md=True,
                write_svg=True,
            )

            self.assertEqual({item.suffix for item in outputs}, {".mmd", ".md", ".svg"})
            self.assertIn("sequenceDiagram", (root / "hci_sequence.mmd").read_text())
            self.assertIn("```mermaid", (root / "hci_sequence.md").read_text())
            svg = (root / "hci_sequence.svg").read_text()
            self.assertIn("<svg", svg)
            self.assertIn("HCI_LE_Test_End", svg)

    def test_saves_markdown_and_full_preview_screenshot(self) -> None:
        records = [
            _record(
                "host_to_controller",
                "01 1F 20 00",
                packet_type="HCI_Command",
                decoded={
                    "display_name": "HCI_LE_Test_End",
                    "opcode_value": 0x201F,
                    "parameters": {},
                },
            )
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "hci.jsonl"
            _write_records(source, records)
            diagram = load_hci_sequence(source)

            markdown = diagram.save_markdown(root / "selected.md")
            screenshot = diagram.save_screenshot(root / "selected.png")

            self.assertEqual(markdown.suffix, ".md")
            self.assertIn("```mermaid", markdown.read_text(encoding="utf-8"))
            self.assertEqual(screenshot.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_saves_preview_outputs_beside_jsonl_with_automatic_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "hci_20260717_000351.jsonl"
            _write_records(source, [])
            diagram = load_hci_sequence(source)

            markdown, screenshot = diagram.save_preview_outputs()

            self.assertEqual(
                markdown,
                root / "hci_20260717_000351_sequence.md",
            )
            self.assertEqual(
                screenshot,
                root / "hci_20260717_000351_sequence.png",
            )
            self.assertTrue(markdown.is_file())
            self.assertTrue(screenshot.is_file())

    def test_invalid_json_lines_and_unrelated_directions_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hci.jsonl"
            path.write_text(
                "not json\n"
                + json.dumps({"direction": "unknown", "raw_data": "AA"})
                + "\n",
                encoding="utf-8",
            )

            diagram = load_hci_sequence(path)

        self.assertEqual(diagram.messages, ())
        self.assertIn("sequenceDiagram", diagram.to_mermaid())


def _record(
    direction: str,
    raw_data: str,
    *,
    success: bool = True,
    packet_type: str,
    decoded: dict | None = None,
    error: dict | None = None,
) -> dict:
    return {
        "timestamp": "2026-07-16T20:00:00.000+09:00",
        "source": "Port1:COM4",
        "direction": direction,
        "kind": "packet" if success else "error",
        "raw_data": raw_data,
        "result": {
            "success": success,
            "packet_type": packet_type,
            "raw_data": raw_data,
            "decoded": decoded or {},
            "error": error,
        },
        "message": None,
    }


def _write_records(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
