"""Stateful H4 stream framing and initial-noise recovery."""

from dataclasses import dataclass, field

from hci_analyzer.parser.race import race_frame_length
from hci_analyzer.parser.registry import COMMAND_DEFINITIONS


@dataclass(slots=True)
class H4StreamChunk:
    """Frames and discarded noise extracted from one input chunk."""

    frames: list[bytes] = field(default_factory=list)
    discarded_noise: list[bytes] = field(default_factory=list)


class H4StreamDecoder:
    """Extract complete H4 packets from arbitrarily divided UART reads."""

    def __init__(self, *, prefer_race: bool = True) -> None:
        self._buffer = bytearray()
        self._synchronized = False
        self._prefer_race = prefer_race

    def feed(self, data: bytes) -> H4StreamChunk:
        """Append bytes and return newly completed frames and noise."""
        result = H4StreamChunk()
        if not data:
            return result
        self._buffer.extend(data)

        while self._buffer:
            indicator_index = self._find_indicator()
            if indicator_index is None:
                result.discarded_noise.append(bytes(self._buffer))
                self._buffer.clear()
                break
            if indicator_index:
                result.discarded_noise.append(bytes(self._buffer[:indicator_index]))
                del self._buffer[:indicator_index]

            frame_length = self._frame_length()
            if frame_length is None or len(self._buffer) < frame_length:
                resync_index = self._find_startup_resync_index()
                if resync_index is not None:
                    result.discarded_noise.append(bytes(self._buffer[:resync_index]))
                    del self._buffer[:resync_index]
                    continue
                break
            result.frames.append(bytes(self._buffer[:frame_length]))
            del self._buffer[:frame_length]
            self._synchronized = True
        return result

    def reset(self) -> None:
        """Clear buffered partial data."""
        self._buffer.clear()
        self._synchronized = False

    def take_pending_data(self) -> bytes:
        """Return and clear bytes that do not yet form a complete packet."""
        pending = bytes(self._buffer)
        self._buffer.clear()
        return pending

    def _find_indicator(self) -> int | None:
        valid = {0x01, 0x02, 0x03, 0x04, 0x05}
        return next(
            (index for index, value in enumerate(self._buffer) if value in valid),
            None,
        )

    def _frame_length(self) -> int | None:
        return self._frame_length_at(0)

    def _frame_length_at(self, offset: int) -> int | None:
        available = len(self._buffer) - offset
        indicator = self._buffer[offset]
        if indicator == 0x01:
            if available < 4:
                return None
            return 4 + self._buffer[offset + 3]
        if indicator == 0x02:
            if available < 5:
                return None
            return 5 + int.from_bytes(
                self._buffer[offset + 3 : offset + 5], "little"
            )
        if indicator == 0x03:
            if available < 4:
                return None
            return 4 + self._buffer[offset + 3]
        if indicator == 0x04:
            if available < 3:
                return None
            return 3 + self._buffer[offset + 2]
        if indicator == 0x05:
            if self._prefer_race:
                race_length = race_frame_length(self._buffer, offset)
                if race_length is not None:
                    return race_length
            if available < 5:
                return None
            return 5 + (
                int.from_bytes(self._buffer[offset + 3 : offset + 5], "little")
                & 0x3FFF
            )
        return None

    def _find_startup_resync_index(self) -> int | None:
        if self._synchronized:
            return None
        for index in range(1, len(self._buffer)):
            if not self._is_plausible_start(index):
                continue
            frame_length = self._frame_length_at(index)
            if frame_length is not None and len(self._buffer) - index >= frame_length:
                return index
        return None

    def _is_plausible_start(self, offset: int) -> bool:
        indicator = self._buffer[offset]
        available = len(self._buffer) - offset
        if indicator == 0x01 and available >= 4:
            opcode = int.from_bytes(
                self._buffer[offset + 1 : offset + 3], "little"
            )
            return (
                opcode in COMMAND_DEFINITIONS
                or ((opcode >> 10) & 0x3F) == 0x3F
            )
        if indicator == 0x04 and available >= 3:
            return self._buffer[offset + 1] in (0x0E, 0x0F, 0x3E, 0xFF)
        if indicator == 0x05 and self._prefer_race:
            return race_frame_length(self._buffer, offset) is not None
        return False
