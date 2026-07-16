"""Tests for sequence generation when Analyzer monitoring stops."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hci_analyzer.application import HciAnalyzerApplication
from hci_analyzer.models import LogSession


class _MonitorStub:
    def stop(self) -> None:
        return None


class _LoggerStub:
    def __init__(self, path: Path) -> None:
        self.session = LogSession.__new__(LogSession)
        object.__setattr__(self.session, "started_at", None)
        object.__setattr__(self.session, "file_path", path)
        self.closed = False

    def close(self) -> None:
        self.closed = True
        self.session = None


class _WindowStub:
    def __init__(self) -> None:
        self.diagram = None
        self.monitoring = True

    def append_record(self, _record: object) -> None:
        return None

    def set_monitoring_state(self, active: bool) -> None:
        self.monitoring = active

    def show_sequence_diagram(self, diagram: object) -> None:
        self.diagram = diagram


class AnalyzerSequenceIntegrationTests(unittest.TestCase):
    def test_stop_monitoring_opens_sequence_window_for_last_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hci.jsonl"
            path.write_text("", encoding="utf-8")
            application = object.__new__(HciAnalyzerApplication)
            application._monitoring = True
            application._monitor = _MonitorStub()
            application._logger = _LoggerStub(path)
            application._window = _WindowStub()
            application._record_queue = __import__("queue").Queue()

            application._stop_monitoring()

            self.assertFalse(application._monitoring)
            self.assertFalse(application._window.monitoring)
            self.assertIsNotNone(application._window.diagram)
            self.assertEqual(application._window.diagram.source_path, path)

    def test_application_close_does_not_open_sequence_window(self) -> None:
        application = object.__new__(HciAnalyzerApplication)
        application._monitoring = True
        with patch.object(application, "_stop_monitoring") as stop:
            application._settings_store = unittest.mock.Mock()
            application._window = unittest.mock.Mock()
            application._window.get_monitor_settings.return_value = (
                "COM1",
                "COM2",
                115200,
            )
            application._window.get_window_size.return_value = (1100, 720)

            application._close()

        stop.assert_called_once_with(show_sequence=False)


if __name__ == "__main__":
    unittest.main()
