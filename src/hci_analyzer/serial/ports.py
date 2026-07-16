"""Serial port enumeration."""

from serial.tools import list_ports


def list_serial_ports() -> list[str]:
    """Return serial port device names available to the GUI."""
    ports = list(list_ports.comports())
    ports.sort(key=lambda item: item.device)
    return [item.device for item in ports]
