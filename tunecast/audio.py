"""Silent MP3 for the profile music section, and a placeholder cover."""

import math
import struct
import zlib
from functools import lru_cache

# MPEG-2 Layer III, 8 kbit/s, 16 kHz, mono: a 36-byte frame ≈ 36 ms of silence
_FRAME = bytes([0xFF, 0xF3, 0x18, 0xC0]) + bytes(32)
_FRAME_SECONDS = 576 / 16000
MAX_SECONDS = 15 * 60  # ~0.9 MB, no need for longer


def _syncsafe(n: int) -> bytes:
    return bytes([(n >> 21) & 0x7F, (n >> 14) & 0x7F, (n >> 7) & 0x7F, n & 0x7F])


def _id3_frame(frame_id: str, text: str) -> bytes:
    data = b"\x01" + text.encode("utf-16")  # UTF-16 with BOM
    return frame_id.encode() + len(data).to_bytes(4, "big") + b"\x00\x00" + data


def silent_mp3(seconds: int, title: str, performer: str) -> bytes:
    """Silence of the given length with ID3 title and artist tags."""
    seconds = max(1, min(int(seconds), MAX_SECONDS))
    frames = _id3_frame("TIT2", title) + _id3_frame("TPE1", performer)
    tag = b"ID3\x03\x00\x00" + _syncsafe(len(frames)) + frames
    return tag + _FRAME * math.ceil(seconds / _FRAME_SECONDS)


@lru_cache(maxsize=1)
def placeholder_png(size: int = 512) -> bytes:
    """A dark green gradient for tracks without a cover."""
    top, bottom = (0x1D, 0xB9, 0x54), (0x10, 0x10, 0x10)
    raw = bytearray()
    for y in range(size):
        t = y / (size - 1)
        pixel = bytes(int(a * (1 - t) + b * t) for a, b in zip(top, bottom))
        raw += b"\x00" + pixel * size

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
