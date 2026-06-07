from datetime import UTC, datetime

from tools.migration.join_filter import build_migration_cohorts
from tools.migration.models import BotUser, XuiClient
from tools.migration.proration import BACKUP_ANCHOR


def test_multi_tariff_keeps_both_vip_tiers():
    migration_run = datetime(2026, 6, 1, tzinfo=UTC)
    clients = [
        XuiClient(17, 'u1', 'uuid-a', True, 1893456000000, 0, 0, 100, vip=1),
        XuiClient(14, 'u1', 'uuid-b', True, 1893456000000, 0, 0, 100, vip=20),
    ]
    users = [BotUser(100, 'u', 'Ali', 0, '1', migration_run, None)]
    stats = [
        {
            'userid': '100',
            'remark': 'u1',
            'total': str(107374182400),
            'up': '0',
            'down': '0',
            'expiryTime': '1893456000',
        }
    ]

    subscribers, campaign, rejects = build_migration_cohorts(
        clients,
        users,
        stats,
        [],
        migration_run=migration_run,
        anchor=BACKUP_ANCHOR,
    )
    assert len(subscribers) == 2
    tariff_ids = {s.tariff_id for s in subscribers}
    assert tariff_ids == {2, 3}
    assert len(campaign) == 0
    assert len(rejects) == 0


def test_campaign_user_without_active_sub():
    migration_run = datetime(2026, 6, 1, tzinfo=UTC)
    users = [
        BotUser(100, 'a', 'Ali', 100, '1', migration_run, None),
        BotUser(200, 'b', 'Bob', 50, '1', migration_run, None, sent='1'),
    ]
    subscribers, campaign, _ = build_migration_cohorts([], users, [], [], migration_run=migration_run)
    assert len(subscribers) == 0
    assert len(campaign) == 2
    assert campaign[1].sent == '1'
