"""Application coordination tests for live Vendor Discovery."""

import queue
import unittest
from unittest.mock import Mock

from hci_analyzer.vendor_discovery_application import (
    VendorDiscoveryApplication,
)


class VendorDiscoveryApplicationTests(unittest.TestCase):
    def test_start_uses_analyzer_dual_port_monitor_configuration(self) -> None:
        application = object.__new__(VendorDiscoveryApplication)
        application._window = Mock()
        application._window.get_monitor_settings.return_value = (
            "COM3",
            "COM4",
            3_000_000,
        )
        application._monitor = Mock()
        application._monitoring = False

        application._start_monitoring()

        first, second = application._monitor.start.call_args.args
        self.assertEqual((first.port, first.baud_rate), ("COM3", 3_000_000))
        self.assertEqual((second.port, second.baud_rate), ("COM4", 3_000_000))
        application._window.set_monitoring_state.assert_called_once_with(True)

    def test_record_queue_is_forwarded_to_window_on_ui_drain(self) -> None:
        application = object.__new__(VendorDiscoveryApplication)
        application._window = Mock()
        application._record_queue = queue.Queue()
        record = Mock()
        application._record_queue.put(record)

        application._consume_pending_records()

        application._window.add_monitor_record.assert_called_once_with(record)


if __name__ == "__main__":
    unittest.main()
