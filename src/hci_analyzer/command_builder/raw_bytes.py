"""Fixed-length byte fields shared by Discovery and Console."""


def validate_byte_size(size: object) -> int:
    """Require an explicit, positive HCI parameter field length."""
    if not isinstance(size, int) or isinstance(size, bool) or not 1 <= size <= 255:
        raise ValueError("RAW byte size must be an integer between 1 and 255")
    return size


def parse_raw_bytes(value: object, size: int | None = None) -> bytes:
    """Read octets in wire order; accept bytes or hex with optional whitespace."""
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, str):
        try:
            raw = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("RAW bytes must be hexadecimal octets, e.g. 01 AB 00 FF") from exc
    else:
        raise ValueError("RAW bytes must be a hexadecimal string or bytes")
    if size is not None:
        validate_byte_size(size)
        if len(raw) != size:
            raise ValueError(f"RAW byte length mismatch: expected {size}, received {len(raw)}")
    return raw
