"""Register all tenant bots handlers."""
from aiogram import Dispatcher, F
from aiogram.filters import StateFilter

from app.states import AdminStates
from .menu import (
    show_tenant_bots_menu,
    list_tenant_bots,
    handle_tenant_bots_list_pagination,
    show_tenant_bots_statistics,
    show_tenant_bots_settings,
)
from .create import (
    start_create_bot,
    process_bot_name,
    process_bot_token,
)
from .detail import show_bot_detail
from .management import (
    activate_tenant_bot,
    deactivate_tenant_bot,
    start_delete_bot,
    confirm_delete_bot,
)
from .settings import (
    show_bot_settings,
    toggle_card_to_card,
    toggle_zarinpal,
    start_edit_bot_name,
    process_edit_bot_name,
    start_edit_bot_language,
    process_edit_bot_language,
    start_edit_bot_support,
    process_edit_bot_support,
    start_edit_bot_notifications,
    process_edit_bot_notifications,
)
from .statistics import show_bot_statistics
from .feature_flags import (
    show_bot_feature_flags,
    show_bot_feature_flags_category,
    toggle_feature_flag,
)
from .payments import (
    show_bot_payment_cards,
    show_bot_payment_methods,
    toggle_payment_method,
    show_zarinpal_config,
    toggle_zarinpal_sandbox,
)
from .test import test_bot_status
from .webhook import update_all_webhooks
from .plans import (
    show_bot_plans,
    start_create_plan,
    process_plan_creation_step,
    show_plan_detail,
    toggle_plan_status,
    start_delete_plan,
    confirm_delete_plan,
)
from .configuration import (
    show_bot_configuration_menu,
    show_config_category,
    start_edit_config,
    save_config_value,
)
from .analytics import show_bot_analytics
from .common import logger


def register_handlers(dp: Dispatcher) -> None:
    """Register tenant bots handlers."""
    # Menu handlers
    dp.callback_query.register(
        show_tenant_bots_menu,
        F.data == "admin_tenant_bots_menu"
    )
    
    # Main list handler (page 1 or no page specified)
    dp.callback_query.register(
        list_tenant_bots,
        F.data == "admin_tenant_bots_list"
    )
    
    # Old pattern support (backward compatible): admin_tenant_bots_list:{page}
    dp.callback_query.register(
        list_tenant_bots,
        F.data.startswith("admin_tenant_bots_list:") & ~F.data.contains("_page_")
    )
    
    # Pagination handler (standard pattern)
    dp.callback_query.register(
        handle_tenant_bots_list_pagination,
        F.data.startswith("admin_tenant_bots_list_page_")
    )
    
    # Bot detail
    dp.callback_query.register(
        show_bot_detail,
        F.data.startswith("admin_tenant_bot_detail:")
    )
    
    # Create bot handlers
    dp.callback_query.register(
        start_create_bot,
        F.data == "admin_tenant_bots_create"
    )
    
    dp.message.register(
        process_bot_name,
        StateFilter(AdminStates.creating_tenant_bot_name)
    )
    
    dp.message.register(
        process_bot_token,
        StateFilter(AdminStates.creating_tenant_bot_token)
    )
    
    # Management handlers
    dp.callback_query.register(
        activate_tenant_bot,
        F.data.startswith("admin_tenant_bot_activate:")
    )
    
    dp.callback_query.register(
        deactivate_tenant_bot,
        F.data.startswith("admin_tenant_bot_deactivate:")
    )
    
    # Delete bot
    dp.callback_query.register(
        start_delete_bot,
        F.data.startswith("admin_tenant_bot_delete:") & ~F.data.contains("_soft:") & ~F.data.contains("_hard:")
    )
    
    # Delete bot confirmation (soft and hard)
    dp.callback_query.register(
        confirm_delete_bot,
        F.data.startswith("admin_tenant_bot_delete_soft:") | F.data.startswith("admin_tenant_bot_delete_hard:")
    )
    
    # Statistics and Settings buttons
    dp.callback_query.register(
        show_tenant_bots_statistics,
        F.data == "admin_tenant_bots_stats"
    )
    
    dp.callback_query.register(
        show_tenant_bots_settings,
        F.data == "admin_tenant_bots_settings"
    )
    
    # Settings handlers
    dp.callback_query.register(
        show_bot_settings,
        F.data.startswith("admin_tenant_bot_settings:")
    )
    
    dp.callback_query.register(
        toggle_card_to_card,
        F.data.startswith("admin_tenant_bot_toggle_card:")
    )
    
    dp.callback_query.register(
        toggle_zarinpal,
        F.data.startswith("admin_tenant_bot_toggle_zarinpal:")
    )
    
    dp.callback_query.register(
        start_edit_bot_name,
        F.data.startswith("admin_tenant_bot_edit_name:")
    )
    
    dp.callback_query.register(
        start_edit_bot_language,
        F.data.startswith("admin_tenant_bot_edit_language:")
    )
    
    dp.callback_query.register(
        start_edit_bot_support,
        F.data.startswith("admin_tenant_bot_edit_support:")
    )
    
    dp.callback_query.register(
        start_edit_bot_notifications,
        F.data.startswith("admin_tenant_bot_edit_notifications:")
    )
    
    dp.message.register(
        process_edit_bot_name,
        StateFilter(AdminStates.editing_tenant_bot_name)
    )
    
    dp.message.register(
        process_edit_bot_language,
        StateFilter(AdminStates.editing_tenant_bot_language)
    )
    
    dp.message.register(
        process_edit_bot_support,
        StateFilter(AdminStates.editing_tenant_bot_support)
    )
    
    dp.message.register(
        process_edit_bot_notifications,
        StateFilter(AdminStates.editing_tenant_bot_notifications)
    )
    
    # Statistics handlers
    dp.callback_query.register(
        show_bot_statistics,
        F.data.startswith("admin_tenant_bot_stats:")
    )
    
    # Feature flags handlers
    dp.callback_query.register(
        toggle_feature_flag,
        F.data.startswith("admin_tenant_bot_toggle_feature:")
    )
    
    dp.callback_query.register(
        show_bot_feature_flags_category,
        F.data.startswith("admin_tenant_bot_features_category:")
    )
    
    dp.callback_query.register(
        show_bot_feature_flags,
        F.data.startswith("admin_tenant_bot_features:")
    )
    
    # Payment handlers
    dp.callback_query.register(
        show_bot_payment_cards,
        F.data.startswith("admin_tenant_bot_cards:")
    )
    
    dp.callback_query.register(
        show_bot_payment_methods,
        F.data.startswith("admin_tenant_bot_payments:")
    )
    
    dp.callback_query.register(
        toggle_payment_method,
        F.data.startswith("admin_tenant_bot_toggle_payment:")
    )
    
    dp.callback_query.register(
        show_zarinpal_config,
        F.data.startswith("admin_tenant_bot_zarinpal:")
    )
    
    dp.callback_query.register(
        toggle_zarinpal_sandbox,
        F.data.startswith("admin_tenant_bot_toggle_zarinpal_sandbox:")
    )
    
    # Test handlers
    dp.callback_query.register(
        test_bot_status,
        F.data.startswith("admin_tenant_bot_test:")
    )
    
    # Webhook handlers
    dp.callback_query.register(
        update_all_webhooks,
        F.data == "admin_tenant_bots_update_webhooks"
    )
    
    # Plans handlers
    dp.callback_query.register(
        show_bot_plans,
        F.data.startswith("admin_tenant_bot_plans:") & ~F.data.contains("_create:") & ~F.data.contains("_delete:") & ~F.data.contains("_detail:") & ~F.data.contains("_toggle:")
    )
    
    dp.callback_query.register(
        show_plan_detail,
        F.data.startswith("admin_tenant_bot_plan_detail:")
    )
    
    dp.callback_query.register(
        toggle_plan_status,
        F.data.startswith("admin_tenant_bot_plan_toggle:")
    )
    
    dp.callback_query.register(
        start_create_plan,
        F.data.startswith("admin_tenant_bot_plans_create:")
    )
    
    dp.callback_query.register(
        start_delete_plan,
        F.data.startswith("admin_tenant_bot_plan_delete:") & ~F.data.contains("_confirm:")
    )
    
    dp.callback_query.register(
        confirm_delete_plan,
        F.data.startswith("admin_tenant_bot_plan_delete_confirm:")
    )
    
    # Plan creation FSM handlers
    dp.message.register(
        process_plan_creation_step,
        StateFilter(AdminStates.creating_tenant_plan)
    )
    
    # Configuration handlers
    # Category handlers (must come before main menu to avoid conflicts)
    dp.callback_query.register(
        show_config_category,
        F.data.startswith("admin_tenant_bot_config_basic:") |
        F.data.startswith("admin_tenant_bot_config_support:") |
        F.data.startswith("admin_tenant_bot_config_notifications:") |
        F.data.startswith("admin_tenant_bot_config_subscription:") |
        F.data.startswith("admin_tenant_bot_config_pricing:") |
        F.data.startswith("admin_tenant_bot_config_ui:") |
        F.data.startswith("admin_tenant_bot_config_integrations:") |
        F.data.startswith("admin_tenant_bot_config_advanced:")
    )
    
    # Edit config handlers (must come before main menu)
    # Support both old and new shortened format
    dp.callback_query.register(
        start_edit_config,
        F.data.startswith("admin_tenant_bot_config_edit:") |
        F.data.startswith("cfg_edit:")
    )
    
    # Main config menu (matches admin_tenant_bot_config:{bot_id})
    dp.callback_query.register(
        show_bot_configuration_menu,
        F.data.startswith("admin_tenant_bot_config:")
    )
    
    # FSM handler for saving config values
    dp.message.register(
        save_config_value,
        StateFilter(AdminStates.editing_tenant_config_value)
    )
    
    # Analytics handlers
    dp.callback_query.register(
        show_bot_analytics,
        F.data.startswith("admin_tenant_bot_analytics:")
    )
    
    logger.info("✅ Tenant bots admin handlers registered")

