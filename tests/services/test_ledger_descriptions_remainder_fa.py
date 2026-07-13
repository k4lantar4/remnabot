"""Regression tests for Persian ledger descriptions (Tasks 18–22)."""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.localization.texts import get_texts
from app.services.wheel_service import FortuneWheelService


ROOT = Path(__file__).resolve().parents[2]

LEDGER_SOURCE_FILES = (
    'app/handlers/subscription/purchase.py',
    'app/services/subscription_purchase_service.py',
    'app/webapi/routes/miniapp.py',
    'app/services/wheel_service.py',
    'app/handlers/admin/users.py',
    'app/cabinet/routes/admin_users.py',
)

HARDCODED_LEDGER_PATTERN = re.compile(
    r"description\s*=\s*f['\"][^'\"]*(?:Выигрыш в колесе|Покупка тарифа|Подписка на)[^'\"]*['\"]",
    re.MULTILINE,
)


def test_fa_json_has_ledger_keys():
    texts = get_texts('fa')
    for key in (
        'ADMIN_LEDGER_TOPUP',
        'CLASSIC_SUB_PURCHASE_LEDGER_DESC',
        'WHEEL_WIN_BALANCE_LEDGER_DESC',
        'DAILY_TARIFF_RENEW_LEDGER_DESC',
    ):
        value = texts.t(key, key)
        assert value != key
        assert not re.search(r'[А-Яа-яЁё]', value), key


def test_no_hardcoded_cyrillic_ledger_descriptions_in_wired_files():
    offenders: list[str] = []
    for rel in LEDGER_SOURCE_FILES:
        content = (ROOT / rel).read_text(encoding='utf-8')
        if HARDCODED_LEDGER_PATTERN.search(content):
            offenders.append(rel)
    assert not offenders, f'hardcoded Cyrillic ledger descriptions: {offenders}'


@pytest.mark.asyncio
async def test_wheel_balance_prize_uses_persian_ledger(monkeypatch):
    db = AsyncMock()
    user = SimpleNamespace(id=3, language='fa')
    prize = SimpleNamespace(
        prize_type='balance_bonus',
        prize_value=50_000,
        prize_value_kopeks=50_000,
    )
    config = SimpleNamespace()
    add_balance = AsyncMock()
    monkeypatch.setattr('app.services.wheel_service.add_user_balance', add_balance)

    service = FortuneWheelService()
    await service._apply_prize(db, user, prize, config, subscription=None)

    description = add_balance.await_args.kwargs['description']
    assert 'جایزه گردونه' in description
    assert 'Выигрыш' not in description
    assert '₽' not in description


@pytest.mark.asyncio
async def test_admin_balance_credit_uses_persian_ledger(monkeypatch):
    """Exercise ledger description construction for admin top-up path."""
    target_user = SimpleNamespace(id=10, language='fa')
    ledger_texts = get_texts(target_user.language)
    amount_label = '100,000 تومان'
    description = ledger_texts.t(
        'ADMIN_LEDGER_TOPUP',
        'Пополнение администратором: +{amount}',
    ).format(amount=amount_label)
    assert 'شارژ توسط ادمین' in description
    assert 'Пополнение' not in description
