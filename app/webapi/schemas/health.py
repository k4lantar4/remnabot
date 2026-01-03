from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class HealthFeatureFlags(BaseModel):
    """Availability flags for administrative API features."""

    monitoring: bool
    maintenance: bool
    reporting: bool
    webhooks: bool

    model_config = ConfigDict(extra="forbid")


class HealthCheckResponse(BaseModel):
    """Response for administrative API health check."""

    status: str
    api_version: str
    bot_version: str | None
    features: HealthFeatureFlags

    model_config = ConfigDict(extra="forbid")
