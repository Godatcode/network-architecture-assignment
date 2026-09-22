#!/usr/bin/env python3
"""Static-file server for the Binary Content Protocol."""

from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path, PurePosixPath
import socket
import threading
from urllib.parse import unquote, urlsplit

from binary_protocol import (
    TYPE_REQUEST,
    TYPE_RESPONSE,
    ProtocolError,
    encode_frame,
    header_map,
    receive_frame,
)


SERVER_NAME = "bserve/1.0"


def response(stream_id: int, status: int, body: bytes, content_type="text/plain; charset=utf-8", close=False) -> bytes:
    headers = [
        (":status", str(status)),
        ("content-length", str(len(body))),
        ("content-type", content_type),
        ("server", SERVER_NAME),
        ("connection", "close" if close else "keep-alive"),
    ]
    return encode_frame(TYPE_RESPONSE, stream_id, headers, body)


def safe_file(root: Path, raw_path: str) -> Path | None:
    root = root.resolve()
    if not raw_path.startswith("/"):
        return None
    index = 0
    while index < len(raw_path):
        if raw_path[index] == "%":
            if index + 2 >= len(raw_path) or any(ch not in "0123456789abcdefABCDEF" for ch in raw_path[index + 1 : index + 3]):
                return None
            index += 3
            continue
        index += 1
    try:
        decoded = unquote(urlsplit(raw_path).path, errors="strict")
    except (UnicodeDecodeError, ValueError):
        return None
    if "\x00" in decoded or "\\" in decoded:
        return None
    relative = PurePosixPath(decoded.lstrip("/"))
    if any(part in {"", ".", ".."} for part in relative.parts):
        return None
    candidate = (root / Path(*relative.parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def handle_request(root: Path, frame) -> bytes:
    if frame.body:
        return response(frame.stream_id, 400, b"GET requests cannot carry a body")
    try:
        headers = header_map(frame.headers)
    except ProtocolError as error:
        return response(frame.stream_id, 400, str(error).encode())
    required = {":method", ":path", "host"}
    if not required.issubset(headers):
        return response(frame.stream_id, 400, b"missing required request header")
    if headers[":method"] != "GET":
        return response(frame.stream_id, 405, b"only GET is supported")
    path = safe_file(root, headers[":path"])
    if path is None:
        return response(frame.stream_id, 400, b"unsafe or malformed path")
    try:
        body = path.read_bytes()
    except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
        return response(frame.stream_id, 404, b"file not found")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if media_type.startswith("text/"):
        media_type += "; charset=utf-8"
    return response(frame.stream_id, 200, body, media_type)


def handle_connection(connection: socket.socket, root: Path) -> None:
    connection.settimeout(15.0)
    try:
        while True:
            try:
                frame = receive_frame(connection)
            except ProtocolError as error:
                connection.sendall(response(0, 400, str(error).encode(), close=True))
                break
            if frame is None:
                break
            if frame.frame_type != TYPE_REQUEST:
                # Length is part of every frame, so unknown types are already
                # consumed and can be skipped without losing synchronization.
                continue
            if frame.stream_id == 0:
                connection.sendall(response(0, 400, b"request stream id must be non-zero", close=True))
                break
            try:
                outgoing = handle_request(root, frame)
            except ProtocolError:
                connection.sendall(response(frame.stream_id, 400, b"file is too large for one frame", close=True))
                break
            connection.sendall(outgoing)
    except (socket.timeout, BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        connection.close()


def serve(root: Path, port: int, host="127.0.0.1") -> None:
    root = root.resolve()
    if not root.is_dir():
        raise SystemExit(f"document root is not a directory: {root}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen()
        actual_port = server.getsockname()[1]
        print(f"serving {root} on {host}:{actual_port}", flush=True)
        while True:
            connection, _ = server.accept()
            threading.Thread(target=handle_connection, args=(connection, root), daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="Binary Content Protocol file server")
    parser.add_argument("root", type=Path)
    parser.add_argument("port", type=int)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    try:
        serve(args.root, args.port, args.host)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
