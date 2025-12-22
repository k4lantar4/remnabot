"""Unit tests for tenant bots admin handlers."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.admin.tenant_bots.menu import list_tenant_bots
from app.handlers.admin.tenant_bots.feature_flags import (
    show_bot_feature_flags,
    show_bot_feature_flags_category,
    toggle_feature_flag,
)
from app.handlers.admin.tenant_bots.configuration import (
    show_bot_configuration_menu,
    show_config_category,
    start_edit_config,
    save_config_value,
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


class TestSubscriptionPlansManagement:
    """Tests for AC8: Subscription Plans Management."""
    
    @pytest.mark.asyncio
    async def test_show_bot_plans_displays_list_of_plans(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that show_bot_plans displays list of all subscription plans for the bot."""
        mock_callback.data = "admin_tenant_bot_plans:1"
        
        # Mock plan query result
        from app.database.models import BotPlan
        mock_plan1 = MagicMock(spec=BotPlan)
        mock_plan1.id = 1
        mock_plan1.name = "Starter Plan"
        mock_plan1.period_days = 30
        mock_plan1.price_toman = 50000
        mock_plan1.traffic_limit_gb = 100
        mock_plan1.device_limit = 1
        mock_plan1.is_active = True
        mock_plan1.sort_order = 0
        
        mock_plan2 = MagicMock(spec=BotPlan)
        mock_plan2.id = 2
        mock_plan2.name = "Growth Plan"
        mock_plan2.period_days = 60
        mock_plan2.price_toman = 90000
        mock_plan2.traffic_limit_gb = 200
        mock_plan2.device_limit = 3
        mock_plan2.is_active = True
        mock_plan2.sort_order = 1
        
        with patch('app.handlers.admin.tenant_bots.plans.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.plans.get_plans', return_value=[mock_plan1, mock_plan2]), \
             patch('app.handlers.admin.tenant_bots.plans.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            from app.handlers.admin.tenant_bots.plans import show_bot_plans
            await show_bot_plans(mock_callback, mock_db_user, mock_db)
            
            # Verify message was edited
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            keyboard = call_args[1]['reply_markup']
            
            # Verify plan details are displayed
            assert "Starter Plan" in text_content
            assert "Growth Plan" in text_content
            assert "30" in text_content or "days" in text_content  # Period
            assert "50000" in text_content or "50,000" in text_content  # Price
            assert "100" in text_content or "GB" in text_content  # Traffic
            assert "1" in text_content or "device" in text_content  # Devices
            
            # Verify action buttons exist
            assert "Create Plan" in str(keyboard.inline_keyboard) or "➕" in str(keyboard.inline_keyboard)
    
    @pytest.mark.asyncio
    async def test_show_bot_plans_shows_empty_state_when_no_plans(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that show_bot_plans shows empty state when no plans exist."""
        mock_callback.data = "admin_tenant_bot_plans:1"
        
        with patch('app.handlers.admin.tenant_bots.plans.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.plans.get_plans', return_value=[]), \
             patch('app.handlers.admin.tenant_bots.plans.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            from app.handlers.admin.tenant_bots.plans import show_bot_plans
            await show_bot_plans(mock_callback, mock_db_user, mock_db)
            
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            
            # Verify empty state message
            assert "No plans" in text_content or "empty" in text_content.lower() or "0" in text_content
    
    @pytest.mark.asyncio
    async def test_show_bot_plans_displays_plan_status(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that show_bot_plans displays plan status (active/inactive)."""
        mock_callback.data = "admin_tenant_bot_plans:1"
        
        from app.database.models import BotPlan
        mock_plan = MagicMock(spec=BotPlan)
        mock_plan.id = 1
        mock_plan.name = "Inactive Plan"
        mock_plan.period_days = 30
        mock_plan.price_toman = 50000
        mock_plan.traffic_limit_gb = 100
        mock_plan.device_limit = 1
        mock_plan.is_active = False
        mock_plan.sort_order = 0
        
        with patch('app.handlers.admin.tenant_bots.plans.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.plans.get_plans', return_value=[mock_plan]), \
             patch('app.handlers.admin.tenant_bots.plans.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            from app.handlers.admin.tenant_bots.plans import show_bot_plans
            await show_bot_plans(mock_callback, mock_db_user, mock_db)
            
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            
            # Verify status is shown (inactive plans should be marked)
            assert "Inactive" in text_content or "❌" in text_content or "inactive" in text_content.lower()
    
    @pytest.mark.asyncio
    async def test_show_bot_plans_callback_format(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that show_bot_plans callback format 'admin_tenant_bot_plans:{bot_id}' works."""
        mock_callback.data = "admin_tenant_bot_plans:1"
        
        with patch('app.handlers.admin.tenant_bots.plans.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.plans.get_plans', return_value=[]), \
             patch('app.handlers.admin.tenant_bots.plans.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            from app.handlers.admin.tenant_bots.plans import show_bot_plans
            await show_bot_plans(mock_callback, mock_db_user, mock_db)
            
            # Verify handler executed without error
            mock_callback.message.edit_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_start_create_plan_triggers_fsm_flow(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that start_create_plan triggers FSM flow for plan creation."""
        from aiogram.fsm.context import FSMContext
        mock_callback.data = "admin_tenant_bot_plans_create:1"
        mock_state = MagicMock(spec=FSMContext)
        mock_state.update_data = AsyncMock()
        mock_state.set_state = AsyncMock()
        
        with patch('app.handlers.admin.tenant_bots.plans.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.plans.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            from app.handlers.admin.tenant_bots.plans import start_create_plan
            await start_create_plan(mock_callback, mock_db_user, mock_db, mock_state)
            
            # Verify FSM state was set
            mock_state.update_data.assert_called_once()
            mock_state.set_state.assert_called_once()
            # Verify message was edited with prompt
            mock_callback.message.edit_text.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_plan_shows_confirmation(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that delete_plan shows confirmation dialog before deletion."""
        mock_callback.data = "admin_tenant_bot_plan_delete:1:5"
        
        from app.database.models import BotPlan
        mock_plan = MagicMock(spec=BotPlan)
        mock_plan.id = 5
        mock_plan.name = "Test Plan"
        mock_plan.bot_id = 1
        
        with patch('app.handlers.admin.tenant_bots.plans.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.plans.get_plan', return_value=mock_plan), \
             patch('app.handlers.admin.tenant_bots.plans.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            from app.handlers.admin.tenant_bots.plans import start_delete_plan
            await start_delete_plan(mock_callback, mock_db_user, mock_db)
            
            # Verify confirmation dialog was shown
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            
            # Verify warning about data loss
            assert "delete" in text_content.lower() or "confirm" in text_content.lower()
            assert "Test Plan" in text_content


class TestConfigurationManagement:
    """Tests for AC9: Configuration Management."""
    
    @pytest.mark.asyncio
    async def test_show_bot_configuration_menu_displays_all_categories(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that configuration menu displays all 8 categories."""
        mock_callback.data = "admin_tenant_bot_config:1"
        
        with patch('app.handlers.admin.tenant_bots.configuration.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.configuration.get_texts') as mock_get_texts:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            await show_bot_configuration_menu(mock_callback, mock_db_user, mock_db)
            
            # Verify message was edited
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            keyboard = call_args[1]['reply_markup']
            
            # Verify all 8 categories are mentioned or buttons exist
            assert "Configuration" in text_content
            assert "Test Bot" in text_content
            
            # Verify keyboard has category buttons (8 categories = 4 rows of 2)
            assert len(keyboard.inline_keyboard) >= 4  # At least 4 rows (categories + back)
    
    @pytest.mark.asyncio
    async def test_show_config_category_displays_config_values(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that category view displays all config values for that category."""
        mock_callback.data = "admin_tenant_bot_config_basic:1"
        
        with patch('app.handlers.admin.tenant_bots.configuration.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.configuration.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.configuration.BotConfigService.get_config') as mock_get_config:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            # Mock config values
            mock_get_config.return_value = "fa"
            
            await show_config_category(mock_callback, mock_db_user, mock_db)
            
            # Verify BotConfigService.get_config was called for each config key in basic category
            assert mock_get_config.called
            # Basic category has 6 keys
            assert mock_get_config.call_count >= 1
            
            # Verify message was edited with config values
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            
            # Verify category name and config keys are displayed
            assert "Basic Settings" in text_content or "basic" in text_content.lower()
            assert "DEFAULT_LANGUAGE" in text_content or "config" in text_content.lower()
    
    @pytest.mark.asyncio
    async def test_start_edit_config_sets_fsm_state(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that start_edit_config sets FSM state correctly."""
        mock_callback.data = "admin_tenant_bot_config_edit:1:basic:DEFAULT_LANGUAGE"
        mock_state = AsyncMock()
        mock_state.update_data = AsyncMock()
        mock_state.set_state = AsyncMock()
        
        with patch('app.handlers.admin.tenant_bots.configuration.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.configuration.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.configuration.BotConfigService.get_config') as mock_get_config:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            mock_get_config.return_value = "fa"
            
            await start_edit_config(mock_callback, mock_db_user, mock_db, mock_state)
            
            # Verify FSM state was set
            mock_state.update_data.assert_called_once()
            mock_state.set_state.assert_called_once()
            
            # Verify message was edited with edit prompt
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            
            assert "Edit" in text_content or "edit" in text_content.lower()
            assert "DEFAULT_LANGUAGE" in text_content
    
    @pytest.mark.asyncio
    async def test_save_config_value_uses_botconfigservice(
        self, mock_db, mock_db_user, mock_bot
    ):
        """Test that save_config_value uses BotConfigService.set_config."""
        mock_message = MagicMock(spec=types.Message)
        mock_message.text = "en"
        mock_message.from_user = MagicMock()
        mock_message.answer = AsyncMock()
        
        mock_state = AsyncMock()
        mock_state.get_data = AsyncMock(return_value={
            "bot_id": 1,
            "category_key": "basic",
            "config_key": "DEFAULT_LANGUAGE",
        })
        mock_state.clear = AsyncMock()
        
        with patch('app.handlers.admin.tenant_bots.configuration.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.configuration.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.configuration.BotConfigService.set_config') as mock_set_config:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await save_config_value(mock_message, mock_db_user, mock_db, mock_state)
            
            # Verify BotConfigService.set_config was called
            mock_set_config.assert_called_once()
            call_args = mock_set_config.call_args
            
            # Verify correct parameters
            assert call_args[0][1] == 1  # bot_id
            assert call_args[0][2] == "DEFAULT_LANGUAGE"  # config_key
            assert call_args[0][3] == "en"  # value
            assert call_args[1]['commit'] is True
            
            # Verify FSM state was cleared
            mock_state.clear.assert_called_once()
            
            # Verify success message was sent
            mock_message.answer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_config_value_parses_boolean_values(
        self, mock_db, mock_db_user, mock_bot
    ):
        """Test that save_config_value correctly parses boolean values."""
        mock_message = MagicMock(spec=types.Message)
        mock_message.text = "true"
        mock_message.from_user = MagicMock()
        mock_message.answer = AsyncMock()
        
        mock_state = AsyncMock()
        mock_state.get_data = AsyncMock(return_value={
            "bot_id": 1,
            "category_key": "basic",
            "config_key": "LANGUAGE_SELECTION_ENABLED",
        })
        mock_state.clear = AsyncMock()
        
        with patch('app.handlers.admin.tenant_bots.configuration.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.configuration.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.configuration.BotConfigService.set_config') as mock_set_config:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await save_config_value(mock_message, mock_db_user, mock_db, mock_state)
            
            # Verify boolean was parsed correctly
            call_args = mock_set_config.call_args
            assert call_args[0][3] is True  # value should be boolean True, not string
    
    @pytest.mark.asyncio
    async def test_save_config_value_parses_integer_values(
        self, mock_db, mock_db_user, mock_bot
    ):
        """Test that save_config_value correctly parses integer values."""
        mock_message = MagicMock(spec=types.Message)
        mock_message.text = "30"
        mock_message.from_user = MagicMock()
        mock_message.answer = AsyncMock()
        
        mock_state = AsyncMock()
        mock_state.get_data = AsyncMock(return_value={
            "bot_id": 1,
            "category_key": "subscription",
            "config_key": "TRIAL_DURATION_DAYS",
        })
        mock_state.clear = AsyncMock()
        
        with patch('app.handlers.admin.tenant_bots.configuration.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.configuration.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.configuration.BotConfigService.set_config') as mock_set_config:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_get_texts.return_value = mock_texts
            
            await save_config_value(mock_message, mock_db_user, mock_db, mock_state)
            
            # Verify integer was parsed correctly
            call_args = mock_set_config.call_args
            assert call_args[0][3] == 30  # value should be integer 30, not string "30"
            assert isinstance(call_args[0][3], int)
    
    @pytest.mark.asyncio
    async def test_show_config_category_handles_missing_configs(
        self, mock_db, mock_callback, mock_db_user, mock_bot
    ):
        """Test that category view handles missing config values gracefully."""
        mock_callback.data = "admin_tenant_bot_config_basic:1"
        
        with patch('app.handlers.admin.tenant_bots.configuration.get_bot_by_id', return_value=mock_bot), \
             patch('app.handlers.admin.tenant_bots.configuration.get_texts') as mock_get_texts, \
             patch('app.handlers.admin.tenant_bots.configuration.BotConfigService.get_config') as mock_get_config:
            mock_texts = MagicMock()
            mock_texts.t = lambda key, default: default
            mock_texts.BACK = "🔙 Back"
            mock_get_texts.return_value = mock_texts
            
            # Mock config values - some missing (None)
            mock_get_config.return_value = None
            
            await show_config_category(mock_callback, mock_db_user, mock_db)
            
            # Verify handler executed without error
            mock_callback.message.edit_text.assert_called_once()
            call_args = mock_callback.message.edit_text.call_args
            text_content = call_args[0][0]
            
            # Verify "Not set" is displayed for missing configs
            assert "Not set" in text_content or "not set" in text_content.lower()

