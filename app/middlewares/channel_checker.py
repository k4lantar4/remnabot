import logging
from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware, Bot, types
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import TelegramObject, Update, Message, CallbackQuery
from aiogram.enums import ChatMemberStatus

from app.config import settings
from app.database.database import get_db
from app.database.crud.campaign import get_campaign_by_start_parameter
from app.database.crud.subscription import deactivate_subscription
from app.database.crud.user import get_user_by_telegram_id
from app.database.models import SubscriptionStatus
from app.keyboards.inline import get_channel_sub_keyboard
from app.localization.loader import DEFAULT_LANGUAGE
from app.localization.texts import get_texts
from app.utils.check_reg_process import is_registration_process
from app.services.subscription_service import SubscriptionService
from app.services.admin_notification_service import AdminNotificationService

logger = logging.getLogger(__name__)


class ChannelCheckerMiddleware(BaseMiddleware):
    def __init__(self):
        self.BAD_MEMBER_STATUS = (
            ChatMemberStatus.LEFT,
            ChatMemberStatus.KICKED,
            ChatMemberStatus.RESTRICTED
        )
        self.GOOD_MEMBER_STATUS = (
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR
        )
        logger.info("🔧 ChannelCheckerMiddleware initialized")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        telegram_id = None
        if isinstance(event, (Message, CallbackQuery)):
            telegram_id = event.from_user.id
        elif isinstance(event, Update):
            if event.message:
                telegram_id = event.message.from_user.id
            elif event.callback_query:
                telegram_id = event.callback_query.from_user.id

        if telegram_id is None:
            logger.debug("❌ telegram_id not found, skipping")
            return await handler(event, data)


        # Allow admins to skip subscription check to avoid blocking
        # admin panel functionality even without subscription. Important to do
        # this before accessing state to avoid unnecessary operations.
        if settings.is_admin(telegram_id):
            logger.debug(
                "✅ User %s is an administrator — skipping subscription check",
                telegram_id,
            )
            return await handler(event, data)

        state: FSMContext = data.get('state')
        current_state = None

        if state:
            current_state = await state.get_state()


        is_reg_process = is_registration_process(event, current_state)

        if is_reg_process:
            logger.debug("✅ Event allowed (registration process), skipping check")
            return await handler(event, data)

        bot: Bot = data["bot"]

        channel_id = settings.CHANNEL_SUB_ID

        if not channel_id:
            logger.warning("⚠️ CHANNEL_SUB_ID not set, skipping check")
            return await handler(event, data)

        is_required = settings.CHANNEL_IS_REQUIRED_SUB

        if not is_required:
            logger.debug("⚠️ Required subscription disabled, skipping check")
            return await handler(event, data)

        channel_link = self._normalize_channel_link(settings.CHANNEL_LINK, channel_id)

        if not channel_link:
            logger.warning(
                "⚠️ CHANNEL_LINK not set or invalid, subscription button will be hidden"
            )

        try:
            member = await bot.get_chat_member(chat_id=channel_id, user_id=telegram_id)

            if member.status in self.GOOD_MEMBER_STATUS:
                return await handler(event, data)
            elif member.status in self.BAD_MEMBER_STATUS:
                logger.info(f"❌ User {telegram_id} not subscribed to channel (status: {member.status})")

                if telegram_id:
                    await self._deactivate_trial_subscription(telegram_id)

                await self._capture_start_payload(state, event, bot)

                if isinstance(event, CallbackQuery) and event.data == "sub_channel_check":
                    user = None
                    if isinstance(event, CallbackQuery):
                        user = event.from_user
                    language = DEFAULT_LANGUAGE
                    if user and user.language_code:
                        language = user.language_code.split('-')[0]
                    texts = get_texts(language)
                    message = texts.get(
                        "CHANNEL_NOT_SUBSCRIBED",
                        "❌ You haven't subscribed to the channel yet! Subscribe and try again."
                    )
                    await event.answer(message, show_alert=True)
                    return

                return await self._deny_message(event, bot, channel_link, channel_id)
            else:
                logger.warning(f"⚠️ Unexpected user status {telegram_id}: {member.status}")
                await self._capture_start_payload(state, event, bot)
                return await self._deny_message(event, bot, channel_link, channel_id)

        except TelegramForbiddenError as e:
            logger.error(f"❌ Bot blocked in channel {channel_id}: {e}")
            await self._capture_start_payload(state, event, bot)
            return await self._deny_message(event, bot, channel_link, channel_id)
        except TelegramBadRequest as e:
            if "chat not found" in str(e).lower():
                logger.error(f"❌ Channel {channel_id} not found: {e}")
            elif "user not found" in str(e).lower():
                logger.error(f"❌ User {telegram_id} not found: {e}")
            else:
                logger.error(f"❌ Error requesting channel {channel_id}: {e}")
            await self._capture_start_payload(state, event, bot)
            return await self._deny_message(event, bot, channel_link, channel_id)
        except Exception as e:
            logger.error(f"❌ Unexpected error checking subscription: {e}")
            return await handler(event, data)

    @staticmethod
    def _normalize_channel_link(channel_link: Optional[str], channel_id: Optional[str]) -> Optional[str]:
        link = (channel_link or "").strip()

        if link.startswith("@"):  # raw username
            return f"https://t.me/{link.lstrip('@')}"

        if link and not link.lower().startswith(("http://", "https://", "tg://")):
            return f"https://{link}"

        if link:
            return link

        if channel_id and str(channel_id).startswith("@"):
            return f"https://t.me/{str(channel_id).lstrip('@')}"

        return None

    async def _capture_start_payload(
        self,
        state: Optional[FSMContext],
        event: TelegramObject,
        bot: Optional[Bot] = None,
    ) -> None:
        if not state:
            return

        message: Optional[Message] = None
        if isinstance(event, Message):
            message = event
        elif isinstance(event, CallbackQuery):
            message = event.message
        elif isinstance(event, Update):
            message = event.message

        if not message or not message.text:
            return

        text = message.text.strip()
        if not text.startswith("/start"):
            return

        parts = text.split(maxsplit=1)
        if len(parts) < 2 or not parts[1]:
            return

        payload = parts[1]

        data = await state.get_data() or {}
        if data.get("pending_start_payload") != payload:
            data["pending_start_payload"] = payload
            await state.set_data(data)
            logger.debug("💾 Saved start payload %s for later processing", payload)

        if bot and message.from_user:
            await self._try_send_campaign_visit_notification(
                bot,
                message.from_user,
                state,
                payload,
            )

    async def _try_send_campaign_visit_notification(
        self,
        bot: Bot,
        telegram_user: types.User,
        state: FSMContext,
        payload: str,
    ) -> None:
        try:
            data = await state.get_data() or {}
        except Exception as error:
            logger.error(
                "❌ Failed to get state data for campaign notification %s: %s",
                payload,
                error,
            )
            return

        if data.get("campaign_notification_sent"):
            return

        async for db in get_db():
            try:
                campaign = await get_campaign_by_start_parameter(
                    db,
                    payload,
                    only_active=True,
                )
                if not campaign:
                    break

                user = await get_user_by_telegram_id(db, telegram_user.id)

                notification_service = AdminNotificationService(bot)
                sent = await notification_service.send_campaign_link_visit_notification(
                    db,
                    telegram_user,
                    campaign,
                    user,
                )
                if sent:
                    await state.update_data(campaign_notification_sent=True)
                break
            except Exception as error:
                logger.error(
                    "❌ Error sending campaign visit notification %s: %s",
                    payload,
                    error,
                )
            finally:
                break

    async def _deactivate_trial_subscription(self, telegram_id: int) -> None:
        async for db in get_db():
            try:
                user = await get_user_by_telegram_id(db, telegram_id)
                if not user or not user.subscription:
                    logger.debug(
                        "⚠️ User %s not found or has no subscription — skipping deactivation",
                        telegram_id,
                    )
                    break

                subscription = user.subscription
                if (not subscription.is_trial or
                        subscription.status != SubscriptionStatus.ACTIVE.value):
                    logger.debug(
                        "ℹ️ User %s subscription does not require deactivation (trial=%s, status=%s)",
                        telegram_id,
                        subscription.is_trial,
                        subscription.status,
                    )
                    break

                await deactivate_subscription(db, subscription)
                logger.info(
                    "🚫 Trial subscription for user %s disabled after channel unsubscription",
                    telegram_id,
                )

                if user.remnawave_uuid:
                    service = SubscriptionService()
                    try:
                        await service.disable_remnawave_user(user.remnawave_uuid)
                    except Exception as api_error:
                        logger.error(
                            "❌ Failed to disable RemnaWave user %s: %s",
                            user.remnawave_uuid,
                            api_error,
                        )
            except Exception as db_error:
                logger.error(
                    "❌ Error deactivating subscription for user %s after unsubscription: %s",
                    telegram_id,
                    db_error,
                )
            finally:
                break

    @staticmethod
    async def _deny_message(
        event: TelegramObject,
        bot: Bot,
        channel_link: Optional[str],
        channel_id: Optional[str],
    ):
        logger.debug("🚫 Sending subscription required message")

        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = getattr(event, "from_user", None)
        elif isinstance(event, Update):
            if event.message and event.message.from_user:
                user = event.message.from_user
            elif event.callback_query and event.callback_query.from_user:
                user = event.callback_query.from_user

        language = DEFAULT_LANGUAGE
        if user and user.language_code:
            language = user.language_code.split('-')[0]

        texts = get_texts(language)
        channel_sub_kb = get_channel_sub_keyboard(channel_link, language=language)
        text = texts.get(
            "CHANNEL_REQUIRED_TEXT",
            "🔒 To use the bot, please subscribe to our news channel to receive notifications about new features and bot updates. Thank you!",
        )

        if not channel_link and channel_id:
            channel_hint = None

            if str(channel_id).startswith("@"):  # username-based channel id
                channel_hint = f"@{str(channel_id).lstrip('@')}"

            if channel_hint:
                text = f"{text}\n\n{channel_hint}"

        try:
            if isinstance(event, Message):
                return await event.answer(text, reply_markup=channel_sub_kb)
            elif isinstance(event, CallbackQuery):
                try:
                    return await event.message.edit_text(text, reply_markup=channel_sub_kb)
                except TelegramBadRequest as e:
                    if "message is not modified" in str(e).lower():
                        logger.debug("ℹ️ Message already contains subscription check text, skipping edit")
                        return await event.answer(text, show_alert=True)
                    raise
            elif isinstance(event, Update) and event.message:
                return await bot.send_message(event.message.chat.id, text, reply_markup=channel_sub_kb)
        except Exception as e:
            logger.error(f"❌ Error sending subscription message: {e}")
