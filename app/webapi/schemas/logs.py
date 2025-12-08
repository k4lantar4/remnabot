"""Pydantic schemas for administrative API logs."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MonitoringLogEntry(BaseModel):
    """Monitoring log entry."""

    id: int
    event_type: str = Field(..., description="Monitoring event type")
    message: str = Field(..., description="Short event description")
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional event data",
    )
    is_success: bool = Field(..., description="Flag indicating operation success")
    created_at: datetime = Field(..., description="Record creation datetime")


class MonitoringLogListResponse(BaseModel):
    """Response with monitoring log list."""

    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    items: List[MonitoringLogEntry]


class MonitoringLogTypeListResponse(BaseModel):
    """Response with available monitoring event types."""

    items: List[str] = Field(default_factory=list)


class SupportAuditLogEntry(BaseModel):
    """Support moderators audit entry."""

    id: int
    actor_user_id: Optional[int]
    actor_telegram_id: int
    is_moderator: bool
    action: str
    ticket_id: Optional[int]
    target_user_id: Optional[int]
    details: Optional[Dict[str, Any]] = None
    created_at: datetime


class SupportAuditLogListResponse(BaseModel):
    """Response with support audit list."""

    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1)
    offset: int = Field(..., ge=0)
    items: List[SupportAuditLogEntry]


class SupportAuditActionsResponse(BaseModel):
    """Response with available support audit actions."""

    items: List[str] = Field(default_factory=list)


class SystemLogPreviewResponse(BaseModel):
    """Response with preview of the bot system log file."""

    path: str = Field(..., description="Absolute path to the log file")
    exists: bool = Field(..., description="Flag indicating log file exists")
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last modified datetime of the log file",
    )
    size_bytes: int = Field(..., ge=0, description="Log file size in bytes")
    size_chars: int = Field(..., ge=0, description="Number of characters in the log file")
    preview: str = Field(
        default="",
        description="Log file content fragment returned for preview",
    )
    preview_chars: int = Field(..., ge=0, description="Preview size in characters")
    preview_truncated: bool = Field(
        ..., description="Flag indicating preview is truncated relative to full file"
    )
    download_url: Optional[str] = Field(
        default=None,
        description="Relative path to the endpoint for downloading the log file",
    )


class SystemLogFullResponse(BaseModel):
    """Full content of the system log file."""

    path: str
    exists: bool
    updated_at: Optional[datetime] = None
    size_bytes: int
    size_chars: int
    content: str
