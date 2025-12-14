from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PaymentCardResponse(BaseModel):
    id: int
    bot_id: int
    card_number: str
    card_holder_name: str
    rotation_strategy: str
    rotation_interval_minutes: Optional[int] = None
    weight: int
    success_count: int
    failure_count: int
    is_active: bool
    last_used_at: Optional[datetime] = None
    current_usage_count: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[int] = None
    
    class Config:
        from_attributes = True


class PaymentCardListResponse(BaseModel):
    items: List[PaymentCardResponse]
    total: int
    limit: int
    offset: int


class PaymentCardCreateRequest(BaseModel):
    bot_id: int
    card_number: str = Field(..., min_length=1, max_length=50)
    card_holder_name: str = Field(..., min_length=1, max_length=255)
    rotation_strategy: str = Field(default="round_robin", pattern="^(round_robin|random|time_based|weighted)$")
    rotation_interval_minutes: Optional[int] = Field(None, ge=1)
    weight: int = Field(default=1, ge=1)
    is_active: bool = True


class PaymentCardUpdateRequest(BaseModel):
    card_number: Optional[str] = Field(None, min_length=1, max_length=50)
    card_holder_name: Optional[str] = Field(None, min_length=1, max_length=255)
    rotation_strategy: Optional[str] = Field(None, pattern="^(round_robin|random|time_based|weighted)$")
    rotation_interval_minutes: Optional[int] = Field(None, ge=1)
    weight: Optional[int] = Field(None, ge=1)
    is_active: Optional[bool] = None


class PaymentCardStatisticsResponse(BaseModel):
    card_id: int
    success_count: int
    failure_count: int
    total_uses: int
    success_rate: float
    current_usage_count: int
    last_used_at: Optional[datetime] = None
    is_active: bool



