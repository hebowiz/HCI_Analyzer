"""Top-level application coordination."""

from hci_analyzer.gui.main_window import MainWindow
from hci_analyzer.logging.jsonl_logger import JsonlLogger
from hci_analyzer.parser.facade import HciParser
from hci_analyzer.serial.monitor import DualSerialMonitor


class HciAnalyzerApplication:
    """Compose the GUI, parser, serial monitor, and JSONL logger."""

    def __init__(self) -> None:
        self._parser: HciParser
        self._monitor: DualSerialMonitor
        self._logger: JsonlLogger
        self._window: MainWindow

    def run(self) -> None:
        """Start the application event loop."""
        raise NotImplementedError

