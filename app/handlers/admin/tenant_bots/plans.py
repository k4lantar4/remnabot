"""Subscription plans management handlers for tenant bots (AC8)."""
from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.crud.bot import get_bot_by_id
from app.database.crud.bot_plan import (
    get_plans,
    get_plan,
    create_plan,
    update_plan,
    delete_plan,
)
from app.localization.texts import get_texts
from app.utils.decorators import error_handler
from app.utils.permissions import admin_required
from app.states import AdminStates
from .common import logger


@admin_required
@error_handler
async def show_bot_plans(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show subscription plans management for a bot (AC8)."""
    texts = get_texts(db_user.language)
    
    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    # Get all plans for the bot (including inactive)
    plans = await get_plans(db, bot_id, active_only=False)
    
    if not plans:
        text = texts.t(
            "ADMIN_TENANT_BOT_PLANS_EMPTY",
            """📦 <b>Subscription Plans: {name}</b>

No subscription plans found.

Click "➕ Create Plan" to add a new plan."""
        ).format(name=bot.name)
    else:
        plans_text = []
        for plan in plans:
            status_icon = "✅" if plan.is_active else "❌"
            status_text = "Active" if plan.is_active else "Inactive"
            
            # Format traffic limit
            traffic_text = f"{plan.traffic_limit_gb} GB" if plan.traffic_limit_gb else "Unlimited"
            
            plan_line = texts.t(
                "ADMIN_TENANT_BOT_PLAN_ITEM",
                """{status_icon} <b>{name}</b>
Period: {period_days} days
Price: {price:,} Toman
Traffic: {traffic}
Devices: {devices}
Status: {status}"""
            ).format(
                status_icon=status_icon,
                name=plan.name,
                period_days=plan.period_days,
                price=plan.price_toman,
                traffic=traffic_text,
                devices=plan.device_limit,
                status=status_text
            )
            plans_text.append(plan_line)
        
        text = texts.t(
            "ADMIN_TENANT_BOT_PLANS",
            """📦 <b>Subscription Plans: {name}</b>

{plans}

Total: {count} plan(s)"""
        ).format(
            name=bot.name,
            plans="\n\n".join(plans_text),
            count=len(plans)
        )
    
    # Build keyboard with action buttons
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    keyboard_builder = InlineKeyboardBuilder()
    
    # Add plan buttons
    for plan in plans:
        keyboard_builder.button(
            text=f"{'✅' if plan.is_active else '❌'} {plan.name}",
            callback_data=f"admin_tenant_bot_plan_detail:{bot_id}:{plan.id}"
        )
    
    # Add create button
    keyboard_builder.button(
        text=texts.t("ADMIN_CREATE_PLAN", "➕ Create Plan"),
        callback_data=f"admin_tenant_bot_plans_create:{bot_id}"
    )
    
    # Add back button
    keyboard_builder.button(
        text=texts.BACK,
        callback_data=f"admin_tenant_bot_detail:{bot_id}"
    )
    
    keyboard_builder.adjust(1)  # One button per row
    
    await callback.message.edit_text(text, reply_markup=keyboard_builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def start_create_plan(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Start plan creation FSM flow."""
    texts = get_texts(db_user.language)
    
    try:
        bot_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_NOT_FOUND", "❌ Bot not found"),
            show_alert=True
        )
        return
    
    await state.update_data(bot_id=bot_id)
    await state.set_state(AdminStates.creating_tenant_plan)
    
    # Start with plan name
    text = texts.t(
        "ADMIN_TENANT_BOT_PLAN_CREATE_NAME",
        """📦 <b>Create New Subscription Plan</b>

Bot: <b>{name}</b>

Step 1/5: Enter plan name:
(Maximum 255 characters)

To cancel, send /cancel"""
    ).format(name=bot.name)
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                callback_data=f"admin_tenant_bot_plans:{bot_id}"
            )
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def process_plan_creation_step(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Process plan creation FSM steps - routes to appropriate handler based on current step."""
    texts = get_texts(db_user.language)
    
    data = await state.get_data()
    bot_id = data.get("bot_id")
    
    # Determine which step we're on
    if "plan_name" not in data:
        # Step 1: Plan name
        plan_name = message.text.strip()
        if not plan_name or len(plan_name) > 255:
            await message.answer(
                texts.t(
                    "ADMIN_TENANT_BOT_PLAN_NAME_INVALID",
                    "❌ Invalid plan name. Please enter a name (1-255 characters)."
                )
            )
            return
        
        await state.update_data(plan_name=plan_name)
        
        text = texts.t(
            "ADMIN_TENANT_BOT_PLAN_CREATE_PERIOD",
            """📦 <b>Create New Subscription Plan</b>

Plan name: <b>{name}</b>

Step 2/5: Enter subscription period in days:
(Common values: 14, 30, 60, 90, 180, 360)

To cancel, send /cancel"""
        ).format(name=plan_name)
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                    callback_data=f"admin_tenant_bot_plans:{bot_id}"
                )
            ]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    elif "period_days" not in data:
        # Step 2: Period
        try:
            period_days = int(message.text.strip())
            if period_days <= 0:
                raise ValueError
        except ValueError:
            await message.answer(
                texts.t(
                    "ADMIN_TENANT_BOT_PLAN_PERIOD_INVALID",
                    "❌ Invalid period. Please enter a positive number of days."
                )
            )
            return
        
        plan_name = data.get("plan_name")
        await state.update_data(period_days=period_days)
        
        text = texts.t(
            "ADMIN_TENANT_BOT_PLAN_CREATE_PRICE",
            """📦 <b>Create New Subscription Plan</b>

Plan name: <b>{name}</b>
Period: <b>{period} days</b>

Step 3/5: Enter price in Toman:
(Enter a positive number)

To cancel, send /cancel"""
        ).format(name=plan_name, period=period_days)
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                    callback_data=f"admin_tenant_bot_plans:{bot_id}"
                )
            ]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    elif "price_toman" not in data:
        # Step 3: Price
        try:
            price_toman = int(message.text.strip().replace(",", ""))
            if price_toman <= 0:
                raise ValueError
        except ValueError:
            await message.answer(
                texts.t(
                    "ADMIN_TENANT_BOT_PLAN_PRICE_INVALID",
                    "❌ Invalid price. Please enter a positive number in Toman."
                )
            )
            return
        
        plan_name = data.get("plan_name")
        period_days = data.get("period_days")
        await state.update_data(price_toman=price_toman)
        
        text = texts.t(
            "ADMIN_TENANT_BOT_PLAN_CREATE_TRAFFIC",
            """📦 <b>Create New Subscription Plan</b>

Plan name: <b>{name}</b>
Period: <b>{period} days</b>
Price: <b>{price:,} Toman</b>

Step 4/5: Enter traffic limit in GB:
(Enter 0 for unlimited)

To cancel, send /cancel"""
        ).format(name=plan_name, period=period_days, price=price_toman)
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                    callback_data=f"admin_tenant_bot_plans:{bot_id}"
                )
            ]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    elif "traffic_limit_gb" not in data:
        # Step 4: Traffic
        try:
            traffic_limit_gb = int(message.text.strip())
            if traffic_limit_gb < 0:
                raise ValueError
        except ValueError:
            await message.answer(
                texts.t(
                    "ADMIN_TENANT_BOT_PLAN_TRAFFIC_INVALID",
                    "❌ Invalid traffic limit. Please enter a non-negative number (0 for unlimited)."
                )
            )
            return
        
        plan_name = data.get("plan_name")
        period_days = data.get("period_days")
        price_toman = data.get("price_toman")
        await state.update_data(traffic_limit_gb=traffic_limit_gb)
        
        text = texts.t(
            "ADMIN_TENANT_BOT_PLAN_CREATE_DEVICES",
            """📦 <b>Create New Subscription Plan</b>

Plan name: <b>{name}</b>
Period: <b>{period} days</b>
Price: <b>{price:,} Toman</b>
Traffic: <b>{traffic} GB</b> {unlimited}

Step 5/5: Enter device limit:
(Enter a positive number)

To cancel, send /cancel"""
        ).format(
            name=plan_name,
            period=period_days,
            price=price_toman,
            traffic=traffic_limit_gb if traffic_limit_gb > 0 else "Unlimited",
            unlimited="(unlimited)" if traffic_limit_gb == 0 else ""
        )
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                    callback_data=f"admin_tenant_bot_plans:{bot_id}"
                )
            ]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
    else:
        # Step 5: Devices - final step, create plan
        try:
            device_limit = int(message.text.strip())
            if device_limit <= 0:
                raise ValueError
        except ValueError:
            await message.answer(
                texts.t(
                    "ADMIN_TENANT_BOT_PLAN_DEVICES_INVALID",
                    "❌ Invalid device limit. Please enter a positive number."
                )
            )
            return
        
        plan_name = data.get("plan_name")
        period_days = data.get("period_days")
        price_toman = data.get("price_toman")
        traffic_limit_gb = data.get("traffic_limit_gb")
        
        # Get current plans to determine sort_order
        existing_plans = await get_plans(db, bot_id, active_only=False)
        sort_order = len(existing_plans)
        
        # Create the plan
        try:
            plan = await create_plan(
                db=db,
                bot_id=bot_id,
                name=plan_name,
                period_days=period_days,
                price_toman=price_toman,
                traffic_limit_gb=traffic_limit_gb if traffic_limit_gb > 0 else None,
                device_limit=device_limit,
                sort_order=sort_order,
                is_active=True
            )
            
            text = texts.t(
                "ADMIN_TENANT_BOT_PLAN_CREATED",
                """✅ <b>Plan Created Successfully</b>

Plan: <b>{name}</b>
Period: {period} days
Price: {price:,} Toman
Traffic: {traffic}
Devices: {devices}

Click below to return to plans:"""
            ).format(
                name=plan.name,
                period=plan.period_days,
                price=plan.price_toman,
                traffic=f"{plan.traffic_limit_gb} GB" if plan.traffic_limit_gb else "Unlimited",
                devices=plan.device_limit
            )
            
            keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_VIEW_PLANS", "📦 View Plans"),
                        callback_data=f"admin_tenant_bot_plans:{bot_id}"
                    )
                ]
            ])
            
            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
            await state.clear()
            
        except Exception as e:
            logger.error(f"Error creating plan: {e}", exc_info=True)
            await message.answer(
                texts.t(
                    "ADMIN_TENANT_BOT_PLAN_CREATE_ERROR",
                    "❌ Error creating plan. Please try again."
                )
            )




@admin_required
@error_handler
async def show_plan_detail(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Show plan detail with edit/delete options."""
    texts = get_texts(db_user.language)
    
    try:
        parts = callback.data.split(":")
        bot_id = int(parts[1])
        plan_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    plan = await get_plan(db, plan_id)
    if not plan or plan.bot_id != bot_id:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_PLAN_NOT_FOUND", "❌ Plan not found"),
            show_alert=True
        )
        return
    
    status_icon = "✅" if plan.is_active else "❌"
    status_text = "Active" if plan.is_active else "Inactive"
    traffic_text = f"{plan.traffic_limit_gb} GB" if plan.traffic_limit_gb else "Unlimited"
    
    text = texts.t(
        "ADMIN_TENANT_BOT_PLAN_DETAIL",
        """📦 <b>Plan Details</b>

{status_icon} <b>{name}</b>

Period: {period} days
Price: {price:,} Toman
Traffic: {traffic}
Devices: {devices}
Status: {status}

Select an action:"""
    ).format(
        status_icon=status_icon,
        name=plan.name,
        period=plan.period_days,
        price=plan.price_toman,
        traffic=traffic_text,
        devices=plan.device_limit,
        status=status_text
    )
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    keyboard_builder = InlineKeyboardBuilder()
    
    # Toggle active status
    toggle_text = texts.t("ADMIN_DEACTIVATE", "❌ Deactivate") if plan.is_active else texts.t("ADMIN_ACTIVATE", "✅ Activate")
    keyboard_builder.button(
        text=toggle_text,
        callback_data=f"admin_tenant_bot_plan_toggle:{bot_id}:{plan_id}"
    )
    
    # Delete button
    keyboard_builder.button(
        text=texts.t("ADMIN_DELETE", "🗑️ Delete"),
        callback_data=f"admin_tenant_bot_plan_delete:{bot_id}:{plan_id}"
    )
    
    # Back button
    keyboard_builder.button(
        text=texts.BACK,
        callback_data=f"admin_tenant_bot_plans:{bot_id}"
    )
    
    keyboard_builder.adjust(1)
    
    await callback.message.edit_text(text, reply_markup=keyboard_builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def toggle_plan_status(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Toggle plan active status."""
    texts = get_texts(db_user.language)
    
    try:
        parts = callback.data.split(":")
        bot_id = int(parts[1])
        plan_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    plan = await get_plan(db, plan_id)
    if not plan or plan.bot_id != bot_id:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_PLAN_NOT_FOUND", "❌ Plan not found"),
            show_alert=True
        )
        return
    
    # Toggle status
    new_status = not plan.is_active
    await update_plan(db, plan_id, is_active=new_status)
    
    status_text = "activated" if new_status else "deactivated"
    await callback.answer(
        texts.t(
            "ADMIN_TENANT_BOT_PLAN_STATUS_TOGGLED",
            f"✅ Plan {status_text}"
        ),
        show_alert=False
    )
    
    # Refresh plan detail view
    callback.data = f"admin_tenant_bot_plan_detail:{bot_id}:{plan_id}"
    await show_plan_detail(callback, db_user, db)


@admin_required
@error_handler
async def start_delete_plan(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Start plan deletion with confirmation."""
    texts = get_texts(db_user.language)
    
    try:
        parts = callback.data.split(":")
        bot_id = int(parts[1])
        plan_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    plan = await get_plan(db, plan_id)
    if not plan or plan.bot_id != bot_id:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_PLAN_NOT_FOUND", "❌ Plan not found"),
            show_alert=True
        )
        return
    
    text = texts.t(
        "ADMIN_TENANT_BOT_PLAN_DELETE_CONFIRM",
        """⚠️ <b>Delete Subscription Plan</b>

Plan: <b>{name}</b>
Period: {period} days
Price: {price:,} Toman

<b>Warning:</b> This action cannot be undone. The plan will be permanently deleted.

Are you sure you want to delete this plan?"""
    ).format(
        name=plan.name,
        period=plan.period_days,
        price=plan.price_toman
    )
    
    keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CONFIRM_DELETE", "✅ Yes, Delete"),
                callback_data=f"admin_tenant_bot_plan_delete_confirm:{bot_id}:{plan_id}"
            ),
            types.InlineKeyboardButton(
                text=texts.t("ADMIN_CANCEL", "❌ Cancel"),
                callback_data=f"admin_tenant_bot_plans:{bot_id}"
            )
        ]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@admin_required
@error_handler
async def confirm_delete_plan(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
):
    """Confirm and delete plan."""
    texts = get_texts(db_user.language)
    
    try:
        parts = callback.data.split(":")
        bot_id = int(parts[1])
        plan_id = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer(
            texts.t("ADMIN_INVALID_REQUEST", "❌ Invalid request"),
            show_alert=True
        )
        return
    
    plan = await get_plan(db, plan_id)
    if not plan or plan.bot_id != bot_id:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_PLAN_NOT_FOUND", "❌ Plan not found"),
            show_alert=True
        )
        return
    
    plan_name = plan.name
    
    # Delete the plan
    success = await delete_plan(db, plan_id)
    
    if success:
        text = texts.t(
            "ADMIN_TENANT_BOT_PLAN_DELETED",
            """✅ <b>Plan Deleted</b>

Plan <b>{name}</b> has been deleted successfully.

Click below to return to plans:"""
        ).format(name=plan_name)
        
        keyboard = types.InlineKeyboardMarkup(inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_VIEW_PLANS", "📦 View Plans"),
                    callback_data=f"admin_tenant_bot_plans:{bot_id}"
                )
            ]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_PLAN_DELETE_SUCCESS", "✅ Plan deleted"),
            show_alert=False
        )
    else:
        await callback.answer(
            texts.t("ADMIN_TENANT_BOT_PLAN_DELETE_ERROR", "❌ Error deleting plan"),
            show_alert=True
        )
