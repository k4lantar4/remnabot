"""Referral level scheme: fixed rewards are Toman, and the notifications speak the recipient's language.

F-007 part a. ``referrer_fixed_kopeks`` / ``referee_fixed_kopeks`` and ``outcome.money_credited`` are
credited 1:1 into the Toman balance (``add_user_balance``), so a 50,000-Toman reward must read
``settings.format_balance(50_000)``, not ``format_price`` (catalog, /100 → «500»). The level
notifications were hard-coded Russian; a Persian recipient gets no Cyrillic and no ₽.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

import pytest

from app.config import Settings, settings
from app.localization.texts import get_texts
from app.services import referral_service
from app.services.referral_reward_service import ReferralRewardLevelService, RewardEvent
from tests.services.test_referral_reward_levels import _level, chain  # noqa: F401 - chain is a fixture


REWARD_TOMAN = 50_000
REWARD_LABEL = settings.format_balance(REWARD_TOMAN)
CYRILLIC = re.compile('[А-Яа-яЁё]')


def _install_all(monkeypatch, configs) -> None:
    async def fake_all(_db):
        return configs

    monkeypatch.setattr(ReferralRewardLevelService, 'get_all', classmethod(lambda cls, db: fake_all(db)))


def test_catalog_formatter_would_show_the_toman_reward_100x_smaller():
    """The premise: the two formatters disagree, so picking the balance one matters."""
    assert settings.format_price(REWARD_TOMAN) != REWARD_LABEL


# ---------------------------------------------------------------- reward descriptions (bot, cabinet, miniapp)


@pytest.mark.asyncio
async def test_level_ladder_shows_the_fixed_referrer_reward_in_toman(chain, monkeypatch):
    from app.services.referral_reward_service import describe_active_levels

    _install_all(monkeypatch, {1: _level(1, referrer_fixed_kopeks=REWARD_TOMAN)})

    lines = await describe_active_levels(None, tariff_names={}, language='fa')

    assert REWARD_LABEL in lines[0]


@pytest.mark.asyncio
async def test_referee_bonus_shows_the_fixed_reward_in_toman(chain, monkeypatch):
    from app.services.referral_reward_service import describe_referee_bonus

    _install_all(monkeypatch, {1: _level(1, referee_fixed_kopeks=REWARD_TOMAN)})

    described = await describe_referee_bonus(None, tariff_names={}, language='fa')

    assert REWARD_LABEL in described


@pytest.mark.asyncio
async def test_reward_choice_sides_show_the_fixed_reward_in_toman(chain, monkeypatch):
    from app.services.referral_reward_service import describe_reward_choice_sides

    monkeypatch.setattr(Settings, 'is_referral_reward_kind_choice_enabled', lambda self: True)
    _install_all(monkeypatch, {1: _level(1, reward_mode='both', referrer_fixed_kopeks=REWARD_TOMAN, referrer_days=7)})

    money, _days = await describe_reward_choice_sides(None, chain[2], language='fa')

    assert REWARD_LABEL in money


def test_referee_parts_show_the_fixed_reward_in_toman():
    from app.services.referral_reward_service import _describe_referee_parts

    parts = _describe_referee_parts(_level(1, referee_fixed_kopeks=REWARD_TOMAN), {}, get_texts('fa'))

    assert REWARD_LABEL in parts


# ---------------------------------------------------------------- level notifications


def _outcome(*, recipient_id: int, is_referrer: bool, level: int = 1, money: int = REWARD_TOMAN, days: int = 0):
    return SimpleNamespace(
        granted_anything=True,
        component=SimpleNamespace(recipient_id=recipient_id, is_referrer=is_referrer, level=level),
        money_credited=money,
        days_credited=days,
        tariff_name='پرو' if days else None,
    )


async def _notify(monkeypatch, outcome, *, event=RewardEvent.FIRST_TOPUP, language='fa') -> str:
    import app.database.crud.user as user_crud

    referee = SimpleNamespace(id=4, telegram_id=1004, full_name='Sara', language=language)
    referrer = SimpleNamespace(id=3, telegram_id=1003, full_name='Ali', language=language)
    sent = {}

    async def fake_get_user(_db, uid):
        return {3: referrer, 4: referee}[uid]

    async def fake_send(bot, telegram_id, text, **kwargs):
        sent['text'] = text
        sent['bonus_kopeks'] = kwargs.get('bonus_kopeks')

    monkeypatch.setattr(user_crud, 'get_user_by_id', fake_get_user)
    monkeypatch.setattr(referral_service, 'send_referral_notification', fake_send)
    await referral_service._notify_level_outcome(object(), None, referee, outcome, event=event)
    assert sent['bonus_kopeks'] == outcome.money_credited  # the email channel formats it with format_balance
    return sent['text']


@pytest.mark.parametrize('is_referrer', [True, False], ids=['referrer', 'referee'])
@pytest.mark.asyncio
async def test_fa_level_notification_shows_toman_and_no_russian(monkeypatch, is_referrer):
    outcome = _outcome(recipient_id=3 if is_referrer else 4, is_referrer=is_referrer, days=7)

    text = await _notify(monkeypatch, outcome)

    assert REWARD_LABEL in text
    assert '7' in text and 'پرو' in text
    assert not CYRILLIC.search(text), text
    assert '₽' not in text


@pytest.mark.parametrize(
    'event', [RewardEvent.REGISTRATION, RewardEvent.FIRST_TOPUP, RewardEvent.REPEAT_TOPUP], ids=str
)
@pytest.mark.parametrize('level', [1, 2])
@pytest.mark.asyncio
async def test_fa_referrer_event_phrase_is_persian(monkeypatch, event, level):
    text = await _notify(monkeypatch, _outcome(recipient_id=3, is_referrer=True, level=level), event=event)

    assert not CYRILLIC.search(text), text
    # level 2+ is paid by a referral of a referral: named as the network, not by name
    assert ('Sara' in text) is (level == 1)


@pytest.mark.asyncio
async def test_ru_level_notification_keeps_todays_text(monkeypatch):
    text = await _notify(monkeypatch, _outcome(recipient_id=3, is_referrer=True), language='ru')

    assert 'Реферальная награда' in text
    assert 'ваш реферал' in text.lower()
    assert settings.format_balance(REWARD_TOMAN) in text
