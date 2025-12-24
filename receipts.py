from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


@dataclass(frozen=True)
class ReceiptData:
    resident_name: str
    entry_date: date
    amount_paid: Decimal
    balance_after: Decimal
    entry_id: int


def _money(x: Decimal) -> str:
    return f"${x.quantize(Decimal('0.01')):,.2f}"


def generate_payment_receipt_pdf_bytes(data: ReceiptData, banner_image_path: Path) -> bytes:
    """
    Generate a simple receipt PDF similar to your template.
    Returns PDF bytes.
    """
    from io import BytesIO
    buf = BytesIO()

    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    # Layout constants
    left = 72
    right = width - 72
    y = height - 72

    # Banner image (top)
    if banner_image_path.exists():
        # Keep it neat: full-width-ish banner, fixed height
        banner_h = 80
        c.drawImage(
            str(banner_image_path),
            left,
            y - banner_h,
            width=(right - left),
            height=banner_h,
            preserveAspectRatio=True,
            mask='auto',
        )
        y -= (banner_h + 18)
    else:
        # Fallback (no banner found)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(left, y, "RECEIPT")
        y -= 24

    # Fields — matching your simple template
    c.setFont("Helvetica", 12)

    # Name
    c.drawString(left, y, "Name:")
    c.line(left + 55, y - 2, right, y - 2)
    c.drawString(left + 60, y, data.resident_name)
    y -= 28

    # Amount Paid
    c.drawString(left, y, "Amount Paid:")
    c.line(left + 95, y - 2, right, y - 2)
    c.drawString(left + 100, y, _money(data.amount_paid))
    y -= 28

    # Date
    c.drawString(left, y, "Date:")
    c.line(left + 40, y - 2, right, y - 2)
    c.drawString(left + 45, y, data.entry_date.strftime("%Y-%m-%d"))
    y -= 28

    # Balance after payment
    c.drawString(left, y, "Balance After Payment:")
    c.line(left + 160, y - 2, right, y - 2)
    c.drawString(left + 165, y, _money(data.balance_after))
    y -= 40

    # Small footer (optional, neat + traceable)
    c.setFont("Helvetica", 9)
    c.drawString(left, 72, f"Receipt ID: {data.entry_id}")

    c.showPage()
    c.save()

    buf.seek(0)
    return buf.read()