#!/usr/bin/env python3
"""Build the two-page BCP specification submitted with the project."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "protocol-specification.pdf"


def footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
    canvas.line(18 * mm, 14 * mm, 192 * mm, 14 * mm)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.setFont("Helvetica", 8)
    canvas.drawString(18 * mm, 9 * mm, "Binary Content Protocol - Version 1")
    canvas.drawRightString(192 * mm, 9 * mm, f"Page {document.page}")
    canvas.restoreState()


def body_table(rows, widths):
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#94a3b8")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def build():
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=23,
        textColor=colors.HexColor("#0f172a"),
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )
    subtitle = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#475569"),
        spaceAfter=5 * mm,
    )
    heading = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#1d4ed8"),
        spaceBefore=3 * mm,
        spaceAfter=1.5 * mm,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=11.2,
        textColor=colors.HexColor("#1f2937"),
        spaceAfter=2 * mm,
    )
    note = ParagraphStyle(
        "Note",
        parent=body,
        borderColor=colors.HexColor("#60a5fa"),
        borderWidth=0.7,
        borderPadding=5,
        backColor=colors.HexColor("#eff6ff"),
        spaceBefore=2 * mm,
        spaceAfter=2 * mm,
    )
    mono = ParagraphStyle(
        "Mono",
        parent=body,
        fontName="Courier",
        fontSize=8,
        leading=10.5,
        leftIndent=5 * mm,
        backColor=colors.HexColor("#f1f5f9"),
        borderPadding=4,
    )

    document = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title="Binary Content Protocol - Version 1",
        author="Arka Ghosh",
        subject="Network Architecture course project protocol specification",
    )
    frame = Frame(document.leftMargin, document.bottomMargin, document.width, document.height, id="main")
    document.addPageTemplates(PageTemplate(id="page", frames=[frame], onPage=footer))

    story = [
        Paragraph("Binary Content Protocol (BCP)", title),
        Paragraph("Version 1 | Default TCP port 9000 | Network byte order", subtitle),
        Paragraph("1. Purpose and connection model", heading),
        Paragraph(
            "BCP transfers named files over a reliable TCP byte stream. A client opens one connection and may exchange any number of request/response pairs on it. Each request uses a non-zero stream identifier and its response repeats that identifier. Version 1 clients send a request and read its response before sending the next, so responses stay in request order.",
            body,
        ),
        Paragraph(
            "TCP has no message boundaries. A receiver reads exactly 12 header bytes, obtains the payload length, then reads exactly that many payload bytes. A short recv() is normal. End-of-file in either part is a protocol error.",
            body,
        ),
        Paragraph("2. Fixed frame header", heading),
        body_table(
            [
                ["Offset", "Width", "Field", "Meaning"],
                ["0", "2", "magic", "ASCII BC (42 43 hex)"],
                ["2", "1", "version", "1 for this specification"],
                ["3", "1", "type", "1 request; 2 response; other values unrecognized"],
                ["4", "1", "flags", "bit 0 END_STREAM; bits 1-7 zero"],
                ["5", "1", "header count", "fields at the start of the payload"],
                ["6", "2", "stream id", "unsigned correlation id; 0 reserved for connection errors"],
                ["8", "4", "payload length", "bytes after this header; implementation maximum 8 MiB"],
            ],
            [13 * mm, 13 * mm, 27 * mm, 117 * mm],
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            "Two magic bytes reject the wrong protocol early. Eight-bit version and type fields leave extension space. A 16-bit stream id is sufficient for a sequential client and allows future multiplexing. The 32-bit length makes every frame skippable; the 8 MiB implementation limit bounds memory use. END_STREAM is set on every version 1 frame because each message fits in one frame.",
            body,
        ),
        Paragraph(
            "Forward compatibility: a receiver that meets an unrecognized frame type MUST read and discard exactly its declared payload length, then continue at the next frame. Header count and payload contents are opaque for that frame.",
            note,
        ),
        Paragraph("3. Header block and body", heading),
        Paragraph("The payload begins with exactly header-count fields. Any bytes left after those fields are the body.", body),
        Paragraph(
            "indexed: code (1) | value length (2) | UTF-8 value<br/>literal: 0 (1) | name length (1) | ASCII name | value length (2) | UTF-8 value",
            mono,
        ),
        Paragraph(
            "Lengths are unsigned big-endian integers. Literal names contain 1-255 lowercase ASCII bytes. Values contain at most 65,535 bytes. Duplicate names are invalid. Code 0 permits uncommon names without shared dynamic state.",
            body,
        ),
        PageBreak(),
        Paragraph("Binary Content Protocol (BCP)", title),
        Paragraph("Version 1 - Messages and receiver behavior", subtitle),
        Paragraph("4. Static header-name table", heading),
        body_table(
            [
                ["Code", "Name", "Direction", "Use"],
                ["1", ":method", "client", "request method; GET in version 1"],
                ["2", ":path", "client", "origin-form resource path"],
                ["3", "host", "client", "server authority"],
                ["4", "user-agent", "client", "client identifier"],
                ["5", "accept", "client", "acceptable media types"],
                ["6", ":status", "server", "three-digit decimal result"],
                ["7", "content-length", "server", "body size in decimal bytes"],
                ["8", "content-type", "server", "body media type"],
                ["9", "server", "server", "server identifier"],
                ["10", "connection", "server", "keep-alive or close"],
            ],
            [13 * mm, 36 * mm, 24 * mm, 97 * mm],
        ),
        Paragraph("5. Request and response", heading),
        Paragraph(
            "A request has type 1 and an empty body. It requires :method=GET, an origin-form :path beginning with /, and host. user-agent and accept are normally included. A response has type 2 and repeats the stream id. It requires decimal :status, decimal content-length, content-type, server, and connection. Content length must equal the body byte count.",
            body,
        ),
        Paragraph(
            "The server percent-decodes the path and maps it beneath its configured root. It rejects NUL, backslash, malformed escape, and .. traversal. A directory maps to index.html. Query text is not part of the filesystem path.",
            body,
        ),
        Paragraph("6. Status and error handling", heading),
        body_table(
            [
                ["Status", "Meaning"],
                ["200", "The response body is the requested file."],
                ["400", "The frame, required headers, or path is malformed."],
                ["404", "The mapped file is unavailable."],
                ["405", "The request method is not supported."],
            ],
            [24 * mm, 146 * mm],
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            "The client exits non-zero for 4xx or 5xx. Bad magic, unsupported version, unknown flag bits, excessive length, truncation, and invalid header encoding are connection-level errors. When framing is still safe, the server sends status 400 on stream 0 with connection=close and closes. Otherwise it closes immediately. Unknown frame types are not errors and follow the mandatory skip rule.",
            body,
        ),
        Paragraph("7. Connection lifetime", heading),
        Paragraph(
            "One TCP connection carries all requests for the same authority. Either peer may close an idle connection; the reference server waits 15 seconds. Normal closure occurs only between complete frames. The version 1 client does not pipeline, but the stream id leaves room for a later version to define multiplexing without changing the fixed header.",
            body,
        ),
        Paragraph("Receiver checklist", heading),
        Paragraph(
            "1. Read 12 bytes exactly. 2. Validate magic, version, flags, and length. 3. Read payload exactly. 4. Skip unknown types without parsing. 5. Decode exactly header-count fields. 6. Treat the remainder as body. 7. Validate required fields and body length. 8. Continue at the next 12-byte header.",
            note,
        ),
    ]
    document.build(story)


if __name__ == "__main__":
    build()
