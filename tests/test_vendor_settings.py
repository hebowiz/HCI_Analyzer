"""Tests for Vendor Discovery serial and view settings."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from hci_analyzer.analyzer_settings import AnalyzerSettings
from hci_analyzer.vendor_settings import (
    VendorDiscoverySettings,
    VendorDiscoverySettingsStore,
)


class VendorDiscoverySettingsTests(unittest.TestCase):
    def test_missing_settings_seed_serial_values_from_analyzer(self) -> None:
        analyzer_store = Mock()
        analyzer_store.load.return_value = AnalyzerSettings(
            port_one="COM7",
            port_two="COM8",
            baud_rate=3_000_000,
        )
        with tempfile.TemporaryDirectory() as directory:
            store = VendorDiscoverySettingsStore(
                Path(directory) / "missing.json",
                analyzer_store,
            )

            settings = store.load()

        self.assertEqual(settings.port_one, "COM7")
        self.assertEqual(settings.port_two, "COM8")
        self.assertEqual(settings.baud_rate, 3_000_000)
        self.assertFalse(settings.group_duplicates)

    def test_saved_grouping_and_serial_values_are_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = VendorDiscoverySettingsStore(path, Mock())
            store.save(
                VendorDiscoverySettings(
                    port_one="COM1",
                    port_two="COM1",
                    baud_rate=115_200,
                    window_width=1300,
                    window_height=900,
                    group_duplicates=True,
                )
            )

            loaded = store.load()

        self.assertTrue(loaded.group_duplicates)
        self.assertEqual(loaded.port_one, "COM1")
        self.assertEqual(loaded.window_width, 1300)


if __name__ == "__main__":
    unittest.main()
