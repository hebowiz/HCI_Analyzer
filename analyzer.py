"""Development entry point for the HCI Analyzer application."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from hci_analyzer.analyzer_main import main


if __name__ == "__main__":
    main()
