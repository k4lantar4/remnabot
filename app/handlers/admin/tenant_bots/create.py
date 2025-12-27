"""Bot creation handlers."""

from aiogram import types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.database.crud.bot import create_bot, get_bot_by_token, get_bot_by_id
from app.localization.texts import get_texts
from app.utils.decorators import error_handler, admin_required
from app.keyboards.inline import get_back_keyboard
from app.states import AdminStates
from .common import logger


@admin_required
@error_handler
async def start_create_bot(
    callback: types.CallbackQuery,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Start bot creation flow."""
    texts = get_texts(db_user.language)

    text = texts.t(
        "ADMIN_TENANT_BOT_CREATE_START",
        """🤖 <b>Create New Tenant Bot</b>

Please enter the bot name:
(Maximum 255 characters)""",
    )

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CANCEL", "❌ Cancel"), callback_data="admin_tenant_bots_menu"
                )
            ]
        ]
    )

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(AdminStates.creating_tenant_bot_name)
    await callback.answer()


@admin_required
@error_handler
async def process_bot_name(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Process bot name input."""
    texts = get_texts(db_user.language)

    bot_name = message.text.strip()
    if not bot_name or len(bot_name) > 255:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_NAME_INVALID", "❌ Invalid bot name. Please enter a name (max 255 characters).")
        )
        return

    await state.update_data(bot_name=bot_name)

    text = texts.t(
        "ADMIN_TENANT_BOT_CREATE_TOKEN",
        """✅ Bot name: <b>{name}</b>

Now please enter the Telegram Bot Token:
(Get it from @BotFather)""",
    ).format(name=bot_name)

    keyboard = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text=texts.t("ADMIN_CANCEL", "❌ Cancel"), callback_data="admin_tenant_bots_menu"
                )
            ]
        ]
    )

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(AdminStates.creating_tenant_bot_token)


@admin_required
@error_handler
async def process_bot_token(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
):
    """Process bot token and create bot."""
    texts = get_texts(db_user.language)

    token = message.text.strip()
    if not token or ":" not in token:
        await message.answer(
            texts.t(
                "ADMIN_TENANT_BOT_TOKEN_INVALID", "❌ Invalid token format. Please enter a valid Telegram Bot Token."
            )
        )
        return

    data = await state.get_data()
    bot_name = data.get("bot_name")

    if not bot_name:
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_ERROR", "❌ Error: Bot name not found. Please start over."),
            reply_markup=get_back_keyboard(db_user.language),
        )
        await state.clear()
        return

    try:
        # Check if token already exists
        existing = await get_bot_by_token(db, token)
        if existing:
            await message.answer(
                texts.t("ADMIN_TENANT_BOT_TOKEN_EXISTS", "❌ A bot with this token already exists."),
                reply_markup=get_back_keyboard(db_user.language),
            )
            await state.clear()
            return

        # Create bot
        bot, api_token = await create_bot(
            db=db, name=bot_name, telegram_bot_token=token, is_master=False, is_active=True, created_by=db_user.id
        )

        # Initialize and start the new bot immediately
        try:
            from app.bot import initialize_single_bot, start_bot_polling, setup_bot_webhook

            # Get fresh bot config from database
            bot_config = await get_bot_by_id(db, bot.id)
            if bot_config:
                # Initialize the bot
                result = await initialize_single_bot(bot_config)
                if result:
                    bot_instance, dp_instance = result

                    # Start polling if enabled
                    await start_bot_polling(bot.id, bot_instance, dp_instance)

                    # Setup webhook if enabled
                    await setup_bot_webhook(bot.id, bot_instance, bot_config.telegram_bot_token)

                    logger.info(f"✅ Bot {bot.id} ({bot.name}) initialized and started successfully")
                else:
                    logger.warning(f"⚠️ Bot {bot.id} created but initialization failed")
            else:
                logger.error(f"❌ Bot {bot.id} not found in database after creation")
        except Exception as e:
            logger.error(f"❌ Error initializing new bot {bot.id}: {e}", exc_info=True)
            # Continue - bot is created in DB, can be initialized on restart

        text = texts.t(
            "ADMIN_TENANT_BOT_CREATED",
            """✅ <b>Bot Created Successfully!</b>

<b>Name:</b> {name}
<b>ID:</b> {id}
<b>Status:</b> ✅ Active

<b>API Token:</b>
<code>{api_token}</code>

⚠️ <b>IMPORTANT:</b> Save this API token! It will not be shown again.""",
        ).format(name=bot.name, id=bot.id, api_token=api_token)

        keyboard = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_TENANT_BOT_VIEW", "👁️ View Bot"),
                        callback_data=f"admin_tenant_bot_detail:{bot.id}",
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text=texts.t("ADMIN_TENANT_BOTS_MENU", "🏠 Bots Menu"), callback_data="admin_tenant_bots_menu"
                    )
                ],
            ]
        )

        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await state.clear()

    except Exception as e:
        logger.error(f"Error creating bot: {e}", exc_info=True)
        await message.answer(
            texts.t("ADMIN_TENANT_BOT_CREATE_ERROR", "❌ Error creating bot. Please try again."),
            reply_markup=get_back_keyboard(db_user.language),
        )
        await state.clear()
