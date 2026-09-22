# Binary Content Protocol (BCP), version 1

Status: course-project specification

Default TCP port: 9000

Byte order: network byte order (big-endian)

## 1. Purpose and connection model

BCP transfers named files over a reliable TCP byte stream. A client opens one connection and may exchange any number of request/response pairs on it. The client assigns a non-zero stream identifier to each request. The response repeats that identifier. Version 1 clients send a request and read its response before sending the next request, so responses are in request order.

TCP does not preserve message boundaries. A receiver must first read exactly the 12-byte frame header, obtain the payload length, and then read exactly that many payload bytes. A short `recv()` is normal and does not end a frame. End-of-file in the middle of either part is a protocol error.

## 2. Fixed frame header

Every frame starts with the following 12 bytes:

| Offset | Width | Field | Meaning |
|---:|---:|---|---|
| 0 | 2 | magic | ASCII `BC` (`42 43` hex), used to reject the wrong protocol early |
| 2 | 1 | version | `1` for this specification |
| 3 | 1 | type | `1` request, `2` response; all other values are unrecognized |
| 4 | 1 | flags | bit 0 is `END_STREAM`; bits 1-7 are zero in version 1 |
| 5 | 1 | header count | number of header fields at the start of the payload |
| 6 | 2 | stream id | unsigned request/response correlation number; 0 is reserved for connection errors |
| 8 | 4 | payload length | unsigned number of bytes following this header, maximum 8 MiB |

Two magic bytes make accidental matches unlikely while keeping the header small. The 8-bit version and type fields leave ample extension space. A 16-bit stream identifier is enough for a sequential command-line client and permits future multiplexing. The 32-bit payload length makes every frame skippable and supports ordinary files; implementations impose the smaller 8 MiB safety limit.

`END_STREAM` is set on every version 1 frame because each message fits in one frame. It reserves a clear route to multi-frame messages later.

**Forward compatibility rule:** a receiver that encounters an unrecognized frame type MUST read and discard exactly its payload length and then continue with the next frame. Its header count and payload contents are opaque. This rule is mandatory.

## 3. Header block and body

The payload begins with exactly `header count` fields. Any remaining payload bytes are the body. A field is encoded as follows:

```text
indexed name:  name code (1) | value length (2) | UTF-8 value
literal name:  0 (1) | name length (1) | ASCII name | value length (2) | UTF-8 value
```

Name and value lengths are unsigned big-endian integers. Literal names are 1-255 bytes, lowercase, and case-sensitive after decoding. Values are at most 65,535 bytes. Duplicate names are invalid in version 1.

The static name table is:

| Code | Name | Sent by |
|---:|---|---|
| 1 | `:method` | client |
| 2 | `:path` | client |
| 3 | `host` | client |
| 4 | `user-agent` | client |
| 5 | `accept` | client |
| 6 | `:status` | server |
| 7 | `content-length` | server |
| 8 | `content-type` | server |
| 9 | `server` | server |
| 10 | `connection` | server |

The table removes repeated name bytes without requiring shared dynamic state. Code 0 keeps the format extensible for uncommon headers.

## 4. Messages

A request has type 1, an empty body, and these required headers: `:method` equal to `GET`, an origin-form `:path` beginning with `/`, and `host`. `user-agent` and `accept` are normally sent. Other methods receive status 405.

A response has type 2 and repeats the request's stream id. It requires decimal `:status`, decimal `content-length`, `content-type`, `server`, and `connection`. The content length must equal the number of body bytes. A 2xx body is the requested file; an error body is UTF-8 explanatory text.

The server maps the decoded path beneath its configured document root. It rejects NUL bytes, backslashes, malformed percent escapes, and `..` traversal. A directory maps to its `index.html`. Query text is not part of the filesystem path.

## 5. Status and error handling

The defined statuses are 200 (file returned), 400 (malformed frame, missing header, or unsafe path), 404 (file unavailable), and 405 (method unsupported). The client exits non-zero for any 4xx or 5xx response.

Bad magic, unsupported version, unknown flag bits, excessive length, truncated payloads, or malformed header encodings are connection-level errors. When possible, the server sends a 400 response on stream 0 with `connection: close`, then closes. If it cannot frame a response safely, it closes immediately. An unknown frame type is not an error and follows the mandatory skip rule above.

Either peer may close an idle connection. The reference server uses a 15-second idle timeout. Normal connection closure occurs only between complete frames.
