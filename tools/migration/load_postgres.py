from __future__ import annotations

import structlog
from sqlalchemy import func, select

from app.database.crud.subscription import create_subscription_no_commit
from app.database.crud.user import create_user_no_commit, get_user_by_telegram_id
from app.database.models import PartnerStatus, SubscriptionStatus, Tariff, User

from tools.migration.config import BATCH_SIZE
from tools.migration.models import CampaignUser, MigrationSubscription, Seller


def _resolve_connected_squads(sub: MigrationSubscription, squad_uuids: dict[str, str]) -> list[str]:
    by_tariff = {2: squad_uuids.get('premium'), 3: squad_uuids.get('basic')}
    if sub.tariff_id in by_tariff and by_tariff[sub.tariff_id]:
        return [by_tariff[sub.tariff_id]]
    connected = list(dict.fromkeys(squad_uuids[k] for k in sub.squad_keys if k in squad_uuids))
    return connected


logger = structlog.get_logger(__name__)


def _count_partners(telegram_ids: set[int], seller_by_tg: dict[int, Seller]) -> int:
    return sum(1 for tg in telegram_ids if tg in seller_by_tg)


async def ensure_migration_tariffs(db, squad_uuids: dict[str, str]) -> None:
    """Ensure tariff rows 2 (premium) and 3 (basic) exist for FK + squad routing."""
    existing = set(
        (await db.execute(select(Tariff.id).where(Tariff.id.in_([2, 3])))).scalars().all()
    )
    if existing >= {2, 3}:
        return

    template = (await db.execute(select(Tariff).order_by(Tariff.id).limit(1))).scalar_one_or_none()
    if template is None:
        raise RuntimeError('No tariff template in DB — create at least one tariff before migration load')

    specs = [
        (2, 'Premium', squad_uuids.get('premium')),
        (3, 'Basic', squad_uuids.get('basic')),
    ]
    for tariff_id, name, squad_uuid in specs:
        if tariff_id in existing:
            continue
        squads = [squad_uuid] if squad_uuid else list(template.allowed_squads or [])
        db.add(
            Tariff(
                id=tariff_id,
                name=name,
                description=f'Migration placeholder {name}',
                display_order=tariff_id,
                is_active=True,
                traffic_limit_gb=template.traffic_limit_gb,
                device_limit=template.device_limit,
                device_price_kopeks=template.device_price_kopeks,
                max_device_limit=template.max_device_limit,
                allowed_squads=squads,
                server_traffic_limits=dict(template.server_traffic_limits or {}),
                period_prices=dict(template.period_prices or {}),
                tier_level=template.tier_level,
                is_trial_available=False,
                allow_traffic_topup=template.allow_traffic_topup,
                traffic_topup_enabled=template.traffic_topup_enabled,
                traffic_topup_packages=dict(template.traffic_topup_packages or {}),
                max_topup_traffic_gb=template.max_topup_traffic_gb,
                is_daily=template.is_daily,
                daily_price_kopeks=template.daily_price_kopeks,
                custom_days_enabled=template.custom_days_enabled,
                price_per_day_kopeks=template.price_per_day_kopeks,
                min_days=template.min_days,
                max_days=template.max_days,
                custom_traffic_enabled=template.custom_traffic_enabled,
                traffic_price_per_gb_kopeks=template.traffic_price_per_gb_kopeks,
                min_traffic_gb=template.min_traffic_gb,
                max_traffic_gb=template.max_traffic_gb,
                show_in_gift=False,
                traffic_reset_mode=template.traffic_reset_mode,
                external_squad_uuid=template.external_squad_uuid,
            )
        )
    await db.flush()
    logger.info('Ensured migration tariffs', created=sorted({2, 3} - existing))


async def load_migration_data(
    db,
    subscribers: list[MigrationSubscription],
    campaign_users: list[CampaignUser],
    sellers: list[Seller],
    squad_uuids: dict[str, str],
    *,
    dry_run: bool = True,
) -> dict[str, int]:
    stats = {
        'created_users': 0,
        'updated_users': 0,
        'created_subs': 0,
        'skipped_subs': 0,
        'skipped_users': 0,
        'campaign_users': 0,
        'partners': 0,
    }
    seller_by_tg = {s.telegram_id: s for s in sellers}
    loaded_email_keys: set[tuple[int, str]] = set()

    if dry_run:
        sub_tg = {s.telegram_id for s in subscribers}
        camp_tg = {c.telegram_id for c in campaign_users}
        stats['created_users'] = len(sub_tg | camp_tg)
        stats['created_subs'] = len(subscribers)
        stats['campaign_users'] = len(campaign_users)
        stats['partners'] = _count_partners(sub_tg | camp_tg, seller_by_tg)
        return stats

    await ensure_migration_tariffs(db, squad_uuids)

    async def apply_partner(user, telegram_id: int) -> None:
        seller = seller_by_tg.get(telegram_id)
        if seller is None:
            return
        user.partner_status = PartnerStatus.APPROVED.value
        user.referral_commission_percent = seller.percent

    for i, sub in enumerate(subscribers):
        connected = _resolve_connected_squads(sub, squad_uuids)
        if not connected:
            logger.warning('no squad uuids for subscriber', telegram_id=sub.telegram_id, keys=sub.squad_keys)
            stats['skipped_subs'] += 1
            continue

        user = await get_user_by_telegram_id(db, sub.telegram_id)
        if user is None:
            user = await create_user_no_commit(
                db,
                telegram_id=sub.telegram_id,
                username=sub.username,
                first_name=sub.first_name,
                language='fa',
            )
            user.balance_kopeks = sub.wallet
            if sub.old_uuids:
                user.vless_uuid = sub.old_uuids[0]
            await apply_partner(user, sub.telegram_id)
            stats['created_users'] += 1
        else:
            user.balance_kopeks = sub.wallet
            if sub.old_uuids and not user.vless_uuid:
                user.vless_uuid = sub.old_uuids[0]
            await apply_partner(user, sub.telegram_id)
            stats['updated_users'] += 1

        email_key = (sub.telegram_id, sub.source_email)
        if email_key in loaded_email_keys:
            stats['skipped_subs'] += 1
            continue
        loaded_email_keys.add(email_key)

        subscription = await create_subscription_no_commit(
            db,
            user_id=user.id,
            status=SubscriptionStatus.ACTIVE.value,
            is_trial=False,
            end_date=sub.end_date,
            traffic_limit_gb=sub.traffic_limit_gb,
            traffic_used_gb=0.0,
            device_limit=1,
            connected_squads=connected,
        )
        subscription.tariff_id = sub.tariff_id
        stats['created_subs'] += 1

        if (i + 1) % BATCH_SIZE == 0:
            await db.commit()
            logger.info('migration subscriber batch committed', count=i + 1)

    for j, camp in enumerate(campaign_users):
        existing = await get_user_by_telegram_id(db, camp.telegram_id)
        if existing:
            stats['skipped_users'] += 1
            await apply_partner(existing, camp.telegram_id)
            continue

        user = await create_user_no_commit(
            db,
            telegram_id=camp.telegram_id,
            username=camp.username,
            first_name=camp.first_name,
            language='fa',
        )
        user.balance_kopeks = camp.wallet
        await apply_partner(user, camp.telegram_id)
        stats['campaign_users'] += 1

        if (j + 1) % BATCH_SIZE == 0:
            await db.commit()
            logger.info('migration campaign batch committed', count=j + 1)

    stats['partners'] = (
        await db.execute(select(func.count()).select_from(User).where(User.partner_status == PartnerStatus.APPROVED.value))
    ).scalar_one()
    await db.commit()
    return stats
