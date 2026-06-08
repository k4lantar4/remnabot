from __future__ import annotations

import structlog
from sqlalchemy import func, select, text

from app.database.models import Subscription, User

logger = structlog.get_logger(__name__)


async def count_bot_users_and_subs(db) -> dict[str, int]:
    user_count = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    sub_count = (await db.execute(select(func.count()).select_from(Subscription))).scalar_one()
    return {'users': user_count, 'subscriptions': sub_count}


async def purge_bot_users(db, *, dry_run: bool = True) -> dict[str, int | bool]:
    counts = await count_bot_users_and_subs(db)
    if dry_run:
        return {**counts, 'dry_run': True, 'deleted_users': counts['users']}

    await db.execute(text('TRUNCATE TABLE users RESTART IDENTITY CASCADE'))
    await db.commit()
    after = await count_bot_users_and_subs(db)
    logger.info('bot user purge complete', before=counts, after=after)
    return {
        **after,
        'dry_run': False,
        'deleted_users': counts['users'],
        'deleted_subscriptions': counts['subscriptions'],
    }


async def purge_panel_users(*, dry_run: bool = True) -> dict[str, int | bool]:
    from app.services.remnawave_service import RemnaWaveService

    service = RemnaWaveService()

    async with service.get_api_client() as api:
        first = await api.get_all_users(start=0, size=1)
        total = int(first.get('total') or 0)
        if dry_run:
            return {'panel_users_total': total, 'deleted': 0, 'dry_run': True}

        deleted = 0
        while True:
            batch = await api.get_all_users(start=0, size=100)
            users = batch.get('users') or []
            if not users:
                break
            for user in users:
                try:
                    if await api.delete_user(user.uuid):
                        deleted += 1
                    else:
                        logger.warning('panel delete returned false', uuid=user.uuid)
                except Exception as exc:
                    logger.warning('panel delete failed', uuid=user.uuid, error=str(exc))

    return {
        'panel_users_total': total,
        'deleted': deleted,
        'dry_run': False,
    }
