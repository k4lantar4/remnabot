"""traffic_purchases: clamp expires_at to subscription.end_date

Fixes the root cause of the "40→60 GB" partner bug: before this revision,
`add_subscription_traffic` created rows with expires_at = now + 30 days,
ignoring subscription.end_date.  A top-up bought near the period end would
therefore "leak" purchased_gb into the NEXT renewal cycle, and because the
renewal code sums base_limit_gb + purchased_gb to honour the user's separately
bought data, the user would see 60 GB of traffic while only paying for 40.

The migration is intentionally written in SQL (not python crud helpers) so it
can run from the freshly-built production bot image without needing live python
imports; it is also idempotent — re-running it produces zero row changes.

Revision ID: 0104
Revises: 0103
Create Date: 2026-08-08
"""
from __future__ import annotations

import logging
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0104'
down_revision: Union[str, None] = '0103'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

log = logging.getLogger('alembic.runtime.0104')


def upgrade() -> None:
    """One-shot clamp of traffic_purchases.expires_at → subscriptions.end_date.

    Because the data fix is idempotent (rows already ≤ end_date are never
    touched), it is safe to re-run this migration if a deploy rolls forward
    and back.
    """
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # Stage 1 — count & audit: rows currently leaking past period end
    # ------------------------------------------------------------------
    audit_sql = sa.text(
        '''
        SELECT
            COUNT(*)                  AS total_leaking_rows,
            COALESCE(SUM(tp.traffic_gb), 0)
                                      AS total_leaking_gb,
            COALESCE(SUM(EXTRACT(EPOCH FROM (tp.expires_at - s.end_date))/86400.0), 0)
                                      AS total_leaking_days
        FROM traffic_purchases tp
        JOIN subscriptions s
          ON s.id = tp.subscription_id
        WHERE s.end_date IS NOT NULL
          AND tp.expires_at > s.end_date
        '''
    )
    audit = conn.execute(audit_sql).mappings().one()

    print(
        f'[0104] pre-clamp audit — '
        f'leaking_rows={audit.total_leaking_rows} '
        f'leaking_gb={audit.total_leaking_gb} '
        f'leaking_days={float(audit.total_leaking_days or 0.0):.2f}'
    )
    log.info(
        'pre-clamp audit: leaking_rows=%s leaking_gb=%s leaking_days=%.2f',
        audit.total_leaking_rows,
        audit.total_leaking_gb,
        float(audit.total_leaking_days or 0.0),
    )

    # ------------------------------------------------------------------
    # Stage 2 — apply the clamp (single SQL UPDATE, idempotent)
    # ------------------------------------------------------------------
    update_sql = sa.text(
        '''
        UPDATE traffic_purchases tp
           SET expires_at = s.end_date
          FROM subscriptions s
         WHERE s.id = tp.subscription_id
           AND s.end_date IS NOT NULL
           AND tp.expires_at > s.end_date
        '''
    )
    result = conn.execute(update_sql)

    print(f'[0104] clamp UPDATE finished — rows_affected={result.rowcount}')
    log.info('clamp UPDATE finished — rows_affected=%s', result.rowcount)


def downgrade() -> None:
    """Data-only migration — downgrade is intentionally a no-op.

    Restoring the previous leaky expires_at values would reintroduce the
    bug and cannot be done safely without storing a per-row before-image
    (which would require a new column — disproportionate to the risk).
    """
    print('[0104] downgrade is a no-op (data-only migration).')
    log.info('downgrade is a no-op (data-only migration).')
