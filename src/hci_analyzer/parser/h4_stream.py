"""Stateful H4 stream framing and initial-noise recovery."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class H4StreamChunk:
    """Frames and discarded noise extracted from one input chunk."""

    frames: list[bytes] = field(default_factory=list)
    discarded_noise: list[bytes] = field(default_factory=list)


class H4StreamDecoder:
    """Extract complete H4 packets from arbitrarily divided UART reads."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> H4StreamChunk:
        """Append bytes and return newly completed frames and noise."""
        raise NotImplementedError

    def reset(self) -> None:
        """Clear buffered partial data."""
        self._buffer.clear()

