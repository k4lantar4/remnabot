"""Audit user-facing DB text columns for Cyrillic (Russian) leakage.

Read-only. Exit 1 when total Cyrillic row count exceeds --threshold.

Usage:
  docker compose run --rm bot python tools/audit_db_user_facing_ru.py
  docker compose run --rm bot python tools/audit_db_user_facing_ru.py --threshold 58 --verbose
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select

from app.database.database import AsyncSessionLocal
from app.database.models import BroadcastHistory, PinnedMessage, Transaction, WelcomeText


CYRILLIC_RE = re.compile(r'[А-Яа-яЁё]')

CYRILLIC_TABLES: tuple[tuple[str, Any, str], ...] = (
    ('transactions', Transaction, 'description'),
    ('broadcast_history', BroadcastHistory, 'message_text'),
    ('pinned_messages', PinnedMessage, 'content'),
    ('welcome_texts', WelcomeText, 'text_content'),
)


@dataclass
class TableAuditResult:
    table: str
    column: str
    count: int
    samples: list[str]


async def _count_cyrillic_rows(model: Any, column_name: str) -> int:
    column = getattr(model, column_name)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count())
            .select_from(model)
            .where(column.isnot(None))
            .where(column.op('~')(r'[А-Яа-яЁё]'))
        )
        return int(result.scalar_one())


async def _sample_cyrillic_rows(model: Any, column_name: str, *, limit: int = 3) -> list[str]:
    column = getattr(model, column_name)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(column)
            .where(column.isnot(None))
            .where(column.op('~')(r'[А-Яа-яЁё]'))
            .limit(limit)
        )
        return [str(row[0])[:120] for row in result.all()]


async def audit_cyrillic(*, verbose: bool) -> list[TableAuditResult]:
    results: list[TableAuditResult] = []
    for table, model, column in CYRILLIC_TABLES:
        count = await _count_cyrillic_rows(model, column)
        samples = await _sample_cyrillic_rows(model, column) if verbose and count else []
        results.append(TableAuditResult(table=table, column=column, count=count, samples=samples))
    return results


async def main_async(*, threshold: int, verbose: bool, as_json: bool) -> int:
    results = await audit_cyrillic(verbose=verbose)
    total = sum(item.count for item in results)

    payload = {
        'threshold': threshold,
        'total_cyrillic_rows': total,
        'passed': total <= threshold,
        'tables': [
            {
                'table': item.table,
                'column': item.column,
                'count': item.count,
                **({'samples': item.samples} if item.samples else {}),
            }
            for item in results
        ],
    }

    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for item in results:
            print(f'{item.table}.{item.column}: {item.count}')
            for sample in item.samples:
                print(f'  sample: {sample!r}')
        print(f'total: {total} (threshold {threshold})')

    return 0 if total <= threshold else 1


def main() -> None:
    parser = argparse.ArgumentParser(description='Audit DB columns for Cyrillic user-facing text')
    parser.add_argument('--threshold', type=int, default=58)
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--json', action='store_true', dest='as_json')
    args = parser.parse_args()
    exit_code = asyncio.run(
        main_async(threshold=args.threshold, verbose=args.verbose, as_json=args.as_json)
    )
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
