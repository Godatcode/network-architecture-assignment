import socket
import threading
import unittest

from calculator_server import handle_connection


def read_response(sock, pending=b""):
    data = bytearray(pending)
    while b"\r\n\r\n" not in data:
        data.extend(sock.recv(4096))
    marker = data.index(b"\r\n\r\n")
    head = bytes(data[:marker]).decode("ascii")
    rest = data[marker + 4 :]
    lines = head.split("\r\n")
    headers = dict(line.split(": ", 1) for line in lines[1:])
    length = int(headers["Content-Length"])
    while len(rest) < length:
        rest.extend(sock.recv(4096))
    return lines[0], headers, bytes(rest[:length]), bytes(rest[length:])


class CalculatorTests(unittest.TestCase):
    def setUp(self):
        self.client, server = socket.socketpair()
        self.thread = threading.Thread(target=handle_connection, args=(server, ("local", 0)))
        self.thread.start()

    def tearDown(self):
        self.client.close()
        self.thread.join(timeout=1)

    def send(self, request):
        self.client.sendall(request)
        return read_response(self.client)

    def test_required_operations(self):
        cases = [("add", 2, 3, b"5"), ("sub", 10, 4, b"6"), ("mul", 6, 7, b"42"), ("div", 9, 3, b"3")]
        for operation, a, b, expected in cases:
            request = f"GET /{operation}?a={a}&b={b} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode()
            status, _, body, _ = self.send(request)
            self.assertEqual(status, "HTTP/1.1 200 OK")
            self.assertEqual(body, expected)

    def test_error_statuses(self):
        cases = [
            (b"GET /div?a=1&b=0 HTTP/1.1\r\nHost: localhost\r\n\r\n", "400 Bad Request"),
            (b"GET /add?a=x&b=3 HTTP/1.1\r\nHost: localhost\r\n\r\n", "400 Bad Request"),
            (b"GET /pow?a=2&b=8 HTTP/1.1\r\nHost: localhost\r\n\r\n", "404 Not Found"),
            (b"POST /add HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\n\r\n", "405 Method Not Allowed"),
            (b"GET /add HTTP/1.1\r\n\r\n", "400 Bad Request"),
        ]
        for request, expected in cases:
            status, _, _, _ = self.send(request)
            self.assertEqual(status, "HTTP/1.1 " + expected)

    def test_six_pipelined_requests_keep_one_connection(self):
        requests = b"".join(
            [
                b"GET /add?a=2&b=3 HTTP/1.1\r\nHost: localhost\r\n\r\n",
                b"GET /sub?a=10&b=4 HTTP/1.1\r\nHost: localhost\r\n\r\n",
                b"GET /mul?a=6&b=7 HTTP/1.1\r\nHost: localhost\r\n\r\n",
                b"GET /div?a=1&b=0 HTTP/1.1\r\nHost: localhost\r\n\r\n",
                b"GET /pow?a=2&b=8 HTTP/1.1\r\nHost: localhost\r\n\r\n",
                b"POST /add HTTP/1.1\r\nHost: localhost\r\nContent-Length: 0\r\nConnection: close\r\n\r\n",
            ]
        )
        self.client.sendall(requests)
        pending = b""
        statuses = []
        bodies = []
        for _ in range(6):
            status, _, body, pending = read_response(self.client, pending)
            statuses.append(status.split()[1])
            bodies.append(body)
        self.assertEqual(statuses, ["200", "200", "200", "400", "404", "405"])
        self.assertEqual(bodies[:3], [b"5", b"6", b"42"])

    def test_chunked_body_is_consumed_before_next_request(self):
        requests = (
            b"GET /add?a=1&b=2 HTTP/1.1\r\nHost: localhost\r\nTransfer-Encoding: chunked\r\n\r\n"
            b"3\r\nabc\r\n0\r\n\r\n"
            b"GET /mul?a=3&b=4 HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        )
        self.client.sendall(requests)
        first = read_response(self.client)
        second = read_response(self.client, first[3])
        self.assertEqual(first[2], b"3")
        self.assertEqual(second[2], b"12")


if __name__ == "__main__":
    unittest.main()
