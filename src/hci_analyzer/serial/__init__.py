"""Serial port discovery and monitoring."""

from hci_analyzer.serial.monitor import DualSerialMonitor
from hci_analyzer.serial.ports import list_serial_ports
from hci_analyzer.serial.transport import HciSerialTransport

__all__ = ["DualSerialMonitor", "HciSerialTransport", "list_serial_ports"]
