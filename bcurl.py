#!/usr/bin/env python3
"""Command-line client for the Binary Content Protocol."""

from __future__ import annotations

import argparse
import socket
import sys
from urllib.parse import urlsplit

from binary_protocol import TYPE_REQUEST, TYPE_RESPONSE, ProtocolError, encode_frame, header_map, hexdump, receive_frame


def parse_target(target: str) -> tuple[str, int, str]:
    value = target if "://" in target else f"bcp://{target}"
    parsed = urlsplit(value)
    if not parsed.hostname:
        raise ValueError(f"invalid target: {target}")
    try:
        port = parsed.port or 9000
    except ValueError as exc:
        raise ValueError(f"invalid port in target: {target}") from exc
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return parsed.hostname, port, path


def request_bytes(host: str, port: int, path: str, stream_id: int) -> bytes:
    headers = [
        (":method", "GET"),
        (":path", path),
        ("host", f"{host}:{port}"),
        ("user-agent", "bcurl/1.0"),
        ("accept", "*/*"),
    ]
    return encode_frame(TYPE_REQUEST, stream_id, headers)


def run(targets: list[str], verbose=False) -> int:
    parsed_targets = [parse_target(target) for target in targets]
    authorities = {(host, port) for host, port, _ in parsed_targets}
    if len(authorities) != 1:
        raise ValueError("all targets must use the same host and port; bcurl opens exactly one connection")
    host, port = next(iter(authorities))
    exit_code = 0
    with socket.create_connection((host, port), timeout=10.0) as connection:
        connection.settimeout(10.0)
        for stream_id, (_, _, path) in enumerate(parsed_targets, start=1):
            raw_request = request_bytes(host, port, path, stream_id)
            if verbose:
                print(f"> request stream={stream_id} ({len(raw_request)} bytes)", file=sys.stderr)
                print(hexdump(raw_request), file=sys.stderr)
            connection.sendall(raw_request)

            while True:
                frame = receive_frame(connection)
                if frame is None:
                    raise ProtocolError("server closed before sending a response")
                if frame.frame_type != TYPE_RESPONSE:
                    if verbose:
                        print(f"< skipped unknown frame type {frame.frame_type}", file=sys.stderr)
                    continue
                if frame.stream_id != stream_id:
                    raise ProtocolError(f"expected stream {stream_id}, received stream {frame.stream_id}")
                break
            headers = header_map(frame.headers)
            try:
                status = int(headers[":status"])
                declared_length = int(headers["content-length"])
            except (KeyError, ValueError) as exc:
                raise ProtocolError("response is missing a valid status or content length") from exc
            if declared_length != len(frame.body):
                raise ProtocolError("response Content-Length does not match its body")
            if verbose:
                print(f"< response stream={stream_id} status={status} ({len(frame.raw)} bytes)", file=sys.stderr)
                print(hexdump(frame.raw), file=sys.stderr)
                for name, value in frame.headers:
                    print(f"< {name}: {value}", file=sys.stderr)
            sys.stdout.buffer.write(frame.body)
            sys.stdout.buffer.flush()
            if 400 <= status <= 599:
                exit_code = 22
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Binary Content Protocol client")
    parser.add_argument("-v", "--verbose", action="store_true", help="show frames and decoded response headers")
    parser.add_argument("targets", nargs="+", help="host:port/path (multiple paths reuse one connection)")
    args = parser.parse_args()
    try:
        raise SystemExit(run(args.targets, args.verbose))
    except (OSError, ProtocolError, ValueError) as error:
        print(f"bcurl: {error}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
