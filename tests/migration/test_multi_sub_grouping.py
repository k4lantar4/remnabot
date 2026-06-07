from datetime import UTC, datetime

from tools.migration.join_filter import build_migration_cohorts
from tools.migration.models import BotUser, XuiClient
from tools.migration.proration import BACKUP_ANCHOR


def test_same_tariff_separate_subs_per_email():
    migration_run = datetime(2026, 6, 1, tzinfo=UTC)
    gib = 1024**3
    clients = [
        XuiClient(11, 'u1', 'uuid-a', True, 1893456000000, 0, 0, 50, vip=20),
        XuiClient(14, 'u2', 'uuid-b', True, 1893456000000, 0, 0, 50, vip=20),
    ]
    users = [BotUser(100, 'u', 'Ali', 0, '1', migration_run, None)]
    stats = [
        {
            'userid': '100',
            'remark': 'u1',
            'total': str(50 * gib),
            'up': '0',
            'down': '0',
            'expiryTime': '1893456000',
        },
        {
            'userid': '100',
            'remark': 'u2',
            'total': str(50 * gib),
            'up': '0',
            'down': '0',
            'expiryTime': '1893456000',
        },
    ]

    subscribers, _, _ = build_migration_cohorts(
        clients,
        users,
        stats,
        [],
        migration_run=migration_run,
        anchor=BACKUP_ANCHOR,
    )
    assert len(subscribers) == 2
    assert subscribers[0].source_email != subscribers[1].source_email
    assert subscribers[0].remaining_bytes == 50 * gib


def test_rejects_over_quota():
    migration_run = datetime(2026, 6, 1, tzinfo=UTC)
    clients = [XuiClient(14, 'u1', 'uuid-a', True, 1893456000000, 0, 0, 1, vip=20)]
    users = [BotUser(100, 'u', 'Ali', 0, '1', migration_run, None)]
    stats = [
        {
            'userid': '100',
            'remark': 'u1',
            'total': '1000',
            'up': '600',
            'down': '500',
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
    assert len(subscribers) == 0
    assert len(campaign) == 1
    assert len(rejects) == 1
    assert rejects[0].reason == 'over_quota'
