"""Правила смены тарифа, общие для кабинета, Mini App и бота.

Три флоу смены тарифа написаны независимо и одинаково ошибались:

* остаток считался как ``(end_date - now).days`` — целая часть. У подписки,
  которой осталось меньше суток, остаток выходил нулевым, доплата за
  переключение обнулялась, и в последний день можно было бесплатно прыгать
  между тарифами. Заодно ломался запрет повышения тарифа: при нулевой
  доплате переключение всегда выглядело понижением.
* использованный трафик обнулялся при ЛЮБОМ переключении. В паре с
  бесплатным прыжком это давало неограниченный трафик: A → B → A, и счётчик
  каждый раз с нуля.

Здесь оба правила в одном месте, чтобы четвёртый флоу не завёл их заново.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.config import settings
from app.services.pricing_engine import pricing_engine


if TYPE_CHECKING:
    from app.database.models import Tariff, User


def remaining_days_for_switch(end_date: datetime | None, now: datetime | None = None) -> int:
    """Сколько дней остатка оплачивать при переключении тарифа.

    Живая подписка стоит минимум один день: остаток в несколько часов — это не
    ноль, иначе переключение достаётся бесплатно. Полные сутки округляются вниз,
    как и раньше, — существующие цены не меняются.

    Истёкшая подписка (или без даты окончания) даёт 0: её путь — покупка нового
    тарифа, а не переключение, и сами флоу это проверяют отдельно.
    """
    if end_date is None:
        return 0

    moment = now or datetime.now(UTC)
    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)

    delta = end_date - moment
    if delta.total_seconds() <= 0:
        return 0
    return max(1, delta.days)


def should_reset_used_traffic(upgrade_cost_kopeks: int) -> bool:
    """Обнулять ли счётчик трафика при переключении тарифа.

    Только если переключение оплачено. Бесплатное переключение (понижение
    тарифа, суточный → суточный) новую квоту не покупает, а обнуление счётчика
    при нём превращалось в бесконечный трафик: понизил тариф — счётчик с нуля,
    вернулся обратно — ещё раз.

    Общий выключатель ``RESET_TRAFFIC_ON_TARIFF_SWITCH`` по-прежнему главнее:
    выключен — не обнуляем никогда.
    """
    if not settings.RESET_TRAFFIC_ON_TARIFF_SWITCH:
        return False
    return upgrade_cost_kopeks > 0


def is_switch_direction_allowed(is_upgrade: bool) -> bool:
    """Разрешено ли переключение в этом направлении (TARIFF_SWITCH_*_ENABLED).

    Направление даёт ``calculate_tariff_switch_cost``: доплата больше нуля —
    повышение, иначе понижение. Тариф той же цены — тоже понижение.
    """
    if is_upgrade:
        return settings.TARIFF_SWITCH_UPGRADE_ENABLED
    return settings.TARIFF_SWITCH_DOWNGRADE_ENABLED


def switch_direction_refusal(is_upgrade: bool) -> dict[str, str]:
    """``detail`` для 403, когда направление запрещено: код кабинет переводит сам."""
    if is_upgrade:
        return {'code': 'tariff_upgrade_disabled', 'message': 'Tariff upgrade is disabled'}
    return {'code': 'tariff_downgrade_disabled', 'message': 'Tariff downgrade is disabled'}


def tariff_switch_allowed(
    current_tariff: Tariff,
    new_tariff: Tariff,
    remaining_days: int,
    user: User | None = None,
) -> bool:
    """Пропустит ли смена тарифа проверку направления.

    Кабинет не может вычислить направление сам (оно зависит от остатка дней и
    скидок пользователя), поэтому бот отдаёт ответ в purchase-options — иначе
    кабинет показывает «Сменить» на тарифе, который бот потом отклонит (F-001).
    """
    if settings.TARIFF_SWITCH_UPGRADE_ENABLED and settings.TARIFF_SWITCH_DOWNGRADE_ENABLED:
        return True

    result = pricing_engine.calculate_tariff_switch_cost(current_tariff, new_tariff, remaining_days, user=user)
    return is_switch_direction_allowed(result.is_upgrade)
