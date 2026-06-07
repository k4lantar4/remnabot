from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from tools.migration.config import squad_key_for_server, vip_to_tariff_id
from tools.migration.models import (
    BotUser,
    CampaignUser,
    MigrationReject,
    MigrationSubscription,
    Seller,
    XuiClient,
)
from tools.migration.proration import (
    BACKUP_ANCHOR,
    compute_end_date,
    compute_remaining_traffic,
    is_expired_at_anchor,
    normalize_expiry_unix,
)


def _client_expiry_unix(c: XuiClient) -> int:
    if c.expiry_ms <= 0:
        return 0
    if c.expiry_ms > 10_000_000_000:
        return c.expiry_ms // 1000
    return c.expiry_ms


def _is_active_at_anchor(c: XuiClient, anchor: datetime) -> bool:
    if not c.enable:
        return False
    exp_unix = _client_expiry_unix(c)
    if exp_unix <= 0:
        return True
    return datetime.fromtimestamp(exp_unix, tz=UTC) > anchor


def _best_stat_for_email(stats_by_remark: dict[str, list[dict]], email: str, telegram_id: int) -> dict | None:
    rows = [r for r in stats_by_remark.get(email, []) if str(r.get('userid')) == str(telegram_id)]
    if not rows:
        return None
    return max(rows, key=lambda r: int(r.get('expiryTime') or 0))


def _traffic_from_stat_and_client(stat: dict, client: XuiClient) -> tuple[int, int, int]:
    total_bytes = int(stat.get('total') or 0)
    up = int(stat.get('up') or 0)
    down = int(stat.get('down') or 0)
    if total_bytes <= 0 and client.total > 0:
        total_bytes = client.total * (1024**3)
        up = client.up
        down = client.down
    return total_bytes, up, down


def _expiry_unix_from_stat_and_client(stat: dict, client: XuiClient) -> int:
    stat_exp = normalize_expiry_unix(int(stat.get('expiryTime') or 0))
    if stat_exp > 0:
        return stat_exp
    return normalize_expiry_unix(_client_expiry_unix(client))


def build_migration_cohorts(
    xui_clients: list[XuiClient],
    bot_users: list[BotUser],
    config_stats: list[dict],
    sellers: list[Seller],
    *,
    migration_run: datetime | None = None,
    anchor: datetime | None = None,
) -> tuple[list[MigrationSubscription], list[CampaignUser], list[MigrationReject]]:
    if migration_run is None:
        migration_run = datetime.now(UTC)
    if anchor is None:
        anchor = BACKUP_ANCHOR

    users_by_tg = {u.telegram_id: u for u in bot_users}
    seller_by_tg = {s.telegram_id: s for s in sellers}

    stats_by_remark: dict[str, list[dict]] = defaultdict(list)
    for row in config_stats:
        remark = (row.get('remark') or '').strip()
        if not remark:
            continue
        stats_by_remark[remark].append(row)

    by_email: dict[str, list[XuiClient]] = defaultdict(list)
    for client in xui_clients:
        if _is_active_at_anchor(client, anchor):
            by_email[client.email].append(client)

    groups: dict[tuple[int, int], list[dict]] = defaultdict(list)
    rejects: list[MigrationReject] = []

    for email, clients in by_email.items():
        stat_rows = stats_by_remark.get(email)
        if not stat_rows:
            continue
        tg_ids = {
            int(str(r['userid']).strip())
            for r in stat_rows
            if r.get('userid') and str(r['userid']).strip().isdigit()
        }
        for tg_id in tg_ids:
            user = users_by_tg.get(tg_id)
            if not user:
                continue
            stat = _best_stat_for_email(stats_by_remark, email, tg_id)
            if not stat:
                continue

            for client in clients:
                tariff_id = vip_to_tariff_id(client.vip)
                expiry_unix = _expiry_unix_from_stat_and_client(stat, client)
                if expiry_unix > 0 and is_expired_at_anchor(expiry_unix):
                    rejects.append(
                        MigrationReject(
                            telegram_id=tg_id,
                            email=email,
                            reason='expired_at_anchor',
                        )
                    )
                    continue

                total_bytes, up, down = _traffic_from_stat_and_client(stat, client)
                remaining_bytes, traffic_limit_gb = compute_remaining_traffic(total_bytes, up, down)
                if remaining_bytes <= 0:
                    rejects.append(
                        MigrationReject(
                            telegram_id=tg_id,
                            email=email,
                            reason='over_quota',
                        )
                    )
                    continue

                try:
                    squad_key = squad_key_for_server(client.server_id)
                except ValueError:
                    continue

                groups[(tg_id, tariff_id)].append(
                    {
                        'user': user,
                        'client': client,
                        'stat': stat,
                        'email': email,
                        'expiry_unix': expiry_unix,
                        'remaining_bytes': remaining_bytes,
                        'traffic_limit_gb': traffic_limit_gb,
                        'squad_key': squad_key,
                    }
                )

    subscribers: list[MigrationSubscription] = []
    subscriber_tg_ids: set[int] = set()

    for (tg_id, tariff_id), members in sorted(groups.items()):
        if not members:
            continue
        user = members[0]['user']
        squad_keys = sorted({m['squad_key'] for m in members})
        end_dates: list[datetime] = []
        for m in members:
            exp = m['expiry_unix']
            if exp <= 0:
                end_dates.append(migration_run + timedelta(days=3650))
            else:
                end_dates.append(compute_end_date(exp, migration_run))
        end_date = max(end_dates)
        remaining_bytes = sum(m['remaining_bytes'] for m in members)
        traffic_limit_gb = max(1, (remaining_bytes + 1024**3 - 1) // (1024**3)) if remaining_bytes > 0 else 0
        old_emails = sorted({m['email'] for m in members})
        old_uuids = [m['client'].uuid for m in members]

        subscribers.append(
            MigrationSubscription(
                telegram_id=tg_id,
                username=user.username,
                first_name=user.first_name,
                wallet=user.wallet,
                tariff_id=tariff_id,
                squad_keys=squad_keys,
                end_date=end_date,
                remaining_bytes=remaining_bytes,
                traffic_limit_gb=traffic_limit_gb,
                old_emails=old_emails,
                old_uuids=old_uuids,
            )
        )
        subscriber_tg_ids.add(tg_id)

    campaign_users = [
        CampaignUser(
            telegram_id=u.telegram_id,
            username=u.username,
            first_name=u.first_name,
            wallet=u.wallet,
            sent=u.sent,
        )
        for u in bot_users
        if u.telegram_id not in subscriber_tg_ids
    ]

    return subscribers, campaign_users, rejects


def build_migration_candidates(*args, **kwargs):
    """Backward-compatible alias returning subscribers only."""
    subscribers, _, _ = build_migration_cohorts(*args, **kwargs)
    return subscribers
