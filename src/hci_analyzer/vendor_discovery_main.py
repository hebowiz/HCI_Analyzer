"""Module entry point for HCI Vendor Command Discovery."""

from hci_analyzer.vendor_discovery_application import VendorDiscoveryApplication


def main() -> None:
    """Start the Vendor Command Discovery application."""
    VendorDiscoveryApplication().run()


if __name__ == "__main__":
    main()
