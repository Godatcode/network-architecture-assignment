#!/usr/bin/env python3
"""Wire-format helpers shared by bserve and bcurl."""

from __future__ import annotations

from dataclasses import dataclass
import socket
import struct


MAGIC = b"BC"
VERSION = 1
FIXED_HEADER = struct.Struct("!2sBBBBHI")
FIXED_HEADER_SIZE = FIXED_HEADER.size
MAX_PAYLOAD = 8 * 1024 * 1024

TYPE_REQUEST = 1
TYPE_RESPONSE = 2
FLAG_END_STREAM = 0x01

STATIC_HEADERS = {
    1: ":method",
    2: ":path",
    3: "host",
    4: "user-agent",
    5: "accept",
    6: ":status",
    7: "content-length",
    8: "content-type",
    9: "server",
    10: "connection",
}
HEADER_CODES = {name: code for code, name in STATIC_HEADERS.items()}


class ProtocolError(Exception):
    pass


@dataclass
class Frame:
    frame_type: int
    flags: int
    stream_id: int
    headers: list[tuple[str, str]]
    body: bytes
    raw: bytes


def read_exact(sock: socket.socket, size: int) -> bytes | None:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            if not data:
                return None
            raise ProtocolError("connection ended in the middle of a frame")
        data.extend(chunk)
    return bytes(data)


def encode_headers(headers: list[tuple[str, str]]) -> bytes:
    encoded = bytearray()
    for name, value in headers:
        name_bytes = name.lower().encode("ascii")
        value_bytes = value.encode("utf-8")
        code = HEADER_CODES.get(name.lower(), 0)
        encoded.append(code)
        if code == 0:
            if not name_bytes or len(name_bytes) > 255:
                raise ProtocolError("literal header names must be 1 to 255 bytes")
            encoded.append(len(name_bytes))
            encoded.extend(name_bytes)
        if len(value_bytes) > 65535:
            raise ProtocolError("header values cannot exceed 65535 bytes")
        encoded.extend(struct.pack("!H", len(value_bytes)))
        encoded.extend(value_bytes)
    return bytes(encoded)


def decode_headers(payload: bytes, count: int) -> tuple[list[tuple[str, str]], int]:
    headers: list[tuple[str, str]] = []
    offset = 0
    for _ in range(count):
        if offset >= len(payload):
            raise ProtocolError("header block ended early")
        code = payload[offset]
        offset += 1
        if code == 0:
            if offset >= len(payload):
                raise ProtocolError("literal header name length is missing")
            name_length = payload[offset]
            offset += 1
            if name_length == 0 or offset + name_length > len(payload):
                raise ProtocolError("invalid literal header name")
            try:
                name = payload[offset : offset + name_length].decode("ascii")
            except UnicodeDecodeError as exc:
                raise ProtocolError("literal header name is not ASCII") from exc
            if name != name.lower() or any(ch.isspace() for ch in name) or ":" in name:
                raise ProtocolError("literal header name must be lowercase and contain no spaces or colon")
            offset += name_length
        else:
            try:
                name = STATIC_HEADERS[code]
            except KeyError as exc:
                raise ProtocolError(f"unknown static header code {code}") from exc
        if offset + 2 > len(payload):
            raise ProtocolError("header value length is missing")
        value_length = struct.unpack_from("!H", payload, offset)[0]
        offset += 2
        if offset + value_length > len(payload):
            raise ProtocolError("header value ended early")
        try:
            value = payload[offset : offset + value_length].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("header value is not UTF-8") from exc
        offset += value_length
        headers.append((name, value))
    return headers, offset


def encode_frame(frame_type: int, stream_id: int, headers: list[tuple[str, str]], body=b"", flags=FLAG_END_STREAM) -> bytes:
    if not 0 <= stream_id <= 65535:
        raise ProtocolError("stream id must fit in 16 bits")
    if len(headers) > 255:
        raise ProtocolError("a frame can contain at most 255 headers")
    header_block = encode_headers(headers)
    payload = header_block + body
    if len(payload) > MAX_PAYLOAD:
        raise ProtocolError("frame payload is too large")
    fixed = FIXED_HEADER.pack(MAGIC, VERSION, frame_type, flags, len(headers), stream_id, len(payload))
    return fixed + payload


def receive_frame(sock: socket.socket) -> Frame | None:
    fixed = read_exact(sock, FIXED_HEADER_SIZE)
    if fixed is None:
        return None
    magic, version, frame_type, flags, count, stream_id, length = FIXED_HEADER.unpack(fixed)
    if magic != MAGIC:
        raise ProtocolError("bad frame magic")
    if version != VERSION:
        raise ProtocolError(f"unsupported protocol version {version}")
    if flags != FLAG_END_STREAM:
        raise ProtocolError("version 1 frames must set only END_STREAM")
    if length > MAX_PAYLOAD:
        raise ProtocolError("frame payload is too large")
    payload = read_exact(sock, length)
    if payload is None:
        raise ProtocolError("frame payload is missing")
    if frame_type not in {TYPE_REQUEST, TYPE_RESPONSE}:
        # Unknown types are length-delimited. Their payload is opaque so a
        # receiver can skip the frame without understanding its layout.
        return Frame(frame_type, flags, stream_id, [], payload, fixed + payload)
    headers, body_offset = decode_headers(payload, count)
    return Frame(frame_type, flags, stream_id, headers, payload[body_offset:], fixed + payload)


def header_map(headers: list[tuple[str, str]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, value in headers:
        if name in result:
            raise ProtocolError(f"duplicate header: {name}")
        result[name] = value
    return result


def hexdump(data: bytes) -> str:
    lines = []
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hex_part = " ".join(f"{byte:02x}" for byte in chunk)
        ascii_part = "".join(chr(byte) if 32 <= byte < 127 else "." for byte in chunk)
        lines.append(f"{offset:04x}  {hex_part:<47}  |{ascii_part}|")
    return "\n".join(lines)
