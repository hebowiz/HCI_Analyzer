"""Tests for JSON Lines logging."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from hci_analyzer.logging.jsonl_logger import JsonlLogger
from hci_analyzer.models import (
    LogRecord,
    ParseResult,
    RecordKind,
    TrafficDirection,
)


class JsonlLoggerTests(unittest.TestCase):
    def test_record_is_serialized_as_one_json_line(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logger = JsonlLogger(Path(directory))
            session = logger.start_session()
            logger.write(
                LogRecord(
                    timestamp=datetime.now().astimezone(),
                    source="Port1:COM1",
                    direction=TrafficDirection.HOST_TO_CONTROLLER,
                    kind=RecordKind.PACKET,
                    raw_data=bytes.fromhex("01 1F 20 00"),
                    result=ParseResult(
                        True,
                        "HCI_Command",
                        bytes.fromhex("01 1F 20 00"),
                        decoded={"command_name": "HCI_LE_Test_End"},
                    ),
                )
            )
            logger.close()

            lines = session.file_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["source"], "Port1:COM1")
            self.assertEqual(payload["raw_data"], "01 1F 20 00")
            self.assertEqual(
                payload["result"]["decoded"]["command_name"], "HCI_LE_Test_End"
            )

    def test_jsonl_replaces_non_ascii_log_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logger = JsonlLogger(Path(directory))
            session = logger.start_session()
            logger.write(
                LogRecord(
                    timestamp=datetime.now().astimezone(),
                    source="Application",
                    direction=TrafficDirection.UNKNOWN,
                    kind=RecordKind.ERROR,
                    message="パラメーターが間違っています。",
                )
            )
            logger.close()

            text = session.file_path.read_text(encoding="utf-8")

        self.assertTrue(text.isascii())
        self.assertIn("[localized message omitted]", text)
        self.assertNotIn(r"\u30d1", text)
        self.assertEqual(
            json.loads(text)["message"],
            "[localized message omitted]",
        )


if __name__ == "__main__":
    unittest.main()
