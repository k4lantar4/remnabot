"""Feature flags management handlers for tenant bots."""

from aiogram import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text as sql_text

from app.database.models import User
from app.database.crud.bot import get_bot_by_id
from app.localization.texts import get_texts
from app.utils.decorators import error_handler
from app.utils.decorators import admin_required
from app.services.bot_config_service import BotConfigService
from .common import logger


@admin_required
@error_handler
async def show_bot_feature_flags(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show feature flags management for a bot (AC6)."""
    texts = get_texts(db_user.language)

    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    # Define feature categories as per AC6
    feature_categories = {
        "Payment Gateways": [
            ("yookassa", "YooKassa"),
            ("cryptobot", "CryptoBot"),
            ("pal24", "Pal24"),
            ("card_to_card", "Card-to-Card"),
            ("zarinpal", "Zarinpal"),
            ("telegram_stars", "Telegram Stars"),
            ("heleket", "Heleket"),
            ("mulenpay", "MulenPay"),
            ("wata", "WATA"),
            ("tribute", "Tribute"),
        ],
        "Subscription Features": [
            ("trial", "Trial"),
            ("auto_renewal", "Auto Renewal"),
            ("simple_purchase", "Simple Purchase"),
        ],
        "Marketing Features": [
            ("referral_program", "Referral Program"),
            ("polls", "Polls"),
        ],
        "Support Features": [
            ("support_tickets", "Support Tickets"),
        ],
        "Integrations": [
            ("server_status", "Server Status"),
            ("monitoring", "Monitoring"),
        ],
    }

    # Get current plan info (if tenant_subscriptions table exists)
    plan_name = None
    try:
        plan_result = await db.execute(
            sql_text("""
                SELECT tsp.display_name
                FROM tenant_subscriptions ts
                LEFT JOIN tenant_subscription_plans tsp ON tsp.id = ts.plan_tier_id
                WHERE ts.bot_id = :bot_id AND ts.status = 'active'
                LIMIT 1
            """),
            {"bot_id": bot_id},
        )
        plan_row = plan_result.fetchone()
        if plan_row and plan_row[0]:
            plan_name = plan_row[0]
    except Exception:
        # Table doesn't exist yet, skip plan check
        pass

    # Build feature flags display
    text = texts.t(
        "ADMIN_TENANT_BOT_FEATURES",
        """🎛️ <b>Feature Flags: {name}</b>

<b>Current Plan:</b> {plan_name}

Select a category to view features:""",
    ).format(name=bot.name, plan_name=plan_name or "Not assigned")

    keyboard_buttons = []

    # Add category buttons
    for category_name, features in feature_categories.items():
        # Count enabled features in this category
        enabled_count = 0
        for feature_key, _ in features:
            is_enabled = await BotConfigService.is_feature_enabled(db, bot_id, feature_key)
            if is_enabled:
                enabled_count += 1

        keyboard_buttons.append(
            [
                types.InlineKeyboardButton(
                    text=f"{category_name} ({enabled_count}/{len(features)})",
                    callback_data=f"admin_tenant_bot_features_category:{bot_id}:{category_name}",
                )
            ]
        )

    # Back button
    keyboard_buttons.append(
        [types.InlineKeyboardButton(text=texts.BACK, callback_data=f"admin_tenant_bot_detail:{bot_id}")]
    )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def show_bot_feature_flags_category(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show feature flags for a specific category."""
    texts = get_texts(db_user.language)

    try:
        parts = callback.data.split(":")
        bot_id = int(parts[1])
        category_name = ":".join(parts[2:])  # Handle category names with colons
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    # Define feature categories
    feature_categories = {
        "Payment Gateways": [
            ("yookassa", "YooKassa"),
            ("cryptobot", "CryptoBot"),
            ("pal24", "Pal24"),
            ("card_to_card", "Card-to-Card"),
            ("zarinpal", "Zarinpal"),
            ("telegram_stars", "Telegram Stars"),
            ("heleket", "Heleket"),
            ("mulenpay", "MulenPay"),
            ("wata", "WATA"),
            ("tribute", "Tribute"),
        ],
        "Subscription Features": [
            ("trial", "Trial"),
            ("auto_renewal", "Auto Renewal"),
            ("simple_purchase", "Simple Purchase"),
        ],
        "Marketing Features": [
            ("referral_program", "Referral Program"),
            ("polls", "Polls"),
        ],
        "Support Features": [
            ("support_tickets", "Support Tickets"),
        ],
        "Integrations": [
            ("server_status", "Server Status"),
            ("monitoring", "Monitoring"),
        ],
    }

    features = feature_categories.get(category_name, [])
    if not features:
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid category"), show_alert=True)
        return

    # Get current plan and check restrictions
    plan_name = None
    plan_restrictions = {}  # feature_key -> required_plan
    try:
        plan_result = await db.execute(
            sql_text("""
                SELECT tsp.id, tsp.name, tsp.display_name
                FROM tenant_subscriptions ts
                LEFT JOIN tenant_subscription_plans tsp ON tsp.id = ts.plan_tier_id
                WHERE ts.bot_id = :bot_id AND ts.status = 'active'
                LIMIT 1
            """),
            {"bot_id": bot_id},
        )
        plan_row = plan_result.fetchone()
        if plan_row and plan_row[0]:
            plan_id, plan_key, plan_name = plan_row

            # Check which features are granted by this plan
            grants_result = await db.execute(
                sql_text("""
                    SELECT feature_key, enabled
                    FROM plan_feature_grants
                    WHERE plan_tier_id = :plan_id
                """),
                {"plan_id": plan_id},
            )
            for row in grants_result.fetchall():
                feature_key, enabled = row
                if not enabled:
                    plan_restrictions[feature_key] = plan_name or "Higher Plan"
    except Exception:
        # Tables don't exist yet, skip plan restrictions
        pass

    # Build feature list
    text = texts.t(
        "ADMIN_TENANT_BOT_FEATURES_CATEGORY",
        """🎛️ <b>{category}: {name}</b>

<b>Current Plan:</b> {plan_name}

<b>Features:</b>""",
    ).format(category=category_name, name=bot.name, plan_name=plan_name or "Not assigned")

    keyboard_buttons = []

    for feature_key, feature_display in features:
        is_enabled = await BotConfigService.is_feature_enabled(db, bot_id, feature_key)
        status_icon = "✅" if is_enabled else "❌"

        # Check if feature requires a higher plan
        requires_plan = plan_restrictions.get(feature_key)
        restriction_text = ""
        if requires_plan and not is_enabled:
            restriction_text = f" (Requires {requires_plan})"

        text += f"\n{status_icon} <b>{feature_display}</b>{restriction_text}"

        # Add toggle button (master admin can always override)
        keyboard_buttons.append(
            [
                types.InlineKeyboardButton(
                    text=f"{'🔴 Disable' if is_enabled else '🟢 Enable'} {feature_display}",
                    callback_data=f"admin_tenant_bot_toggle_feature:{bot_id}:{feature_key}",
                )
            ]
        )

    # Back button
    keyboard_buttons.append(
        [types.InlineKeyboardButton(text=texts.BACK, callback_data=f"admin_tenant_bot_features:{bot_id}")]
    )

    keyboard = types.InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def toggle_feature_flag(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Toggle a feature flag for a bot (AC6)."""
    texts = get_texts(db_user.language)

    try:
        parts = callback.data.split(":")
        bot_id = int(parts[1])
        feature_key = parts[2]
    except (ValueError, IndexError):
        await callback.answer(texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"), show_alert=True)
        return

    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"), show_alert=True)
        return

    # Check plan restrictions (master admin can override)
    plan_name = None
    feature_allowed = True
    try:
        plan_result = await db.execute(
            sql_text("""
                SELECT tsp.id, tsp.name, tsp.display_name
                FROM tenant_subscriptions ts
                LEFT JOIN tenant_subscription_plans tsp ON tsp.id = ts.plan_tier_id
                WHERE ts.bot_id = :bot_id AND ts.status = 'active'
                LIMIT 1
            """),
            {"bot_id": bot_id},
        )
        plan_row = plan_result.fetchone()
        if plan_row and plan_row[0]:
            plan_id, plan_key, plan_name = plan_row

            # Check if feature is granted by plan
            grant_result = await db.execute(
                sql_text("""
                    SELECT enabled
                    FROM plan_feature_grants
                    WHERE plan_tier_id = :plan_id AND feature_key = :feature_key
                """),
                {"plan_id": plan_id, "feature_key": feature_key},
            )
            grant_row = grant_result.fetchone()
            if grant_row:
                feature_allowed = grant_row[0]
            # If no grant record exists, feature is not allowed by plan
            # But master admin can override
    except Exception:
        # Tables don't exist, allow toggle (master admin override)
        feature_allowed = True

    # Get current value
    current_value = await BotConfigService.is_feature_enabled(db, bot_id, feature_key)
    new_value = not current_value

    # If enabling and plan doesn't allow it, warn but allow (master admin override)
    if new_value and not feature_allowed and plan_name:
        # Master admin can override, but show warning
        await callback.answer(
            texts.t(
                "ADMIN_TENANT_BOT_FEATURE_PLAN_RESTRICTION",
                f"⚠️ This feature requires a higher plan. Overriding as master admin.",
            ),
            show_alert=True,
        )

    # Toggle feature using BotConfigService (auto-commits with default commit=True)
    await BotConfigService.set_feature_enabled(db, bot_id, feature_key, new_value)

    status_text = "enabled" if new_value else "disabled"
    await callback.answer(f"✅ Feature {status_text}")

    # Refresh the category view
    # Find which category this feature belongs to
    feature_categories = {
        "Payment Gateways": [
            ("yookassa", "YooKassa"),
            ("cryptobot", "CryptoBot"),
            ("pal24", "Pal24"),
            ("card_to_card", "Card-to-Card"),
            ("zarinpal", "Zarinpal"),
            ("telegram_stars", "Telegram Stars"),
            ("heleket", "Heleket"),
            ("mulenpay", "MulenPay"),
            ("wata", "WATA"),
            ("tribute", "Tribute"),
        ],
        "Subscription Features": [
            ("trial", "Trial"),
            ("auto_renewal", "Auto Renewal"),
            ("simple_purchase", "Simple Purchase"),
        ],
        "Marketing Features": [
            ("referral_program", "Referral Program"),
            ("polls", "Polls"),
        ],
        "Support Features": [
            ("support_tickets", "Support Tickets"),
        ],
        "Integrations": [
            ("server_status", "Server Status"),
            ("monitoring", "Monitoring"),
        ],
    }

    # Find category for this feature
    category_name = None
    for cat_name, features in feature_categories.items():
        if any(fk == feature_key for fk, _ in features):
            category_name = cat_name
            break

    if category_name:
        # Update callback data to show category
        callback.data = f"admin_tenant_bot_features_category:{bot_id}:{category_name}"
        await show_bot_feature_flags_category(callback, db_user, db)
    else:
        # Fallback to main features view
        await show_bot_feature_flags(callback, db_user, db)
