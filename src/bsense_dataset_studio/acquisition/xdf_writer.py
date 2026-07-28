"""Minimal thread-safe XDF writer."""

from __future__ import annotations

import struct
import threading
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Sequence

FILE_HEADER, STREAM_HEADER, SAMPLES, CLOCK_OFFSET, BOUNDARY, STREAM_FOOTER = range(1, 7)
BOUNDARY_UUID = bytes((0x43, 0xA5, 0x46, 0xDC, 0xCB, 0xF5, 0x41, 0x0F, 0xB3, 0x0E, 0xD5, 0x46, 0x73, 0x83, 0xCB, 0xE4))


def encode_varlen_int(value: int) -> bytes:
    if value < 0:
        raise ValueError("XDF variable-length integers cannot be negative")
    if value < 256:
        return b"\x01" + struct.pack("<B", value)
    if value <= 0xFFFFFFFF:
        return b"\x04" + struct.pack("<I", value)
    return b"\x08" + struct.pack("<Q", value)


class XDFWriter:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file: BinaryIO = self.path.open("xb")
        self._lock = threading.Lock()
        self._closed = False
        self._file.write(b"XDF:")
        timestamp = datetime.now().astimezone().isoformat()
        self._write_chunk(FILE_HEADER, f'<?xml version="1.0"?><info><version>1.0</version><datetime>{timestamp}</datetime></info>'.encode())

    def _write_chunk(self, tag: int, content: bytes, stream_id: int | None = None) -> None:
        prefix = b"" if stream_id is None else struct.pack("<I", stream_id)
        self._file.write(encode_varlen_int(2 + len(prefix) + len(content)))
        self._file.write(struct.pack("<H", tag) + prefix + content)
        self._file.flush()

    def write_stream_header(self, stream_id: int, xml: str) -> None:
        with self._lock:
            self._write_chunk(STREAM_HEADER, xml.encode("utf-8"), stream_id)

    def write_samples(self, stream_id: int, timestamps: Sequence[float], samples: Sequence[Sequence[object]], channel_count: int, channel_format: int) -> None:
        if not timestamps:
            return
        if len(timestamps) != len(samples):
            raise ValueError("timestamp/sample count mismatch")
        formats = {1: "f", 2: "d", 4: "i", 5: "h", 6: "b", 7: "q"}
        sample_struct = struct.Struct("<" + formats[channel_format] * channel_count) if channel_format in formats else None
        if channel_format != 3 and sample_struct is None:
            raise ValueError(f"unsupported LSL channel format: {channel_format}")
        payload = bytearray(encode_varlen_int(len(timestamps)))
        for timestamp, sample in zip(timestamps, samples, strict=True):
            if len(sample) != channel_count:
                raise ValueError("sample channel count mismatch")
            payload.extend(b"\x08" + struct.pack("<d", float(timestamp)))
            if channel_format == 3:
                for value in sample:
                    encoded = str(value).encode("utf-8")
                    payload.extend(encode_varlen_int(len(encoded)) + encoded)
            else:
                payload.extend(sample_struct.pack(*sample))
        with self._lock:
            self._write_chunk(SAMPLES, bytes(payload), stream_id)

    def write_clock_offset(self, stream_id: int, collection_time: float, offset: float) -> None:
        with self._lock:
            self._write_chunk(CLOCK_OFFSET, struct.pack("<dd", collection_time, offset), stream_id)

    def write_stream_footer(self, stream_id: int, first: float, last: float, count: int) -> None:
        xml = f'<?xml version="1.0"?><info><first_timestamp>{first}</first_timestamp><last_timestamp>{last}</last_timestamp><sample_count>{count}</sample_count></info>'
        with self._lock:
            self._write_chunk(STREAM_FOOTER, xml.encode(), stream_id)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._file.close()
                self._closed = True

    def __enter__(self) -> "XDFWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
