"""Tests for persistent Command Console settings."""

import json
import tempfile
import unittest
from pathlib import Path

from hci_analyzer.config import (
    COMMAND_CONSOLE_DEFAULT_WINDOW_SIZE,
    DEFAULT_BAUD_RATE,
    DEFAULT_RESPONSE_TIMEOUT_SECONDS,
)
from hci_analyzer.console_settings import (
    CommandConsoleSettings,
    CommandConsoleSettingsStore,
)


class CommandConsoleSettingsStoreTests(unittest.TestCase):
    def test_missing_file_returns_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = CommandConsoleSettingsStore(Path(directory) / "settings.json")

            settings = store.load()

            self.assertEqual(settings.port, "")
            self.assertEqual(settings.baud_rate, DEFAULT_BAUD_RATE)
            self.assertEqual(
                settings.response_timeout_seconds,
                DEFAULT_RESPONSE_TIMEOUT_SECONDS,
            )
            self.assertEqual(
                (settings.window_width, settings.window_height),
                COMMAND_CONSOLE_DEFAULT_WINDOW_SIZE,
            )

    def test_saved_settings_are_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = CommandConsoleSettingsStore(path)
            store.save(
                CommandConsoleSettings(
                    "COM7",
                    3_000_000,
                    response_timeout_seconds=2,
                    window_width=1500,
                    window_height=950,
                )
            )

            settings = store.load()

            self.assertEqual(settings.port, "COM7")
            self.assertEqual(settings.baud_rate, 3_000_000)
            self.assertEqual(settings.response_timeout_seconds, 2)
            self.assertEqual(settings.window_width, 1500)
            self.assertEqual(settings.window_height, 950)

    def test_invalid_baud_rate_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps({"port": "COM7", "baud_rate": 12345}),
                encoding="utf-8",
            )

            settings = CommandConsoleSettingsStore(path).load()

            self.assertEqual(settings.port, "COM7")
            self.assertEqual(settings.baud_rate, DEFAULT_BAUD_RATE)

    def test_invalid_response_timeout_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps({"response_timeout_seconds": 10}),
                encoding="utf-8",
            )

            settings = CommandConsoleSettingsStore(path).load()

            self.assertEqual(
                settings.response_timeout_seconds,
                DEFAULT_RESPONSE_TIMEOUT_SECONDS,
            )

    def test_legacy_settings_without_window_size_use_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps({"port": "COM7", "baud_rate": 115_200}),
                encoding="utf-8",
            )

            settings = CommandConsoleSettingsStore(path).load()

            self.assertEqual(settings.port, "COM7")
            self.assertEqual(
                settings.response_timeout_seconds,
                DEFAULT_RESPONSE_TIMEOUT_SECONDS,
            )
            self.assertEqual(
                (settings.window_width, settings.window_height),
                COMMAND_CONSOLE_DEFAULT_WINDOW_SIZE,
            )

    def test_too_small_window_size_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text(
                json.dumps(
                    {
                        "port": "COM7",
                        "baud_rate": 115_200,
                        "window_width": 100,
                        "window_height": 100,
                    }
                ),
                encoding="utf-8",
            )

            settings = CommandConsoleSettingsStore(path).load()

            self.assertEqual(
                (settings.window_width, settings.window_height),
                COMMAND_CONSOLE_DEFAULT_WINDOW_SIZE,
            )


if __name__ == "__main__":
    unittest.main()
