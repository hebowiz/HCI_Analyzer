"""Tests for persistent HCI Analyzer settings."""

import json
import tempfile
import unittest
from pathlib import Path

from hci_analyzer.analyzer_settings import (
    AnalyzerSettings,
    AnalyzerSettingsStore,
)
from hci_analyzer.config import (
    ANALYZER_DEFAULT_WINDOW_SIZE,
    DEFAULT_BAUD_RATE,
)


class AnalyzerSettingsStoreTests(unittest.TestCase):
    def test_missing_file_returns_default_window_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = AnalyzerSettingsStore(Path(directory) / "settings.json")

            settings = store.load()

            self.assertEqual(
                (settings.window_width, settings.window_height),
                ANALYZER_DEFAULT_WINDOW_SIZE,
            )
            self.assertEqual(settings.port_one, "")
            self.assertEqual(settings.port_two, "")
            self.assertEqual(settings.baud_rate, DEFAULT_BAUD_RATE)

    def test_saved_window_size_is_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = AnalyzerSettingsStore(path)
            store.save(
                AnalyzerSettings(
                    port_one="COM7",
                    port_two="COM8",
                    baud_rate=3_000_000,
                    window_width=1400,
                    window_height=900,
                )
            )

            settings = store.load()

            self.assertEqual(settings.window_width, 1400)
            self.assertEqual(settings.window_height, 900)
            self.assertEqual(settings.port_one, "COM7")
            self.assertEqual(settings.port_two, "COM8")
            self.assertEqual(settings.baud_rate, 3_000_000)

    def test_too_small_window_size_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps({"window_width": 100, "window_height": 100}),
                encoding="utf-8",
            )

            settings = AnalyzerSettingsStore(path).load()

            self.assertEqual(
                (settings.window_width, settings.window_height),
                ANALYZER_DEFAULT_WINDOW_SIZE,
            )

    def test_invalid_serial_settings_fall_back_to_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "port_one": 7,
                        "port_two": None,
                        "baud_rate": 12345,
                    }
                ),
                encoding="utf-8",
            )

            settings = AnalyzerSettingsStore(path).load()

            self.assertEqual(settings.port_one, "")
            self.assertEqual(settings.port_two, "")
            self.assertEqual(settings.baud_rate, DEFAULT_BAUD_RATE)


if __name__ == "__main__":
    unittest.main()
