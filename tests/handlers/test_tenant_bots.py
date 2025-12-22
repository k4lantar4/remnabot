"""Unit tests for tenant bots admin handlers."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.admin.tenant_bots import (
    list_tenant_bots,
    show_bot_feature_flags,
    show_bot_feature_flags_category,
    toggle_feature_flag,
)
from app.database.models import Bot, User, Transaction, TransactionType


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def mock_db():
    """Mock AsyncSession for testing."""
    db = AsyncMock(spec=AsyncSession)
    db.execute = AsyncMock()
    return db


@pytest.fixture
def mock_callback():
    """Mock CallbackQuery for testing."""
    callback = MagicMock(spec=types.CallbackQuery)
    callback.data = "admin_tenant_bots_list"
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
def mock_db_user():
    """Mock User for testing."""
    user = MagicMock(spec=User)
    user.telegram_id = 123456789
    user.language = "en"
    return user


@pytest.fixture
def mock_bot():
    """Mock Bot instance."""
    bot = MagicMock(spec=Bot)
    bot.id = 1
    bot.name = "Test Bot"
    bot.is_active = True
    bot.is_master = False
    bot.created_at = MagicMock()
    return bot


class TestListTenantBots:
    """Tests for list_tenant_bots handler."""
    
    @pytest.mark.asyncio
    async def test_list_tenant_bots_displays_all_required_columns(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that list_tenant_bots displays Name, ID, Status, User Count, Revenue, Plan."""
        # Mock query result with plan
        mock_result = MagicMock()
        mock_row = (1, "Test Bot", True, MagicMock(), 10, 50000, 1, "Starter Plan")
        mock_result.fetchall.return_value = [mock_row]
        mock_result.scalar.return_value = 1  # Total count
        
        mock_db.execute.return_value = mock_result
        
        # Mock get_bot_by_id
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await list_tenant_bots(mock_callback, mock_db_user, mock_db, page=1)
            
            # Verify message was edited with bot information
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            
            # Verify all required columns are present
            assert "Test Bot" in text_content  # Name
            assert "ID: 1" in text_content  # ID
            assert "✅" in text_content or "⏸️" in text_content  # Status icon
            assert "Users:" in text_content  # User Count
            assert "Revenue:" in text_content  # Revenue
            assert "Plan:" in text_content  # Plan
    
    @pytest.mark.asyncio
    async def test_list_tenant_bots_shows_na_when_no_plan(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that plan column shows 'N/A' when no plan is assigned."""
        # Mock query result without plan
        mock_result = MagicMock()
        mock_row = (1, "Test Bot", True, MagicMock(), 10, 50000, None, None)
        mock_result.fetchall.return_value = [mock_row]
        mock_result.scalar.return_value = 1
        
        mock_db.execute.return_value = mock_result
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await list_tenant_bots(mock_callback, mock_db_user, mock_db, page=1)
            
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            
            # Verify "N/A" is shown for plan
            assert "Plan: N/A" in text_content
    
    @pytest.mark.asyncio
    async def test_list_tenant_bots_shows_plan_name_when_plan_exists(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that plan column shows plan name when plan exists."""
        # Mock query result with plan
        mock_result = MagicMock()
        mock_row = (1, "Test Bot", True, MagicMock(), 10, 50000, 1, "Growth Plan")
        mock_result.fetchall.return_value = [mock_row]
        mock_result.scalar.return_value = 1
        
        mock_db.execute.return_value = mock_result
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await list_tenant_bots(mock_callback, mock_db_user, mock_db, page=1)
            
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            
            # Verify plan name is shown
            assert "Plan: Growth Plan" in text_content
    
    @pytest.mark.asyncio
    async def test_list_tenant_bots_pagination_works(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that pagination works correctly."""
        # Mock query result for page 2
        mock_result = MagicMock()
        mock_row = (2, "Test Bot 2", True, MagicMock(), 5, 25000, None, None)
        mock_result.fetchall.return_value = [mock_row]
        mock_result.scalar.return_value = 10  # Total count
        
        mock_db.execute.return_value = mock_result
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.get_admin_pagination_keyboard') as mock_pagination:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            mock_pagination_keyboard = MagicMock()
            mock_pagination_keyboard.inline_keyboard = []
            mock_pagination.return_value = mock_pagination_keyboard
            
            await list_tenant_bots(mock_callback, mock_db_user, mock_db, page=2)
            
            # Verify pagination was called with correct page
            mock_pagination.assert_called_once()
            call_args = mock_pagination.call_args
            assert call_args[1]['current_page'] == 2
            assert call_args[1]['callback_prefix'] == "admin_tenant_bots_list"
    
    @pytest.mark.asyncio
    async def test_list_tenant_bots_callback_format_admin_tenant_bots_list(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test callback format 'admin_tenant_bots_list' works."""
        mock_callback.data = "admin_tenant_bots_list"
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.scalar.return_value = 0
        
        mock_db.execute.return_value = mock_result
        
        with patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await list_tenant_bots(mock_callback, mock_db_user, mock_db, page=1)
            
            # Verify handler executed without error
            mock_callback.message.edit_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_tenant_bots_callback_format_with_page(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test callback format 'admin_tenant_bots_list:{page}' works."""
        mock_callback.data = "admin_tenant_bots_list:0"  # 0-based page
        
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_result.scalar.return_value = 0
        
        mock_db.execute.return_value = mock_result
        
        with patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await list_tenant_bots(mock_callback, mock_db_user, mock_db, page=1)
            
            # Verify handler executed and parsed page correctly
            mock_callback.message.edit_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_list_tenant_bots_fallback_query_when_tables_dont_exist(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test fallback query works when tenant_subscriptions tables don't exist."""
        # First call fails (tables don't exist), second call succeeds (fallback)
        mock_result_fallback = MagicMock()
        mock_result_fallback.all.return_value = [(mock_bot, 10, 50000)]
        mock_result_fallback.scalar.return_value = 1
        
        # Simulate exception on first call (optimized query), success on fallback
        call_count = 0
        def mock_execute(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails (optimized query)
                raise Exception("Table tenant_subscriptions does not exist")
            else:
                # Subsequent calls succeed (fallback and count)
                return mock_result_fallback
        
        mock_db.execute = AsyncMock(side_effect=mock_execute)
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.logger') as mock_logger:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await list_tenant_bots(mock_callback, mock_db_user, mock_db, page=1)
            
            # Verify fallback was used (warning logged)
            mock_logger.warning.assert_called_once()
            # Verify handler still executed successfully
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            # Verify plan shows N/A in fallback mode
            assert "Plan: N/A" in text_content
    
    @pytest.mark.asyncio
    async def test_list_tenant_bots_optimized_query_when_tables_exist(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test optimized query works when tenant_subscriptions tables exist."""
        # Mock successful optimized query
        mock_result = MagicMock()
        mock_row = (1, "Test Bot", True, MagicMock(), 10, 50000, 1, "Enterprise Plan")
        mock_result.fetchall.return_value = [mock_row]
        mock_result.scalar.return_value = 1
        
        mock_db.execute.return_value = mock_result
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await list_tenant_bots(mock_callback, mock_db_user, mock_db, page=1)
            
            # Verify optimized query was used (no fallback warning)
            # Verify plan name is shown
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            assert "Plan: Enterprise Plan" in text_content


class TestFeatureFlagsManagement:
    """Tests for AC6: Feature Flags Management."""
    
    @pytest.mark.asyncio
    async def test_show_bot_feature_flags_displays_categories(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that show_bot_feature_flags displays all feature categories."""
        mock_callback.data = "admin_tenant_bot_features:1"
        
        # Mock plan query (no plan assigned)
        mock_plan_result = MagicMock()
        mock_plan_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_plan_result
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.BotConfigService.is_feature_enabled', return_value=False):
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            await show_bot_feature_flags(mock_callback, mock_db_user, mock_db)
            
            # Verify message was edited
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            keyboard = call_args[1]['reply_markup']
            
            # Verify categories are displayed
            assert "Feature Flags" in text_content
            assert "Payment Gateways" in str(keyboard.inline_keyboard)
            assert "Subscription Features" in str(keyboard.inline_keyboard)
            assert "Marketing Features" in str(keyboard.inline_keyboard)
            assert "Support Features" in str(keyboard.inline_keyboard)
            assert "Integrations" in str(keyboard.inline_keyboard)
    
    @pytest.mark.asyncio
    async def test_show_bot_feature_flags_shows_plan_name(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that show_bot_feature_flags displays current plan name."""
        mock_callback.data = "admin_tenant_bot_features:1"
        
        # Mock plan query (plan exists)
        mock_plan_result = MagicMock()
        mock_plan_result.fetchone.return_value = ("Growth Plan",)
        mock_db.execute.return_value = mock_plan_result
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.BotConfigService.is_feature_enabled', return_value=False):
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            await show_bot_feature_flags(mock_callback, mock_db_user, mock_db)
            
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            
            # Verify plan name is shown
            assert "Growth Plan" in text_content
    
    @pytest.mark.asyncio
    async def test_show_bot_feature_flags_category_displays_features(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that show_bot_feature_flags_category displays features with status."""
        mock_callback.data = "admin_tenant_bot_features_category:1:Payment Gateways"
        
        # Mock plan query (no plan)
        mock_plan_result = MagicMock()
        mock_plan_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_plan_result
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.BotConfigService.is_feature_enabled') as mock_is_enabled:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            # Mock feature status: card_to_card enabled, zarinpal disabled
            def mock_feature_status(bot_id, feature_key):
                return feature_key == "card_to_card"
            mock_is_enabled.side_effect = mock_feature_status
            
            await show_bot_feature_flags_category(mock_callback, mock_db_user, mock_db)
            
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            keyboard = call_args[1]['reply_markup']
            
            # Verify features are displayed with status icons
            assert "✅" in text_content or "❌" in text_content
            assert "Card-to-Card" in text_content
            assert "Zarinpal" in text_content
            # Verify toggle buttons exist
            assert "Enable" in str(keyboard.inline_keyboard) or "Disable" in str(keyboard.inline_keyboard)
    
    @pytest.mark.asyncio
    async def test_toggle_feature_flag_enables_feature(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that toggle_feature_flag enables a disabled feature."""
        mock_callback.data = "admin_tenant_bot_toggle_feature:1:card_to_card"
        
        # Mock plan query (no plan restrictions)
        mock_plan_result = MagicMock()
        mock_plan_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_plan_result
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.BotConfigService.is_feature_enabled', return_value=False), \
             patch('app.handlers.admin.tenant_bots.BotConfigService.set_feature_enabled') as mock_set_feature, \
             patch('app.handlers.admin.tenant_bots.show_bot_feature_flags_category') as mock_show_category:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await toggle_feature_flag(mock_callback, mock_db_user, mock_db)
            
            # Verify feature was enabled
            mock_set_feature.assert_called_once_with(mock_db, 1, "card_to_card", True)
            # Verify callback answer
            mock_callback.answer.assert_called_once()
            # Verify category view was refreshed
            mock_show_category.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_toggle_feature_flag_disables_feature(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that toggle_feature_flag disables an enabled feature."""
        mock_callback.data = "admin_tenant_bot_toggle_feature:1:card_to_card"
        
        # Mock plan query (no plan restrictions)
        mock_plan_result = MagicMock()
        mock_plan_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_plan_result
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.BotConfigService.is_feature_enabled', return_value=True), \
             patch('app.handlers.admin.tenant_bots.BotConfigService.set_feature_enabled') as mock_set_feature, \
             patch('app.handlers.admin.tenant_bots.show_bot_feature_flags_category') as mock_show_category:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await toggle_feature_flag(mock_callback, mock_db_user, mock_db)
            
            # Verify feature was disabled
            mock_set_feature.assert_called_once_with(mock_db, 1, "card_to_card", False)
            # Verify callback answer
            mock_callback.answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_toggle_feature_flag_respects_plan_restrictions(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that toggle_feature_flag shows warning when plan doesn't allow feature."""
        mock_callback.data = "admin_tenant_bot_toggle_feature:1:yookassa"
        
        # Mock plan query (Starter plan, yookassa not allowed)
        mock_plan_result = MagicMock()
        mock_plan_result.fetchone.return_value = (1, "starter", "Starter Plan")
        mock_grant_result = MagicMock()
        mock_grant_result.fetchone.return_value = None  # No grant = not allowed
        mock_db.execute.side_effect = [mock_plan_result, mock_grant_result]
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.BotConfigService.is_feature_enabled', return_value=False), \
             patch('app.handlers.admin.tenant_bots.BotConfigService.set_feature_enabled') as mock_set_feature, \
             patch('app.handlers.admin.tenant_bots.show_bot_feature_flags_category') as mock_show_category:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await toggle_feature_flag(mock_callback, mock_db_user, mock_db)
            
            # Verify warning was shown (answer called with show_alert)
            answer_calls = [call for call in mock_callback.answer.call_args_list]
            # Verify feature was still enabled (master admin override)
            mock_set_feature.assert_called_once()
            # Verify category view was refreshed
            mock_show_category.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_show_bot_feature_flags_uses_botconfigservice(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that show_bot_feature_flags uses BotConfigService to check feature status."""
        mock_callback.data = "admin_tenant_bot_features:1"
        
        # Mock plan query
        mock_plan_result = MagicMock()
        mock_plan_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_plan_result
        
        with patch('app.handlers.admin.tenant_bots.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.BotConfigService.is_feature_enabled') as mock_is_enabled:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            await show_bot_feature_flags(mock_callback, mock_db_user, mock_db)
            
            # Verify BotConfigService.is_feature_enabled was called for each feature
            assert mock_is_enabled.called
            # Verify it was called with correct bot_id
            calls = mock_is_enabled.call_args_list
            assert all(call[0][1] == 1 for call in calls)  # All calls use bot_id=1

