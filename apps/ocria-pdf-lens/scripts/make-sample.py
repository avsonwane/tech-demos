#!/usr/bin/env python3
"""Build public/sample/invoice-scan.pdf: a two-page image-only scan with a table.

There is no text layer. OCRia-nano-1 has to read the pixels.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PAGE_W = 612
PAGE_H = 792
SCALE = 3
PAPER = (247, 243, 234)
INK = (28, 25, 21)
RULE = (120, 110, 98)
BAND = (236, 226, 208)
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "public" / "sample" / "invoice-scan.pdf"


def px(value: float) -> int:
    return int(round(value * SCALE))


def font(path: str, points: float) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, px(points))


def new_page() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (px(PAGE_W), px(PAGE_H)), PAPER)
    return image, ImageDraw.Draw(image)


def text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], value: str, face: ImageFont.FreeTypeFont) -> None:
    draw.text((px(xy[0]), px(xy[1])), value, fill=INK, font=face)


def hline(draw: ImageDraw.ImageDraw, x0: float, x1: float, y: float) -> None:
    draw.line((px(x0), px(y), px(x1), px(y)), fill=RULE, width=max(1, px(0.8)))


def jpeg(image: Image.Image) -> tuple[bytes, int, int]:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=92, subsampling=0, optimize=True)
    return buf.getvalue(), image.width, image.height


def page_invoice() -> tuple[bytes, int, int]:
    image, draw = new_page()
    text(draw, (48, 46), "NORTHWIND SUPPLY", font(SERIF_BOLD, 22))
    hline(draw, 48, 564, 82)
    text(draw, (48, 96), "Invoice 1842", font(SANS_BOLD, 14))
    text(draw, (48, 118), "12 March 2026", font(SANS, 12))
    text(draw, (48, 156), "Bill to", font(SANS_BOLD, 11))
    text(draw, (48, 182), "Ada Lovelace", font(SANS, 13))
    text(draw, (48, 214), "Analytical Engines", font(SANS, 13))
    text(draw, (48, 246), "12 Threadneedle Street", font(SANS, 13))

    top = 300
    row_h = 36
    cols = [48, 280, 390, 470, 564]
    rows = [
        ["Item", "Qty", "Price", "Amount"],
        ["Copper wire", "3 units", "12.50", "37.50"],
        ["Brass gears", "8 units", "4.00", "32.00"],
        ["Oak panel", "1 unit", "46.00", "46.00"],
    ]
    draw.rectangle((px(cols[0]), px(top), px(cols[-1]), px(top + row_h)), fill=BAND)
    for r in range(len(rows) + 1):
        hline(draw, cols[0], cols[-1], top + r * row_h)
    hline(draw, cols[0], cols[0], top)  # keep the left edge drawn as a vertical below
    for x in cols:
        draw.line((px(x), px(top), px(x), px(top + row_h * len(rows))), fill=RULE, width=max(1, px(0.8)))
    body = font(SANS, 13)
    body_bold = font(SANS_BOLD, 13)
    qty = font(SANS_BOLD, 14)
    mono = font(MONO, 13)
    for r, row in enumerate(rows):
        y = top + r * row_h + 9
        text(draw, (cols[0] + 10, y), row[0], body_bold if r == 0 else body)
        text(draw, (cols[1] + 12, y), row[1], body_bold if r == 0 else qty)
        text(draw, (cols[2] + 12, y), row[2], body_bold if r == 0 else mono)
        text(draw, (cols[3] + 12, y), row[3], body_bold if r == 0 else mono)

    text(draw, (48, 560), "Subtotal 115.50", font(SANS, 13))
    text(draw, (48, 586), "Tax 9.24", font(SANS, 13))
    text(draw, (48, 614), "Total 124.74", font(SANS_BOLD, 15))
    text(draw, (48, 670), "Thank you for your order.", font(SERIF, 14))
    return jpeg(image)


def page_notes() -> tuple[bytes, int, int]:
    image, draw = new_page()
    text(draw, (48, 46), "Notes", font(SERIF_BOLD, 22))
    hline(draw, 48, 564, 82)
    notes = font(SANS, 14)
    text(draw, (48, 110), "Ship the oak panel flat.", notes)
    text(draw, (48, 140), "Call the workshop before Thursday.", notes)
    text(draw, (48, 170), "Payment is due in 14 days.", notes)
    text(draw, (48, 230), "Workshop copy. Not a tax invoice.", font(SANS, 11))
    return jpeg(image)


def pdf_from_jpegs(images: list[tuple[bytes, int, int]]) -> bytes:
    objects: list[bytes] = []

    def add(data: bytes) -> int:
        objects.append(data)
        return len(objects)

    n = len(images)
    # Ids: 1 catalog, 2 pages, then per page: page, content, image.
    page_ids = []
    content_ids = []
    image_ids = []
    next_id = 3
    for _ in images:
        page_ids.append(next_id)
        content_ids.append(next_id + 1)
        image_ids.append(next_id + 2)
        next_id += 3

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    catalog = f"<< /Type /Catalog /Pages 2 0 R >>".encode()
    pages = f"<< /Type /Pages /Count {n} /Kids [{kids}] >>".encode()
    assert add(catalog) == 1
    assert add(pages) == 2

    content = b"q\n612 0 0 792 0 0 cm\n/Im0 Do\nQ\n"
    for index, ((blob, width, height), pid, cid, iid) in enumerate(
        zip(images, page_ids, content_ids, image_ids, strict=True)
    ):
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /XObject << /Im0 {iid} 0 R >> >> "
            f"/Contents {cid} 0 R >>"
        ).encode()
        contents = f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"endstream"
        image = (
            f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
            f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
            f"/Length {len(blob)} >>\nstream\n".encode()
            + blob
            + b"\nendstream"
        )
        assert add(page) == pid
        assert add(contents) == cid
        assert add(image) == iid
        del index

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode()
        out += obj
        if not obj.endswith(b"\n"):
            out += b"\n"
        out += b"endobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = pdf_from_jpegs([page_invoice(), page_notes()])
    OUT.write_bytes(payload)
    print(f"wrote {OUT} ({len(payload)} bytes)")


if __name__ == "__main__":
    main()
