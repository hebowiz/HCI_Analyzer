"""JSON Lines session logger."""

from pathlib import Path

from hci_analyzer.models import LogRecord, LogSession


class JsonlLogger:
    """Write records from both ports and manual parsing to one JSONL file."""

    def __init__(self, log_directory: Path) -> None:
        self._log_directory = log_directory
        self._session: LogSession | None = None

    @property
    def session(self) -> LogSession | None:
        """Return the active log session, if any."""
        return self._session

    def start_session(self) -> LogSession:
        """Create a timestamped JSONL file for a new analysis session."""
        raise NotImplementedError

    def write(self, record: LogRecord) -> None:
        """Append one record to the active JSONL file."""
        raise NotImplementedError

    def close(self) -> None:
        """Close the current log session."""
        raise NotImplementedError

