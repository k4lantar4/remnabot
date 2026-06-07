from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class XuiClient:
    server_id: int
    email: str
    uuid: str
    enable: bool
    expiry_ms: int
    up: int
    down: int
    total: int
    vip: int


@dataclass(frozen=True)
class BotUser:
    telegram_id: int
    username: str | None
    first_name: str | None
    wallet: int
    status: str
    created_at: datetime | None
    refcode: str | None
    sent: str | None = None


@dataclass(frozen=True)
class Seller:
    telegram_id: int
    percent: int


@dataclass
class MigrationSubscription:
    telegram_id: int
    tariff_id: int
    squad_keys: list[str]
    end_date: datetime
    remaining_bytes: int
    traffic_limit_gb: int
    old_emails: list[str]
    old_uuids: list[str]
    username: str | None = None
    first_name: str | None = None
    wallet: int = 0


@dataclass
class CampaignUser:
    telegram_id: int
    username: str | None
    first_name: str | None
    wallet: int
    sent: str | None = None


@dataclass(frozen=True)
class MigrationReject:
    telegram_id: int
    reason: str
    email: str | None = None


@dataclass
class MigrationCohorts:
    subscribers: list[MigrationSubscription] = field(default_factory=list)
    campaign_users: list[CampaignUser] = field(default_factory=list)
    rejects: list[MigrationReject] = field(default_factory=list)
