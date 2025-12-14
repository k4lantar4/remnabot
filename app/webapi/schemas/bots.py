from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class BotResponse(BaseModel):
    id: int
    name: str
    is_master: bool
    is_active: bool
    
    # Card-to-card settings
    card_to_card_enabled: bool
    card_receipt_topic_id: Optional[int] = None
    
    # Zarinpal settings
    zarinpal_enabled: bool
    zarinpal_merchant_id: Optional[str] = None
    zarinpal_sandbox: bool
    
    # General settings
    default_language: str
    support_username: Optional[str] = None
    admin_chat_id: Optional[int] = None
    admin_topic_id: Optional[int] = None
    notification_group_id: Optional[int] = None
    notification_topic_id: Optional[int] = None
    
    # Wallet & billing
    wallet_balance_kopeks: int
    wallet_balance_rubles: float
    traffic_consumed_bytes: int
    traffic_sold_bytes: int
    
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    
    class Config:
        from_attributes = True


class BotListResponse(BaseModel):
    items: List[BotResponse]
    total: int
    limit: int
    offset: int


class BotCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    telegram_bot_token: str = Field(..., min_length=1)
    is_master: bool = False
    is_active: bool = True
    
    # Card-to-card settings
    card_to_card_enabled: bool = False
    card_receipt_topic_id: Optional[int] = None
    
    # Zarinpal settings
    zarinpal_enabled: bool = False
    zarinpal_merchant_id: Optional[str] = None
    zarinpal_sandbox: bool = False
    
    # General settings
    default_language: str = "fa"
    support_username: Optional[str] = None
    admin_chat_id: Optional[int] = None
    admin_topic_id: Optional[int] = None
    notification_group_id: Optional[int] = None
    notification_topic_id: Optional[int] = None


class BotUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    telegram_bot_token: Optional[str] = None
    is_active: Optional[bool] = None
    
    # Card-to-card settings
    card_to_card_enabled: Optional[bool] = None
    card_receipt_topic_id: Optional[int] = None
    
    # Zarinpal settings
    zarinpal_enabled: Optional[bool] = None
    zarinpal_merchant_id: Optional[str] = None
    zarinpal_sandbox: Optional[bool] = None
    
    # General settings
    default_language: Optional[str] = None
    support_username: Optional[str] = None
    admin_chat_id: Optional[int] = None
    admin_topic_id: Optional[int] = None
    notification_group_id: Optional[int] = None
    notification_topic_id: Optional[int] = None


class BotCreateResponse(BaseModel):
    bot: BotResponse
    api_token: str = Field(..., description="Plain API token (shown only once)")


class BotActivateResponse(BaseModel):
    success: bool
    message: str



