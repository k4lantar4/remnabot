"""
Тесты для утилит ценообразования и форматирования цен.

Этот модуль тестирует функции из app/utils/pricing_utils.py и app/localization/texts.py,
особенно функции отображения цен со скидками на кнопках подписки.
"""

from unittest.mock import MagicMock, patch

from app.localization.texts import _build_dynamic_values
from app.utils.pricing_utils import resolve_period_price


# DEPRECATED: format_period_option_label tests removed - function replaced with unified price_display system


class TestBuildDynamicValues:
    """
    Тесты для функции _build_dynamic_values из texts.py.

    NOTE: PERIOD_*_DAYS константы были удалены из _build_dynamic_values,
    так как теперь кнопки периодов генерируются динамически в get_subscription_period_keyboard()
    с учетом персональных скидок пользователя.
    """

    @patch('app.localization.texts.settings')
    def test_returns_empty_dict_for_unknown_language(self, mock_settings: MagicMock) -> None:
        """Неизвестный язык должен возвращать пустой словарь."""
        result = _build_dynamic_values('fr-FR')  # Французский не поддерживается
        assert result == {}

    @patch('app.localization.texts.settings')
    def test_traffic_keys_also_generated(self, mock_settings: MagicMock) -> None:
        """Должны генерироваться ключи трафика и другие динамические значения."""
        # Настройка моков для traffic цен
        mock_settings.format_price = lambda x: f'{x // 100} ₽'
        mock_settings.PRICE_TRAFFIC_5GB = 10000
        mock_settings.PRICE_TRAFFIC_10GB = 20000
        mock_settings.PRICE_TRAFFIC_25GB = 30000
        mock_settings.PRICE_TRAFFIC_50GB = 40000
        mock_settings.PRICE_TRAFFIC_100GB = 50000
        mock_settings.PRICE_TRAFFIC_250GB = 60000
        mock_settings.PRICE_TRAFFIC_UNLIMITED = 70000

        result = _build_dynamic_values('ru-RU')

        # Проверяем наличие ключей трафика
        assert 'TRAFFIC_5GB' in result
        assert 'TRAFFIC_10GB' in result
        assert 'TRAFFIC_UNLIMITED' in result
        assert 'SUPPORT_INFO' in result


class TestResolvePeriodPrice:
    @patch('app.utils.pricing_utils.settings')
    def test_prefers_tariff_period_price(self, mock_settings: MagicMock) -> None:
        tariff = MagicMock()
        tariff.period_prices = {'30': 12345}
        price, source = resolve_period_price(tariff, 30)
        assert price == 12345
        assert source == 'tariff.period_prices'

    @patch('app.utils.pricing_utils.settings')
    def test_uses_env_when_tariff_price_zero(self, mock_settings: MagicMock) -> None:
        tariff = MagicMock()
        tariff.period_prices = {'90': 0}
        mock_settings.PRICE_90_DAYS = 55000
        price, source = resolve_period_price(tariff, 90)
        assert price == 55000
        assert source == 'settings.PRICE_90_DAYS'

    @patch('app.utils.pricing_utils.settings')
    def test_uses_ladder_when_tariff_and_env_zero(self, mock_settings: MagicMock) -> None:
        tariff = MagicMock()
        tariff.period_prices = {'60': 0}
        mock_settings.PRICE_60_DAYS = 0
        price, source = resolve_period_price(tariff, 60)
        assert price == 38000
        assert source == 'fallback.ladder'

    @patch('app.utils.pricing_utils.settings')
    def test_uses_monthly_fallback_for_non_standard_period(self, mock_settings: MagicMock) -> None:
        tariff = MagicMock()
        tariff.period_prices = {}
        mock_settings.DEFAULT_PERIOD_PRICE_PER_MONTH = 20000
        price, source = resolve_period_price(tariff, 120)
        assert price == 80000
        assert source == 'fallback.monthly'

    @patch('app.utils.pricing_utils.settings')
    def test_preserves_negative_price_as_disabled(self, mock_settings: MagicMock) -> None:
        tariff = MagicMock()
        tariff.period_prices = {'30': -1}
        price, source = resolve_period_price(tariff, 30)
        assert price == -1
        assert source == 'tariff.period_prices'
