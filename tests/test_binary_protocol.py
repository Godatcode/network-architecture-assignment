import socket
import tempfile
import threading
import unittest
from pathlib import Path

from binary_protocol import (
    FLAG_END_STREAM,
    FIXED_HEADER,
    MAGIC,
    TYPE_REQUEST,
    TYPE_RESPONSE,
    VERSION,
    encode_frame,
    header_map,
    receive_frame,
)
from bserve import handle_connection


class BinaryProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "index.html").write_bytes(b"hello over one socket")
        self.client, server = socket.socketpair()
        self.thread = threading.Thread(target=handle_connection, args=(server, self.root))
        self.thread.start()

    def tearDown(self):
        self.client.close()
        self.thread.join(timeout=1)
        self.temp.cleanup()

    @staticmethod
    def request(path, stream_id):
        return encode_frame(
            TYPE_REQUEST,
            stream_id,
            [(":method", "GET"), (":path", path), ("host", "localhost:9000")],
        )

    def test_file_and_404_reuse_connection(self):
        self.client.sendall(self.request("/index.html", 1))
        first = receive_frame(self.client)
        self.client.sendall(self.request("/missing.txt", 2))
        second = receive_frame(self.client)
        self.assertEqual(first.frame_type, TYPE_RESPONSE)
        self.assertEqual(first.stream_id, 1)
        self.assertEqual(header_map(first.headers)[":status"], "200")
        self.assertEqual(first.body, b"hello over one socket")
        self.assertEqual(header_map(second.headers)[":status"], "404")

    def test_unknown_frame_is_skipped_cleanly(self):
        opaque = b"payload that has no header encoding"
        unknown = FIXED_HEADER.pack(MAGIC, VERSION, 99, FLAG_END_STREAM, 255, 7, len(opaque)) + opaque
        self.client.sendall(unknown + self.request("/index.html", 8))
        response = receive_frame(self.client)
        self.assertEqual(response.stream_id, 8)
        self.assertEqual(response.body, b"hello over one socket")

    def test_traversal_is_rejected(self):
        self.client.sendall(self.request("/%2e%2e/secret.txt", 3))
        response = receive_frame(self.client)
        self.assertEqual(header_map(response.headers)[":status"], "400")

    def test_malformed_escape_is_rejected(self):
        self.client.sendall(self.request("/bad%2name", 3))
        response = receive_frame(self.client)
        self.assertEqual(header_map(response.headers)[":status"], "400")

    def test_malformed_header_block_gets_400(self):
        payload = b"\x01\x00"  # known header code, incomplete value length
        malformed = FIXED_HEADER.pack(MAGIC, VERSION, TYPE_REQUEST, FLAG_END_STREAM, 1, 4, len(payload)) + payload
        self.client.sendall(malformed)
        response = receive_frame(self.client)
        self.assertEqual(header_map(response.headers)[":status"], "400")

    def test_stream_zero_is_reserved(self):
        self.client.sendall(self.request("/index.html", 0))
        response = receive_frame(self.client)
        headers = header_map(response.headers)
        self.assertEqual(headers[":status"], "400")
        self.assertEqual(headers["connection"], "close")


if __name__ == "__main__":
    unittest.main()
