"""QR generation helpers for subscription configuration links."""

from __future__ import annotations

from io import BytesIO

import qrcode
from aiogram.types import BufferedInputFile


def generate_subscription_qr_png(url: str) -> bytes:
    """Render a stable PNG QR code payload for a subscription URL."""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(url)
    qr.make(fit=True)

    image = qr.make_image(fill_color='black', back_color='white')
    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()


def subscription_qr_photo_file(url: str) -> BufferedInputFile:
    """Wrap subscription QR PNG bytes in an aiogram file object."""
    return BufferedInputFile(generate_subscription_qr_png(url), filename='subscription-config.png')
