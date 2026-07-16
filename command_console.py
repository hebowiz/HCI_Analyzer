"""Development entry point for the HCI Command Console."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from hci_analyzer.command_console_main import main


if __name__ == "__main__":
    main()

