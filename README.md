# Persistent Socket Protocols

This repository contains both parts of the networking assignment:

- an HTTP/1.1 calculator that serves several requests on one TCP connection; and
- a small binary protocol, with a static-file server, client, specification, and annotated byte trace.

The runtime programs use only the Python standard library. There is no web framework and no HTTP library in the server. The checked-in PDF is ready to submit; its optional rebuild script uses ReportLab.

## 1. HTTP/1.1 calculator

Start the server:

```sh
./calculator_server.py 8080
```

The four routes are `/add`, `/sub`, `/mul`, and `/div`. Each expects exactly one `a` and one `b` query parameter.

```sh
curl 'http://127.0.0.1:8080/add?a=2&b=3'
curl 'http://127.0.0.1:8080/sub?a=10&b=4'
curl 'http://127.0.0.1:8080/mul?a=6&b=7'
curl 'http://127.0.0.1:8080/div?a=9&b=3'
```

To see persistence and pipelining directly, send several requests before reading any response:

```python
import socket

s = socket.create_connection(("127.0.0.1", 8080))
s.sendall(
    b"GET /add?a=2&b=3 HTTP/1.1\r\nHost: localhost\r\n\r\n"
    b"GET /mul?a=6&b=7 HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
)
print(s.recv(4096).decode())
```

The request reader keeps a private buffer. It stops after the declared body length and leaves the following bytes untouched for the next request. It also understands chunked request bodies, applies a 10-second idle timeout, and honors `Connection: close`.

## 2. Binary Content Protocol

Start the file server in one terminal:

```sh
./bserve ./www 9000
```

Fetch a file in another terminal:

```sh
./bcurl -v localhost:9000/index.html
```

`-v` writes the request and response hexdumps to standard error while the response body goes to standard output. Multiple targets reuse one TCP connection:

```sh
./bcurl localhost:9000/index.html localhost:9000/missing.txt
```

The second command exits with status 22 because one response is a 4xx. Targets with different hosts or ports are rejected, since `bcurl` promises to open exactly one connection.

## Submitted material

- [`docs/protocol-specification.pdf`](docs/protocol-specification.pdf) - the two-page wire specification
- [`docs/protocol-specification.md`](docs/protocol-specification.md) - an accessible source copy
- [`docs/annotated-hexdump.md`](docs/annotated-hexdump.md) - one complete request and response, byte for byte
- `bserve`, `bcurl`, `binary_protocol.py` - the binary server, client, and shared codec
- `calculator_server.py` - the HTTP/1.1 calculator

## Tests

Run the full suite with:

```sh
make test
```

The tests cover the required status codes, six pipelined HTTP requests, chunk boundaries, connection reuse, malformed binary frames, unknown frame types, missing files, and path traversal.
