"""Schemas for card-to-card receipt review in the cabinet admin.

Amounts: ``amount_kopeks`` is on the frozen catalog wire scale (Toman x100, ``app/utils/wire_scale.py``),
the ``*_toman`` fields are the plain Toman values the screen prints.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class C2cReceiptUserInfo(BaseModel):
    id: int
    telegram_id: int | None = None
    username: str | None = None
    full_name: str | None = None
    email: str | None = None


class C2cReceiptReviewerInfo(BaseModel):
    user_id: int | None = None
    telegram_id: int | None = None
    label: str | None = None
    via: str | None = None


class C2cReceiptAdminItem(BaseModel):
    id: int
    status: str
    amount_kopeks: int
    amount_toman: int
    approved_amount_toman: int | None = None
    card_label: str | None = None
    receipt_type: str | None = None
    has_receipt: bool
    created_at: datetime
    processed_at: datetime | None = None
    expires_at: datetime | None = None
    user: C2cReceiptUserInfo
    reviewer: C2cReceiptReviewerInfo
    rejection_reason_key: str | None = None
    rejection_reason: str | None = None


class C2cReceiptAdminDetail(C2cReceiptAdminItem):
    # Same contract as ticket attachments: the cabinet builds ``/cabinet/media/{file_id}?token=`` on
    # its own API base (an absolute URL minted here would lose Caddy's ``/api`` prefix).
    receipt_media_file_id: str | None = None
    receipt_media_token: str | None = None
    receipt_text: str | None = None
    transaction_id: int | None = None
    user_balance_toman: int
    card_number_masked: str | None = None


class C2cReceiptAdminListResponse(BaseModel):
    items: list[C2cReceiptAdminItem]
    total: int
    page: int
    per_page: int
    pages: int


class C2cReceiptAdminStats(BaseModel):
    total: int
    pending: int
    approved: int
    rejected: int
    expired: int
    cancelled: int


class C2cReceiptApproveRequest(BaseModel):
    """``amount_kopeks`` (wire scale) omitted = credit the requested amount."""

    amount_kopeks: int | None = Field(default=None, ge=1, le=2_000_000_000)


class C2cReceiptRejectRequest(BaseModel):
    reason_key: str = Field(max_length=32)
    comment: str | None = Field(default=None, max_length=500)


class C2cRejectReasonItem(BaseModel):
    code: str
    label: str
