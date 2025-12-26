from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RichTextPageResponse(BaseModel):
    """Generic representation for rich text informational pages."""

    requested_language: str = Field(..., description="Language requested by client")
    language: str = Field(..., description="Actual language of the found record")
    is_enabled: Optional[bool] = Field(
        default=None,
        description="Current publication status of the page (if applicable)",
    )
    content: str = Field(..., description="Full page content")
    content_pages: List[str] = Field(
        default_factory=list,
        description="Content split into fixed-length pages",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Record creation date",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last update date",
    )


class RichTextPageUpdateRequest(BaseModel):
    language: str = Field(
        default="ru",
        min_length=2,
        max_length=10,
        description="Language being updated",
    )
    content: str = Field(..., description="New page content")
    is_enabled: Optional[bool] = Field(
        default=None,
        description="If provided, update publication status",
    )


class FaqPageResponse(BaseModel):
    id: int
    language: str
    title: str
    content: str
    content_pages: List[str] = Field(default_factory=list)
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class FaqPageListResponse(BaseModel):
    requested_language: str
    language: str
    is_enabled: bool
    total: int
    items: List[FaqPageResponse]


class FaqPageCreateRequest(BaseModel):
    language: str = Field(
        default="ru",
        min_length=2,
        max_length=10,
        description="Language of the page being created",
    )
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(...)
    display_order: Optional[int] = Field(
        default=None,
        ge=0,
        description="Display order (calculated automatically if not provided)",
    )
    is_active: Optional[bool] = Field(
        default=True,
        description="Initial page activity status",
    )


class FaqPageUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    content: Optional[str] = None
    display_order: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class FaqReorderItem(BaseModel):
    id: int = Field(..., ge=1)
    display_order: int = Field(..., ge=0)


class FaqReorderRequest(BaseModel):
    language: str = Field(
        default="ru",
        min_length=2,
        max_length=10,
        description="Language to which sorting applies",
    )
    items: List[FaqReorderItem]


class FaqStatusResponse(BaseModel):
    requested_language: str
    language: str
    is_enabled: bool


class FaqStatusUpdateRequest(BaseModel):
    language: str = Field(
        default="ru",
        min_length=2,
        max_length=10,
    )
    is_enabled: bool


class ServiceRulesResponse(BaseModel):
    id: int
    title: str
    content: str
    language: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ServiceRulesUpdateRequest(BaseModel):
    language: str = Field(
        default="ru",
        min_length=2,
        max_length=10,
        description="Language for which rules are updated",
    )
    title: Optional[str] = Field(
        default="Service rules",
        min_length=1,
        max_length=255,
    )
    content: str = Field(...)


class ServiceRulesHistoryResponse(BaseModel):
    language: str
    total: int
    items: List[ServiceRulesResponse]

