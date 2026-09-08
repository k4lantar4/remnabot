"""Cabinet user-facing balance JSON must use Toman 1:1 helpers, not /100.

M6-T5: cabinet FX on already-Toman amounts showed 20,185,533 for DB 126800.
skipFx in the frontend only works if GET /balance sends 1:1 balance_rubles.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_cabinet_balance_route_uses_toman_display_helpers() -> None:
    text = (ROOT / 'app/cabinet/routes/balance.py').read_text(encoding='utf-8')
    assert 'display_balance_from_storage' in text
    assert 'display_transaction_amount_from_storage' in text
    assert 'balance_rubles=fresh_user.balance_kopeks / 100' not in text
    assert 'amount_rubles=amount_kopeks / 100' not in text
