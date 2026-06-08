from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from tools.migration.config import ROOKARI_DB_PATH
from tools.migration.models import BotUser, Seller


def _ts_to_dt(raw: str | int | None) -> datetime | None:
    if raw is None or raw == '':
        return None
    return datetime.fromtimestamp(int(raw), tz=UTC)


def parse_rookari_tables(path: Path = ROOKARI_DB_PATH) -> tuple[list[BotUser], list[dict], list[Seller]]:
    with path.open('r', encoding='utf-8') as fh:
        tables = json.load(fh)

    users: list[BotUser] = []
    stats: list[dict] = []
    sellers: list[Seller] = []

    for block in tables:
        if block.get('type') != 'table':
            continue
        name = block.get('name')
        rows = block.get('data') or []
        if name == 'fl_user':
            for row in rows:
                if row.get('status') != '1':
                    continue
                raw_id = str(row.get('userid') or '').strip()
                if not raw_id.isdigit():
                    continue
                users.append(
                    BotUser(
                        telegram_id=int(raw_id),
                        username=row.get('username') or None,
                        first_name=row.get('name') or None,
                        wallet=int(row.get('wallet') or 0),
                        status=row.get('status') or '1',
                        created_at=_ts_to_dt(row.get('date')),
                        refcode=row.get('refcode') or None,
                        sent=row.get('sent') or None,
                    )
                )
        elif name == 'config_stat':
            stats.extend(rows)
        elif name == 'fl_sellers':
            for row in rows:
                raw_id = str(row.get('userid') or '').strip()
                if not raw_id.isdigit():
                    continue
                sellers.append(
                    Seller(
                        telegram_id=int(raw_id),
                        percent=int(row.get('percent') or 0),
                    )
                )
    return users, stats, sellers
