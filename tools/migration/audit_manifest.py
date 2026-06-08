from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from tools.migration.config import backup_anchor_iso, migration_backup_dir
from tools.migration.models import CampaignUser, MigrationReject, MigrationSubscription


def build_manifest(
    subscribers: list[MigrationSubscription],
    campaign_users: list[CampaignUser],
    rejects: list[MigrationReject],
    *,
    backup_dir: Path | None = None,
    migration_run: datetime | None = None,
) -> dict:
    if migration_run is None:
        migration_run = datetime.now(UTC)
    if backup_dir is None:
        backup_dir = migration_backup_dir()

    return {
        'backup_dir': str(backup_dir) if backup_dir else None,
        'anchor': backup_anchor_iso(),
        'migration_run': migration_run.isoformat().replace('+00:00', 'Z'),
        'subscribers': [
            {
                'telegram_id': s.telegram_id,
                'tariff_id': s.tariff_id,
                'source_email': s.source_email,
                'old_uuids': s.old_uuids,
                'old_emails': s.old_emails,
                'remaining_bytes': s.remaining_bytes,
                'traffic_limit_gb': s.traffic_limit_gb,
                'squad_keys': s.squad_keys,
                'end_date': s.end_date.isoformat(),
            }
            for s in subscribers
        ],
        'subscriber_user_count': len({s.telegram_id for s in subscribers}),
        'subscriber_subscription_count': len(subscribers),
        'campaign_users_count': len(campaign_users),
        'campaign_users_sent_flags': sum(1 for c in campaign_users if c.sent not in (None, '', '0')),
        'rejects': [asdict(r) for r in rejects],
        'reject_count': len(rejects),
    }


def write_manifest(
    path: Path,
    subscribers: list[MigrationSubscription],
    campaign_users: list[CampaignUser],
    rejects: list[MigrationReject],
    *,
    backup_dir: Path | None = None,
    migration_run: datetime | None = None,
) -> dict:
    manifest = build_manifest(
        subscribers,
        campaign_users,
        rejects,
        backup_dir=backup_dir,
        migration_run=migration_run,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding='utf-8')
    return manifest
