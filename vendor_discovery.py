"""Development entry point for HCI Vendor Command Discovery."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from hci_analyzer.vendor_discovery_main import main


if __name__ == "__main__":
    main()
