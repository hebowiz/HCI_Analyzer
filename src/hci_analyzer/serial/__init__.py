"""Serial port discovery and monitoring."""

from hci_analyzer.serial.monitor import DualSerialMonitor
from hci_analyzer.serial.ports import list_serial_ports

__all__ = ["DualSerialMonitor", "list_serial_ports"]

