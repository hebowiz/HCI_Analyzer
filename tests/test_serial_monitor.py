"""Tests for one-port and two-port monitor coordination."""

import unittest
from unittest.mock import Mock, patch

from hci_analyzer.models import SerialPortConfig
from hci_analyzer.serial.monitor import DualSerialMonitor


class DualSerialMonitorTests(unittest.TestCase):
    @patch("hci_analyzer.serial.monitor.SerialPortWorker")
    def test_same_port_starts_only_one_worker(self, worker_class: Mock) -> None:
        worker = worker_class.return_value
        monitor = DualSerialMonitor(Mock())
        first = SerialPortConfig("COM1", 115200, "Port1:COM1")
        second = SerialPortConfig("COM1", 115200, "Port2:COM1")

        monitor.start(first, second)

        worker_class.assert_called_once()
        self.assertEqual(worker_class.call_args.args[0], first)
        worker.start.assert_called_once_with()
        self.assertEqual(len(monitor._workers), 1)

    @patch("hci_analyzer.serial.monitor.SerialPortWorker")
    def test_different_ports_start_two_workers(self, worker_class: Mock) -> None:
        first_worker = Mock()
        second_worker = Mock()
        worker_class.side_effect = [first_worker, second_worker]
        monitor = DualSerialMonitor(Mock())
        first = SerialPortConfig("COM1", 115200, "Port1:COM1")
        second = SerialPortConfig("COM2", 115200, "Port2:COM2")

        monitor.start(first, second)

        self.assertEqual(worker_class.call_count, 2)
        first_worker.start.assert_called_once_with()
        second_worker.start.assert_called_once_with()
        self.assertEqual(len(monitor._workers), 2)


if __name__ == "__main__":
    unittest.main()
