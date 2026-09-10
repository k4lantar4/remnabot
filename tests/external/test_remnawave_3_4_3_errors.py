"""Классификация ошибок панели по OpenAPI Remnawave 3.4.3 (upstream 9d786897, частично).

* «пользователя нет» = 404 с ``A025`` («User not found») или ``A063`` («User with
  specified params not found»). ``A018`` — это «Failed to create user» (500), ``A039`` —
  общий «Update user error» (500). 404 у панели имеет 27 разных причин (сквад, внешний
  сквад, HWID-устройство…), поэтому «любой 404 = юзера нет» плодит дубли: вызывающий
  код пересоздаёт панельного пользователя по этому признаку;
* протухший ``externalSquadUuid`` на создании даёт ``A018``, на обновлении — ``A039``
  либо 404 ``A182`` («External squad not found»); повтор без поля — для всех трёх, и на
  копии запроса, а не на исходном словаре.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.external.remnawave_api import (
    RemnaWaveAPI,
    RemnaWaveAPIError,
    is_stale_external_squad_error,
    is_user_not_found_error,
)


def _api() -> RemnaWaveAPI:
    api = RemnaWaveAPI('http://panel.local', 'key')
    api.enrich_user_with_happ_link = AsyncMock(side_effect=lambda user: user)  # type: ignore[method-assign]
    return api


def _user_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'id': 42,
        'shortUuid': 'short-42',
        'username': 'user42',
        'status': 'ACTIVE',
        'trafficLimitBytes': 0,
        'trafficLimitStrategy': 'NO_RESET',
        'expireAt': '2030-01-01T00:00:00.000Z',
        'createdAt': '2026-01-01T00:00:00.000Z',
        'updatedAt': '2026-01-02T00:00:00.000Z',
        'telegramId': 555,
    }
    payload.update(overrides)
    return payload


# ============== is_user_not_found_error: только настоящее отсутствие пользователя ==============


@pytest.mark.parametrize(
    ('error', 'expected'),
    [
        # 3.4.3: коды отсутствия пользователя.
        (RemnaWaveAPIError('User not found', 404, {'errorCode': 'A025', 'message': 'User not found'}), True),
        (RemnaWaveAPIError('x', 404, {'errorCode': 'A063', 'message': 'User with specified params not found'}), True),
        # Старые панели слали A063 не всегда с 404 — код однозначен, терпим.
        (RemnaWaveAPIError('x', 500, {'errorCode': 'A063'}), True),
        # Панель без кода, но с человекочитаемым сообщением.
        (RemnaWaveAPIError('User not found', 404, {'message': 'User not found'}), True),
        (RemnaWaveAPIError('User not found', 404, {}), True),
        # 404 по ДРУГОЙ причине: внешний сквад, внутренний сквад, HWID-устройство.
        (RemnaWaveAPIError('External squad not found', 404, {'errorCode': 'A182'}), False),
        (RemnaWaveAPIError('Internal squad not found', 404, {'errorCode': 'A118'}), False),
        (RemnaWaveAPIError('HWID device not found', 404, {'errorCode': 'A204'}), False),
        # A018 в 3.4.3 — «Failed to create user» (500), а не «юзера нет».
        (RemnaWaveAPIError('Failed to create user', 500, {'errorCode': 'A018'}), False),
        (RemnaWaveAPIError('x', 400, {'errorCode': 'A018'}), False),
        # 404 от прокси/не той ручки: HTML вместо JSON — это не ответ панели о пользователе.
        (RemnaWaveAPIError('HTTP 404', 404, {'raw_response': '<html>nginx</html>'}), False),
        (RemnaWaveAPIError('not found', 404, {}), False),
        (RemnaWaveAPIError('Validation failed', 400, {}), False),
        (RemnaWaveAPIError('boom', 500, {}), False),
        # Без response_data вовсе (ошибка конфигурации) — не «юзера нет».
        (RemnaWaveAPIError('не настроен'), False),
    ],
)
def test_is_user_not_found_error_matches_panel_error_codes(error: RemnaWaveAPIError, expected: bool) -> None:
    assert is_user_not_found_error(error) is expected


@pytest.mark.parametrize(
    ('error', 'expected'),
    [
        (RemnaWaveAPIError('Failed to create user', 500, {'errorCode': 'A018'}), True),
        (RemnaWaveAPIError('Update user error', 500, {'errorCode': 'A039'}), True),
        (RemnaWaveAPIError('External squad not found', 404, {'errorCode': 'A182'}), True),
        (RemnaWaveAPIError('x', 404, {'message': 'External squad not found'}), True),
        (RemnaWaveAPIError('User not found', 404, {'errorCode': 'A025'}), False),
        (RemnaWaveAPIError('boom', 500, {}), False),
        (RemnaWaveAPIError('не настроен'), False),
    ],
)
def test_is_stale_external_squad_error(error: RemnaWaveAPIError, expected: bool) -> None:
    assert is_stale_external_squad_error(error) is expected


# ============== протухший externalSquadUuid: повтор без поля ==============


async def test_create_user_retries_without_external_squad_on_a018() -> None:
    api = _api()
    api._make_request = AsyncMock(
        side_effect=[
            RemnaWaveAPIError('Failed to create user', 500, {'errorCode': 'A018'}),
            {'response': _user_payload()},
        ]
    )

    user = await api.create_user('user42', datetime(2030, 1, 1, tzinfo=UTC), external_squad_uuid='stale-squad')

    assert user.id == 42
    first, second = api._make_request.await_args_list
    # Первый запрос не изменён задним числом: повтор идёт на копии.
    assert first.args[2]['externalSquadUuid'] == 'stale-squad'
    assert 'externalSquadUuid' not in second.args[2]


async def test_update_user_retries_without_external_squad_on_a182_not_found() -> None:
    api = _api()
    api._make_request = AsyncMock(
        side_effect=[
            RemnaWaveAPIError('External squad not found', 404, {'errorCode': 'A182'}),
            {'response': _user_payload()},
        ]
    )

    user = await api.update_user(42, external_squad_uuid='stale-squad')

    assert user.id == 42
    first, second = api._make_request.await_args_list
    assert first.args[2]['externalSquadUuid'] == 'stale-squad'
    assert 'externalSquadUuid' not in second.args[2]


async def test_update_user_still_retries_on_a039_update_error() -> None:
    api = _api()
    api._make_request = AsyncMock(
        side_effect=[
            RemnaWaveAPIError('Update user error', 500, {'errorCode': 'A039'}),
            {'response': _user_payload()},
        ]
    )

    await api.update_user(42, external_squad_uuid='stale-squad')

    assert 'externalSquadUuid' not in api._make_request.await_args_list[1].args[2]


async def test_update_user_does_not_retry_when_external_squad_was_not_sent() -> None:
    """Без externalSquadUuid в запросе повтор бессмыслен — ошибка уходит вызывающему."""
    api = _api()
    api._make_request = AsyncMock(side_effect=RemnaWaveAPIError('Update user error', 500, {'errorCode': 'A039'}))

    with pytest.raises(RemnaWaveAPIError):
        await api.update_user(42, description='x')

    assert api._make_request.await_count == 1
