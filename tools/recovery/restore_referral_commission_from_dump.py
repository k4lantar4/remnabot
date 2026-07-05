#!/usr/bin/env python3
"""Extract users.referral_commission_percent from a pg_dump for column restore.

Usage:
  python tools/recovery/restore_referral_commission_from_dump.py \\
    /opt/migration-backups/pre-c2c-recovery-20260622_125824.sql \\
    /tmp/users_referral_commission_backup.csv

Then load into Postgres and UPDATE (see ops runbook / plan restore_commission).
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path


def extract_users_referral_commission(dump_path: Path, out_path: Path) -> int:
    in_copy = False
    col_idx: int | None = None
    rows = 0

    with dump_path.open('r', encoding='utf-8', errors='replace') as src, out_path.open(
        'w', newline='', encoding='utf-8'
    ) as out:
        writer = csv.writer(out)
        for line in src:
            if line.startswith('COPY public.users '):
                match = re.search(r'\(([^)]+)\)', line)
                if not match:
                    raise ValueError('Could not parse COPY column list')
                cols = [c.strip() for c in match.group(1).split(',')]
                col_idx = cols.index('referral_commission_percent')
                in_copy = True
                continue
            if in_copy:
                if line.strip() == '\\.':
                    break
                parts = line.rstrip('\n').split('\t')
                val = parts[col_idx]
                uid = parts[0]
                writer.writerow([uid, '' if val == '\\N' else val])
                rows += 1

    if col_idx is None:
        raise ValueError(f'COPY public.users block not found in {dump_path}')

    return rows


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    dump_path = Path(argv[1])
    out_path = Path(argv[2])
    if not dump_path.is_file():
        print(f'dump not found: {dump_path}', file=sys.stderr)
        return 1
    count = extract_users_referral_commission(dump_path, out_path)
    print(f'Wrote {count} rows to {out_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
