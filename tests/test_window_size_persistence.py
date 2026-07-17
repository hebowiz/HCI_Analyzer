"""Tests for application-level window size persistence."""

import unittest

from hci_analyzer.application import HciAnalyzerApplication
from hci_analyzer.console_application import HciCommandConsoleApplication


class _SettingsStoreStub:
    def __init__(self) -> None:
        self.saved = None

    def save(self, settings: object) -> None:
        self.saved = settings


class _AnalyzerWindowStub:
    def __init__(self) -> None:
        self.destroyed = False

    def get_window_size(self) -> tuple[int, int]:
        return 1400, 900

    def get_monitor_settings(self) -> tuple[str, str, int]:
        return "COM7", "COM8", 3_000_000

    def destroy(self) -> None:
        self.destroyed = True


class _ConsoleWindowStub:
    def __init__(self) -> None:
        self.destroyed = False

    def get_connection_settings(self) -> tuple[str, int]:
        return "COM7", 3_000_000

    def get_window_size(self) -> tuple[int, int]:
        return 1500, 950

    def get_response_timeout_seconds(self) -> float:
        return 2.0

    def destroy(self) -> None:
        self.destroyed = True


class _CloseStub:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def disconnect(self) -> None:
        self.closed = True


class WindowSizePersistenceTests(unittest.TestCase):
    def test_analyzer_saves_window_size_on_close(self) -> None:
        application = object.__new__(HciAnalyzerApplication)
        application._monitoring = False
        application._settings_store = _SettingsStoreStub()
        application._window = _AnalyzerWindowStub()
        application._logger = _CloseStub()

        application._close()

        saved = application._settings_store.saved
        self.assertEqual(saved.port_one, "COM7")
        self.assertEqual(saved.port_two, "COM8")
        self.assertEqual(saved.baud_rate, 3_000_000)
        self.assertEqual(saved.window_width, 1400)
        self.assertEqual(saved.window_height, 900)
        self.assertTrue(application._window.destroyed)

    def test_console_saves_connection_and_window_size_on_close(self) -> None:
        application = object.__new__(HciCommandConsoleApplication)
        application._settings_store = _SettingsStoreStub()
        application._window = _ConsoleWindowStub()
        application._transport = _CloseStub()

        application._close()

        saved = application._settings_store.saved
        self.assertEqual(saved.port, "COM7")
        self.assertEqual(saved.baud_rate, 3_000_000)
        self.assertEqual(saved.response_timeout_seconds, 2)
        self.assertEqual(saved.window_width, 1500)
        self.assertEqual(saved.window_height, 950)
        self.assertTrue(application._window.destroyed)


if __name__ == "__main__":
    unittest.main()
