"""Module entry point for the HCI Command Console."""

from hci_analyzer.console_application import HciCommandConsoleApplication


def main() -> None:
    """Start the HCI Command Console application."""
    application = HciCommandConsoleApplication()
    application.run()


if __name__ == "__main__":
    main()

