"""Module entry point for HCI Vendor Command Discovery."""

from hci_analyzer.gui.vendor_discovery import VendorDiscoveryWindow


def main() -> None:
    """Start the Vendor Command Discovery application."""
    VendorDiscoveryWindow().run()


if __name__ == "__main__":
    main()
