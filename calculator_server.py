#!/usr/bin/env python3
"""A small HTTP/1.1 calculator built directly on TCP sockets."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from decimal import Decimal, DecimalException, InvalidOperation
import socket
import threading
from urllib.parse import parse_qs, urlsplit


MAX_HEADER_BYTES = 16 * 1024
MAX_BODY_BYTES = 1024 * 1024
READ_SIZE = 4096
IDLE_TIMEOUT_SECONDS = 10.0


class HTTPError(Exception):
    def __init__(self, status: int, reason: str, message: str, headers=None):
        super().__init__(message)
        self.status = status
        self.reason = reason
        self.message = message
        self.headers = headers or {}


@dataclass
class Request:
    method: str
    target: str
    version: str
    headers: dict[str, str]
    body: bytes


class RequestReader:
    """Buffered reader that leaves bytes for the next pipelined request."""

    def __init__(self, connection: socket.socket):
        self.connection = connection
        self.buffer = bytearray()

    def _receive(self) -> bool:
        chunk = self.connection.recv(READ_SIZE)
        if not chunk:
            return False
        self.buffer.extend(chunk)
        return True

    def _read_exact(self, size: int) -> bytes:
        while len(self.buffer) < size:
            if not self._receive():
                raise HTTPError(400, "Bad Request", "request body ended early")
        result = bytes(self.buffer[:size])
        del self.buffer[:size]
        return result

    def _read_line(self, limit: int = MAX_HEADER_BYTES) -> bytes:
        while True:
            end = self.buffer.find(b"\r\n")
            if end >= 0:
                result = bytes(self.buffer[:end])
                del self.buffer[: end + 2]
                return result
            if len(self.buffer) > limit:
                raise HTTPError(431, "Request Header Fields Too Large", "header line is too long")
            if not self._receive():
                raise HTTPError(400, "Bad Request", "request ended before a complete line")

    def _read_chunked_body(self) -> bytes:
        body = bytearray()
        while True:
            raw_size = self._read_line(128).split(b";", 1)[0]
            try:
                size = int(raw_size, 16)
            except ValueError as exc:
                raise HTTPError(400, "Bad Request", "invalid chunk size") from exc
            if size < 0 or len(body) + size > MAX_BODY_BYTES:
                raise HTTPError(413, "Content Too Large", "request body is too large")
            if size == 0:
                while self._read_line():
                    pass
                return bytes(body)
            body.extend(self._read_exact(size))
            if self._read_exact(2) != b"\r\n":
                raise HTTPError(400, "Bad Request", "chunk is missing its terminating CRLF")

    def read_request(self) -> Request | None:
        while b"\r\n\r\n" not in self.buffer:
            if len(self.buffer) > MAX_HEADER_BYTES:
                raise HTTPError(431, "Request Header Fields Too Large", "request headers are too large")
            if not self._receive():
                if not self.buffer:
                    return None
                raise HTTPError(400, "Bad Request", "request headers ended early")

        marker = self.buffer.find(b"\r\n\r\n")
        if marker > MAX_HEADER_BYTES:
            raise HTTPError(431, "Request Header Fields Too Large", "request headers are too large")
        head = bytes(self.buffer[:marker])
        del self.buffer[: marker + 4]

        try:
            lines = head.decode("iso-8859-1").split("\r\n")
            method, target, version = lines[0].split(" ")
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPError(400, "Bad Request", "malformed request line") from exc

        headers: dict[str, str] = {}
        for line in lines[1:]:
            if not line or ":" not in line:
                raise HTTPError(400, "Bad Request", "malformed header line")
            name, value = line.split(":", 1)
            name = name.strip().lower()
            value = value.strip()
            if not name or any(ch.isspace() for ch in name):
                raise HTTPError(400, "Bad Request", "invalid header name")
            if name in headers:
                if name == "content-length" and headers[name] == value:
                    continue
                raise HTTPError(400, "Bad Request", f"duplicate {name} header")
            else:
                headers[name] = value

        transfer_encoding = headers.get("transfer-encoding", "").lower()
        if transfer_encoding and "content-length" in headers:
            raise HTTPError(400, "Bad Request", "both Transfer-Encoding and Content-Length were sent")
        if transfer_encoding:
            encodings = [part.strip() for part in transfer_encoding.split(",")]
            if encodings != ["chunked"]:
                raise HTTPError(501, "Not Implemented", "only chunked transfer encoding is supported")
            body = self._read_chunked_body()
        else:
            raw_length = headers.get("content-length", "0")
            try:
                content_length = int(raw_length)
            except ValueError as exc:
                raise HTTPError(400, "Bad Request", "invalid Content-Length") from exc
            if content_length < 0:
                raise HTTPError(400, "Bad Request", "invalid Content-Length")
            if content_length > MAX_BODY_BYTES:
                raise HTTPError(413, "Content Too Large", "request body is too large")
            body = self._read_exact(content_length)

        return Request(method, target, version, headers, body)


def _format_number(value: Decimal) -> str:
    if not value.is_finite():
        raise HTTPError(400, "Bad Request", "operands must be finite numbers")
    if value == value.to_integral():
        return str(value.quantize(Decimal(1)))
    return format(value.normalize(), "f")


def calculate(request: Request) -> tuple[int, str, bytes, dict[str, str]]:
    if request.version != "HTTP/1.1":
        raise HTTPError(505, "HTTP Version Not Supported", "this server requires HTTP/1.1")
    if "host" not in request.headers:
        raise HTTPError(400, "Bad Request", "HTTP/1.1 requires a Host header")

    parsed = urlsplit(request.target)
    operation = parsed.path.lstrip("/")
    if operation not in {"add", "sub", "mul", "div"}:
        raise HTTPError(404, "Not Found", "unknown calculator operation")
    if request.method != "GET":
        raise HTTPError(405, "Method Not Allowed", "calculator routes only accept GET", {"Allow": "GET"})

    values = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=False)
    if set(values) != {"a", "b"} or len(values["a"]) != 1 or len(values["b"]) != 1:
        raise HTTPError(400, "Bad Request", "query must contain one a and one b operand")
    if len(values["a"][0]) > 128 or len(values["b"][0]) > 128:
        raise HTTPError(400, "Bad Request", "operands are too long")
    try:
        a = Decimal(values["a"][0])
        b = Decimal(values["b"][0])
    except InvalidOperation as exc:
        raise HTTPError(400, "Bad Request", "a and b must be numbers") from exc
    if not a.is_finite() or not b.is_finite():
        raise HTTPError(400, "Bad Request", "a and b must be finite numbers")

    try:
        if operation == "add":
            result = a + b
        elif operation == "sub":
            result = a - b
        elif operation == "mul":
            result = a * b
        else:
            if b == 0:
                raise HTTPError(400, "Bad Request", "division by zero")
            result = a / b
        rendered = _format_number(result)
    except DecimalException as exc:
        raise HTTPError(400, "Bad Request", "operands are outside the supported numeric range") from exc
    return 200, "OK", rendered.encode("ascii"), {}


def make_response(status: int, reason: str, body: bytes, extra_headers=None, close=False) -> bytes:
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Length": str(len(body)),
        "Connection": "close" if close else "keep-alive",
        "Server": "line-calculator/1.0",
    }
    headers.update(extra_headers or {})
    lines = [f"HTTP/1.1 {status} {reason}"]
    lines.extend(f"{name}: {value}" for name, value in headers.items())
    return ("\r\n".join(lines) + "\r\n\r\n").encode("ascii") + body


def handle_connection(connection: socket.socket, address) -> None:
    connection.settimeout(IDLE_TIMEOUT_SECONDS)
    reader = RequestReader(connection)
    try:
        while True:
            try:
                request = reader.read_request()
                if request is None:
                    break
                should_close = request.headers.get("connection", "").lower() == "close"
                try:
                    status, reason, body, headers = calculate(request)
                except HTTPError as error:
                    status, reason = error.status, error.reason
                    body = error.message.encode("utf-8")
                    headers = error.headers
                connection.sendall(make_response(status, reason, body, headers, should_close))
                if should_close:
                    break
            except socket.timeout:
                break
            except HTTPError as error:
                connection.sendall(make_response(error.status, error.reason, error.message.encode(), error.headers, True))
                break
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        connection.close()


def serve(host: str, port: int, ready: threading.Event | None = None) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen()
        actual_port = server.getsockname()[1]
        print(f"calculator listening on {host or '0.0.0.0'}:{actual_port}", flush=True)
        if ready:
            ready.set()
        while True:
            connection, address = server.accept()
            threading.Thread(target=handle_connection, args=(connection, address), daemon=True).start()


def main() -> None:
    parser = argparse.ArgumentParser(description="HTTP/1.1 calculator server")
    parser.add_argument("port", nargs="?", type=int, default=8080)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    try:
        serve(args.host, args.port)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
