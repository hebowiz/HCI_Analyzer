"""Module entry point for the HCI Analyzer application."""

from hci_analyzer.application import HciAnalyzerApplication


def main() -> None:
    """Start the HCI Analyzer application."""
    application = HciAnalyzerApplication()
    application.run()


if __name__ == "__main__":
    main()
