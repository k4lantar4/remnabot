from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MediaUploadResponse(BaseModel):
    media_type: str = Field(description="Uploaded file type (photo, video, document)")
    file_id: str = Field(description="Telegram file_id of the uploaded file")
    file_unique_id: Optional[str] = Field(
        default=None, description="Unique identifier of the file"
    )
    media_url: Optional[str] = Field(
        default=None, description="Direct file link for preview"
    )
