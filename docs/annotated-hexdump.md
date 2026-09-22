# Annotated BCP request and response

This is one complete `GET /index.html` exchange. Both frames were produced by the submitted codec. Multi-byte integers are big-endian; offsets are hexadecimal.

## Request (67 bytes)

### Fixed header, offsets 0x00-0x0b

| Offset | Bytes | Interpretation |
|---:|---|---|
| 00 | `42 43` | magic `BC` |
| 02 | `01` | version 1 |
| 03 | `01` | request frame |
| 04 | `01` | `END_STREAM` |
| 05 | `05` | five header fields |
| 06 | `00 01` | stream 1 |
| 08 | `00 00 00 37` | 55 payload bytes |

### Request payload

| Header | Encoding |
|---|---|
| `:method: GET` | code 1, value length 3, `GET` |
| `:path: /index.html` | code 2, value length 11, `/index.html` |
| `host: localhost:9000` | code 3, value length 14 |
| `user-agent: bcurl/1.0` | code 4, value length 9 |
| `accept: */*` | code 5, value length 3 |

There is no request body. The next byte after the fifth value would begin the next frame.

```text
0000  42 43 01 01 01 05 00 01 00 00 00 37 01 00 03 47  |BC.........7...G|
0010  45 54 02 00 0b 2f 69 6e 64 65 78 2e 68 74 6d 6c  |ET.../index.html|
0020  03 00 0e 6c 6f 63 61 6c 68 6f 73 74 3a 39 30 30  |...localhost:900|
0030  30 04 00 09 62 63 75 72 6c 2f 31 2e 30 05 00 03  |0...bcurl/1.0...|
0040  2a 2f 2a                                         |*/*|
```

## Response (406 bytes)

### Fixed header, offsets 0x00-0x0b

| Offset | Bytes | Interpretation |
|---:|---|---|
| 00 | `42 43` | magic `BC` |
| 02 | `01` | version 1 |
| 03 | `02` | response frame |
| 04 | `01` | `END_STREAM` |
| 05 | `05` | five header fields |
| 06 | `00 01` | response belongs to stream 1 |
| 08 | `00 00 01 8a` | 394 payload bytes |

### Response payload

| Header | Encoding |
|---|---|
| `:status: 200` | code 6, value length 3 |
| `content-length: 329` | code 7, decimal byte count of the file |
| `content-type: text/html; charset=utf-8` | code 8 |
| `server: bserve/1.0` | code 9 |
| `connection: keep-alive` | code 10 |

Immediately after the fifth header value, the remaining 329 payload bytes are the file body. The `3c 21 64 6f ...` sequence begins `<!do...`; no delimiter is needed because the frame payload length and the decoded header lengths identify both boundaries.

```text
0000  42 43 01 02 01 05 00 01 00 00 01 8a 06 00 03 32  |BC.............2|
0010  30 30 07 00 03 33 32 39 08 00 18 74 65 78 74 2f  |00...329...text/|
0020  68 74 6d 6c 3b 20 63 68 61 72 73 65 74 3d 75 74  |html; charset=ut|
0030  66 2d 38 09 00 0a 62 73 65 72 76 65 2f 31 2e 30  |f-8...bserve/1.0|
0040  0a 00 0a 6b 65 65 70 2d 61 6c 69 76 65 3c 21 64  |...keep-alive<!d|
0050  6f 63 74 79 70 65 20 68 74 6d 6c 3e 0a 3c 68 74  |octype html>.<ht|
0060  6d 6c 20 6c 61 6e 67 3d 22 65 6e 22 3e 0a 20 20  |ml lang="en">.  |
0070  3c 68 65 61 64 3e 0a 20 20 20 20 3c 6d 65 74 61  |<head>.    <meta|
0080  20 63 68 61 72 73 65 74 3d 22 75 74 66 2d 38 22  | charset="utf-8"|
0090  3e 0a 20 20 20 20 3c 6d 65 74 61 20 6e 61 6d 65  |>.    <meta name|
00a0  3d 22 76 69 65 77 70 6f 72 74 22 20 63 6f 6e 74  |="viewport" cont|
00b0  65 6e 74 3d 22 77 69 64 74 68 3d 64 65 76 69 63  |ent="width=devic|
00c0  65 2d 77 69 64 74 68 2c 20 69 6e 69 74 69 61 6c  |e-width, initial|
00d0  2d 73 63 61 6c 65 3d 31 22 3e 0a 20 20 20 20 3c  |-scale=1">.    <|
00e0  74 69 74 6c 65 3e 42 69 6e 61 72 79 20 43 6f 6e  |title>Binary Con|
00f0  74 65 6e 74 20 50 72 6f 74 6f 63 6f 6c 3c 2f 74  |tent Protocol</t|
0100  69 74 6c 65 3e 0a 20 20 3c 2f 68 65 61 64 3e 0a  |itle>.  </head>.|
0110  20 20 3c 62 6f 64 79 3e 0a 20 20 20 20 3c 68 31  |  <body>.    <h1|
0120  3e 54 68 65 20 63 6f 6e 6e 65 63 74 69 6f 6e 20  |>The connection |
0130  73 74 61 79 65 64 20 6f 70 65 6e 2e 3c 2f 68 31  |stayed open.</h1|
0140  3e 0a 20 20 20 20 3c 70 3e 54 68 69 73 20 66 69  |>.    <p>This fi|
0150  6c 65 20 77 61 73 20 73 65 72 76 65 64 20 6f 76  |le was served ov|
0160  65 72 20 74 68 65 20 42 69 6e 61 72 79 20 43 6f  |er the Binary Co|
0170  6e 74 65 6e 74 20 50 72 6f 74 6f 63 6f 6c 2e 3c  |ntent Protocol.<|
0180  2f 70 3e 0a 20 20 3c 2f 62 6f 64 79 3e 0a 3c 2f  |/p>.  </body>.</|
0190  68 74 6d 6c 3e 0a                                |html>.|
```
