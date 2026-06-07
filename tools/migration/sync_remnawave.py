from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from pathlib import Path

import structlog
from sqlalchemy import select

from app.database.models import Subscription, User
from app.services.subscription_service import SubscriptionService

from tools.migration.config import MIGRATION_OUTPUT_DIR, REMNAWAVE_CONCURRENCY

logger = structlog.get_logger(__name__)


def _load_remaining_bytes_map(manifest_path: Path | None = None) -> dict[tuple[int, str], int]:
    path = manifest_path or (MIGRATION_OUTPUT_DIR / 'migration_manifest.json')
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    out: dict[tuple[int, str], int] = {}
    for row in data.get('subscribers', []):
        tg = int(row['telegram_id'])
        source_email = row.get('source_email') or (row.get('old_emails') or [''])[0]
        out[(tg, source_email)] = int(row.get('remaining_bytes') or 0)
    return out


def _load_remaining_bytes_queues(manifest_path: Path | None = None) -> dict[int, list[int]]:
    """Per-telegram FIFO queues — load and sync use the same subscriber order."""
    path = manifest_path or (MIGRATION_OUTPUT_DIR / 'migration_manifest.json')
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding='utf-8'))
    queues: dict[int, list[int]] = defaultdict(list)
    for row in data.get('subscribers', []):
        tg = int(row['telegram_id'])
        queues[tg].append(int(row.get('remaining_bytes') or 0))
    return queues


async def sync_subscription_to_panel(
    db,
    subscription: Subscription,
    user: User,
    *,
    remaining_bytes: int | None = None,
    dry_run: bool = True,
) -> bool:
    if dry_run:
        return True

    service = SubscriptionService()
    original = service._gb_to_bytes

    if remaining_bytes is not None and remaining_bytes > 0:
        service._gb_to_bytes = lambda _gb: remaining_bytes  # noqa: ARG005

    try:
        rw_user = await service.create_remnawave_user(db, subscription, reset_traffic=False)
        if rw_user is None:
            return False
        subscription.remnawave_uuid = rw_user.uuid
        subscription.remnawave_short_uuid = getattr(rw_user, 'short_uuid', None)
        subscription.subscription_url = getattr(rw_user, 'subscription_url', None) or subscription.subscription_url
        await db.commit()
        return True
    except Exception as exc:
        logger.error('panel sync failed', telegram_id=user.telegram_id, error=str(exc))
        await db.rollback()
        return False
    finally:
        service._gb_to_bytes = original


async def sync_all(
    db,
    *,
    dry_run: bool = True,
    manifest_path: Path | None = None,
) -> dict[str, int]:
    remaining_map = _load_remaining_bytes_map(manifest_path)
    remaining_queues = _load_remaining_bytes_queues(manifest_path)
    sem = asyncio.Semaphore(REMNAWAVE_CONCURRENCY)
    stats = {'ok': 0, 'fail': 0, 'dry_run': int(dry_run)}

    result = await db.execute(
        select(Subscription, User)
        .join(User, User.id == Subscription.user_id)
        .where(Subscription.remnawave_uuid.is_(None))
        .where(User.telegram_id.is_not(None))
        .order_by(Subscription.id)
    )
    rows = result.all()

    for sub, user in rows:
        remaining = None
        tg_id = user.telegram_id
        if tg_id is not None and remaining_queues.get(tg_id):
            remaining = remaining_queues[tg_id].pop(0)
        elif tg_id is not None and remaining_map:
            for (map_tg, _email), map_remaining in remaining_map.items():
                if map_tg == tg_id:
                    remaining = map_remaining
                    break
        ok = await sync_subscription_to_panel(
            db,
            sub,
            user,
            remaining_bytes=remaining,
            dry_run=dry_run,
        )
        if ok:
            stats['ok'] += 1
        else:
            stats['fail'] += 1
    return stats
