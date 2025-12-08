from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SettingCategorySummary(BaseModel):
    """Short description of a settings category."""

    key: str
    label: str
    items: int

    model_config = ConfigDict(extra="forbid")


class SettingCategoryRef(BaseModel):
    """Reference to the category a setting belongs to."""

    key: str
    label: str

    model_config = ConfigDict(extra="forbid")


class SettingChoice(BaseModel):
    """Selectable value option for a setting."""

    value: Any
    label: str
    description: Optional[str] = None

    model_config = ConfigDict(extra="forbid")


class SettingDefinition(BaseModel):
    """Full description of a setting and its current state."""

    key: str
    name: str
    category: SettingCategoryRef
    type: str
    is_optional: bool
    current: Any | None = Field(default=None)
    original: Any | None = Field(default=None)
    has_override: bool
    read_only: bool = Field(default=False)
    choices: list[SettingChoice] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


class SettingUpdateRequest(BaseModel):
    """Request to update a setting value."""

    value: Any

    model_config = ConfigDict(extra="forbid")
