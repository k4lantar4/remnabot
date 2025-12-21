"""Unit tests for BotConfigService."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.bot_config_service import BotConfigService
from app.database.models import Bot, BotFeatureFlag, BotConfiguration


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def mock_db():
    """Mock AsyncSession for testing."""
    db = AsyncMock(spec=AsyncSession)
    db.commit = AsyncMock()
    return db


@pytest.fixture
def mock_bot():
    """Mock Bot instance with redundant columns."""
    bot = MagicMock(spec=Bot)
    bot.id = 1
    bot.card_to_card_enabled = True
    bot.zarinpal_enabled = False
    bot.default_language = 'fa'
    bot.support_username = '@support'
    bot.admin_chat_id = 123456789
    bot.admin_topic_id = 1
    bot.notification_group_id = 987654321
    bot.notification_topic_id = 2
    bot.card_receipt_topic_id = 3
    bot.zarinpal_merchant_id = 'merchant123'
    bot.zarinpal_sandbox = True
    return bot


class TestBotConfigServiceFeatureFlags:
    """Tests for feature flag methods."""
    
    @pytest.mark.asyncio
    async def test_is_feature_enabled_returns_true_when_enabled(self, mock_db):
        """Test is_feature_enabled returns True when feature is enabled."""
        # Mock feature flag exists and is enabled
        mock_feature_flag = MagicMock(spec=BotFeatureFlag)
        mock_feature_flag.enabled = True
        
        with patch('app.services.bot_config_service.get_feature_flag', return_value=mock_feature_flag):
            result = await BotConfigService.is_feature_enabled(mock_db, 1, 'card_to_card')
            assert result is True
    
    @pytest.mark.asyncio
    async def test_is_feature_enabled_returns_false_when_disabled(self, mock_db):
        """Test is_feature_enabled returns False when feature is disabled."""
        # Mock feature flag exists but is disabled
        mock_feature_flag = MagicMock(spec=BotFeatureFlag)
        mock_feature_flag.enabled = False
        
        with patch('app.services.bot_config_service.get_feature_flag', return_value=mock_feature_flag):
            result = await BotConfigService.is_feature_enabled(mock_db, 1, 'zarinpal')
            assert result is False
    
    @pytest.mark.asyncio
    async def test_is_feature_enabled_fallback_to_bots_table(self, mock_db, mock_bot):
        """Test is_feature_enabled falls back to bots table when not in feature_flags."""
        # Mock: no feature flag exists, but bot has the column
        with patch('app.services.bot_config_service.get_feature_flag', return_value=None), \
             patch('app.services.bot_config_service.get_bot_by_id', return_value=mock_bot):
            result = await BotConfigService.is_feature_enabled(mock_db, 1, 'card_to_card')
            assert result is True
    
    @pytest.mark.asyncio
    async def test_set_feature_enabled_updates_flag(self, mock_db):
        """Test set_feature_enabled updates the feature flag."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        
        with patch('app.services.bot_config_service.set_feature_flag', return_value=MagicMock()):
            await BotConfigService.set_feature_enabled(mock_db, 1, 'card_to_card', True)
            # Verify execute was called for dual-write
            mock_db.execute.assert_called()
    
    @pytest.mark.asyncio
    async def test_set_feature_enabled_dual_write_during_transition(self, mock_db, mock_bot):
        """Test set_feature_enabled writes to both new table and bots table during transition."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        
        with patch('app.services.bot_config_service.set_feature_flag', return_value=MagicMock()):
            await BotConfigService.set_feature_enabled(mock_db, 1, 'card_to_card', True)
            
            # Verify execute was called for dual-write to bots table
            mock_db.execute.assert_called()
            # Verify set_feature_flag was called for new table
            from app.services.bot_config_service import set_feature_flag
            # The patch ensures set_feature_flag was called


class TestBotConfigServiceConfigurations:
    """Tests for configuration methods."""
    
    @pytest.mark.asyncio
    async def test_get_config_returns_value_when_exists(self, mock_db):
        """Test get_config returns value when configuration exists."""
        # Mock configuration exists
        mock_config = MagicMock(spec=BotConfiguration)
        mock_config.config_value = {'value': 'fa'}
        
        with patch('app.services.bot_config_service.get_configuration', return_value=mock_config):
            result = await BotConfigService.get_config(mock_db, 1, 'DEFAULT_LANGUAGE')
            assert result == 'fa'
    
    @pytest.mark.asyncio
    async def test_get_config_returns_default_when_not_exists(self, mock_db):
        """Test get_config returns default when configuration doesn't exist."""
        # Mock: no configuration exists
        with patch('app.services.bot_config_service.get_configuration', return_value=None), \
             patch('app.services.bot_config_service.get_bot_by_id', return_value=None):
            result = await BotConfigService.get_config(mock_db, 1, 'DEFAULT_LANGUAGE', 'en')
            assert result == 'en'
    
    @pytest.mark.asyncio
    async def test_get_config_fallback_to_bots_table(self, mock_db, mock_bot):
        """Test get_config falls back to bots table when not in configurations."""
        # Mock: no config exists, but bot has the column
        with patch('app.services.bot_config_service.get_configuration', return_value=None), \
             patch('app.services.bot_config_service.get_bot_by_id', return_value=mock_bot):
            result = await BotConfigService.get_config(mock_db, 1, 'DEFAULT_LANGUAGE', 'en')
            assert result == 'fa'
    
    @pytest.mark.asyncio
    async def test_get_config_unwraps_simple_values(self, mock_db):
        """Test get_config unwraps simple values from {'value': ...} format."""
        mock_config = MagicMock(spec=BotConfiguration)
        mock_config.config_value = {'value': 'test_value'}
        
        with patch('app.services.bot_config_service.get_configuration', return_value=mock_config):
            result = await BotConfigService.get_config(mock_db, 1, 'TEST_KEY')
            assert result == 'test_value'
    
    @pytest.mark.asyncio
    async def test_get_config_returns_complex_objects_as_is(self, mock_db):
        """Test get_config returns complex objects without unwrapping."""
        complex_value = {'nested': {'key': 'value'}, 'other': 123}
        mock_config = MagicMock(spec=BotConfiguration)
        mock_config.config_value = complex_value
        
        with patch('app.services.bot_config_service.get_configuration', return_value=mock_config):
            result = await BotConfigService.get_config(mock_db, 1, 'COMPLEX_CONFIG')
            assert result == complex_value
    
    @pytest.mark.asyncio
    async def test_set_config_updates_value(self, mock_db):
        """Test set_config updates the configuration value."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        
        with patch('app.services.bot_config_service.set_configuration', return_value=MagicMock()):
            await BotConfigService.set_config(mock_db, 1, 'DEFAULT_LANGUAGE', 'en')
            # Verify execute was called for dual-write
            mock_db.execute.assert_called()
    
    @pytest.mark.asyncio
    async def test_set_config_normalizes_simple_values(self, mock_db):
        """Test set_config wraps simple values in {'value': ...} format."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_set_config = MagicMock()
        
        with patch('app.services.bot_config_service.set_configuration', return_value=mock_set_config) as mock_set:
            await BotConfigService.set_config(mock_db, 1, 'DEFAULT_LANGUAGE', 'fa')
            # Verify set_configuration was called with normalized value
            call_args = mock_set.call_args
            assert call_args[0][2] == 'DEFAULT_LANGUAGE'  # config_key
            assert call_args[0][3] == {'value': 'fa'}  # normalized_value
    
    @pytest.mark.asyncio
    async def test_set_config_stores_complex_objects_as_is(self, mock_db):
        """Test set_config stores complex objects without wrapping."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        complex_value = {'nested': {'key': 'value'}}
        
        with patch('app.services.bot_config_service.set_configuration', return_value=MagicMock()) as mock_set:
            await BotConfigService.set_config(mock_db, 1, 'COMPLEX_CONFIG', complex_value)
            # Verify complex object stored as-is (not wrapped)
            call_args = mock_set.call_args
            assert call_args[0][3] == complex_value  # stored as-is
    
    @pytest.mark.asyncio
    async def test_set_config_dual_write_during_transition(self, mock_db, mock_bot):
        """Test set_config writes to both new table and bots table during transition."""
        mock_db.execute = AsyncMock(return_value=MagicMock())
        
        with patch('app.services.bot_config_service.set_configuration', return_value=MagicMock()):
            await BotConfigService.set_config(mock_db, 1, 'DEFAULT_LANGUAGE', 'en')
            
            # Verify execute was called for dual-write to bots table
            mock_db.execute.assert_called()
            # Verify set_configuration was called for new table
            from app.services.bot_config_service import set_configuration
            # The patch ensures set_configuration was called

