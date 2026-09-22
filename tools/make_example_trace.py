#!/usr/bin/env python3
"""Create the submitted trace from the same codec and file as the programs."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bcurl import request_bytes
from bserve import response
from binary_protocol import hexdump


BODY = (ROOT / "www" / "index.html").read_bytes()
REQUEST = request_bytes("localhost", 9000, "/index.html", 1)
RESPONSE = response(1, 200, BODY, "text/html; charset=utf-8")


document = f"""# Annotated BCP request and response

This is one complete `GET /index.html` exchange. Both frames were produced by the submitted codec. Multi-byte integers are big-endian; offsets are hexadecimal.

## Request ({len(REQUEST)} bytes)

### Fixed header, offsets 0x00-0x0b

| Offset | Bytes | Interpretation |
|---:|---|---|
| 00 | `42 43` | magic `BC` |
| 02 | `01` | version 1 |
| 03 | `01` | request frame |
| 04 | `01` | `END_STREAM` |
| 05 | `05` | five header fields |
| 06 | `00 01` | stream 1 |
| 08 | `{REQUEST[8:12].hex(' ')}` | {len(REQUEST) - 12} payload bytes |

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
{hexdump(REQUEST)}
```

## Response ({len(RESPONSE)} bytes)

### Fixed header, offsets 0x00-0x0b

| Offset | Bytes | Interpretation |
|---:|---|---|
| 00 | `42 43` | magic `BC` |
| 02 | `01` | version 1 |
| 03 | `02` | response frame |
| 04 | `01` | `END_STREAM` |
| 05 | `05` | five header fields |
| 06 | `00 01` | response belongs to stream 1 |
| 08 | `{RESPONSE[8:12].hex(' ')}` | {len(RESPONSE) - 12} payload bytes |

### Response payload

| Header | Encoding |
|---|---|
| `:status: 200` | code 6, value length 3 |
| `content-length: {len(BODY)}` | code 7, decimal byte count of the file |
| `content-type: text/html; charset=utf-8` | code 8 |
| `server: bserve/1.0` | code 9 |
| `connection: keep-alive` | code 10 |

Immediately after the fifth header value, the remaining {len(BODY)} payload bytes are the file body. The `3c 21 64 6f ...` sequence begins `<!do...`; no delimiter is needed because the frame payload length and the decoded header lengths identify both boundaries.

```text
{hexdump(RESPONSE)}
```
"""

(ROOT / "docs" / "annotated-hexdump.md").write_text(document, encoding="utf-8")
