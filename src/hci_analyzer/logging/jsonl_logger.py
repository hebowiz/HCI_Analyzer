"""JSON Lines session logger."""

import json
import threading
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from io import TextIOWrapper
from pathlib import Path
from typing import Any

from hci_analyzer.models import LogRecord, LogSession
from hci_analyzer.presentation.text import ascii_safe_text


class JsonlLogger:
    """Write records from both ports and manual parsing to one JSONL file."""

    def __init__(self, log_directory: Path) -> None:
        self._log_directory = log_directory
        self._session: LogSession | None = None
        self._file: TextIOWrapper | None = None
        self._lock = threading.Lock()

    @property
    def session(self) -> LogSession | None:
        """Return the active log session, if any."""
        return self._session

    def start_session(self) -> LogSession:
        """Create a timestamped JSONL file for a new analysis session."""
        with self._lock:
            self._close_unlocked()
            self._log_directory.mkdir(parents=True, exist_ok=True)
            started_at = datetime.now().astimezone()
            base_name = started_at.strftime("hci_%Y%m%d_%H%M%S")
            file_path = self._unique_path(base_name)
            self._file = file_path.open("a", encoding="utf-8", newline="\n")
            self._session = LogSession(started_at, file_path)
            return self._session

    def write(self, record: LogRecord) -> None:
        """Append one record to the active JSONL file."""
        with self._lock:
            if self._file is None:
                raise RuntimeError("JSONL log session has not been started")
            payload = self._to_json_value(record)
            self._file.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._file.flush()

    def close(self) -> None:
        """Close the current log session."""
        with self._lock:
            self._close_unlocked()

    def _unique_path(self, base_name: str) -> Path:
        candidate = self._log_directory / f"{base_name}.jsonl"
        suffix = 1
        while candidate.exists():
            candidate = self._log_directory / f"{base_name}_{suffix:02d}.jsonl"
            suffix += 1
        return candidate

    def _close_unlocked(self) -> None:
        if self._file is not None:
            self._file.close()
        self._file = None
        self._session = None

    @classmethod
    def _to_json_value(cls, value: Any) -> Any:
        if isinstance(value, bytes):
            return value.hex(" ").upper()
        if isinstance(value, datetime):
            return value.isoformat(timespec="milliseconds")
        if isinstance(value, Path):
            return ascii_safe_text(value)
        if isinstance(value, str):
            return ascii_safe_text(value)
        if isinstance(value, Enum):
            return cls._to_json_value(value.value)
        if is_dataclass(value):
            return {
                key: cls._to_json_value(item)
                for key, item in asdict(value).items()
            }
        if isinstance(value, dict):
            return {
                ascii_safe_text(key): cls._to_json_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [cls._to_json_value(item) for item in value]
        return value
