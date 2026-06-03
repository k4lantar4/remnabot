import structlog
from aiogram import Dispatcher, F, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.localization.texts import get_texts
from app.services.version_service import version_service
from app.utils.decorators import admin_required, error_handler


logger = structlog.get_logger(__name__)


def get_updates_keyboard(language: str = 'ru') -> InlineKeyboardMarkup:
    texts = get_texts(language)
    buttons = [
        [
            InlineKeyboardButton(
                text=texts.t('ADMIN_UPDATES_BTN_CHECK', '🔄 Проверить обновления'),
                callback_data='admin_updates_check',
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t('ADMIN_UPDATES_BTN_INFO', '📋 Информация о версии'),
                callback_data='admin_updates_info',
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t('ADMIN_UPDATES_BTN_REPO', '🔗 Открыть репозиторий'),
                url=f'https://github.com/{version_service.repo}/releases',
            )
        ],
        [InlineKeyboardButton(text=texts.t('ADMIN_REQCH_BACK', '◀️ Назад'), callback_data='admin_panel')],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_version_info_keyboard(language: str = 'ru') -> InlineKeyboardMarkup:
    texts = get_texts(language)
    buttons = [
        [
            InlineKeyboardButton(
                text=texts.t('ADMIN_UPDATES_BTN_REFRESH', '🔄 Обновить'), callback_data='admin_updates_info'
            )
        ],
        [
            InlineKeyboardButton(
                text=texts.t('ADMIN_UPDATES_BACK_MENU', '◀️ К обновлениям'), callback_data='admin_updates'
            )
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=buttons)


@admin_required
@error_handler
async def show_updates_menu(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    try:
        version_info = await version_service.get_version_info()

        current_version = version_info['current_version']
        has_updates = version_info['has_updates']
        total_newer = version_info['total_newer']
        last_check = version_info['last_check']

        status_icon = '🆕' if has_updates else '✅'
        status_text = (
            texts.t('ADMIN_UPDATES_STATUS_AVAILABLE', 'Доступно {count} обновлений').format(count=total_newer)
            if has_updates
            else texts.t('ADMIN_UPDATES_STATUS_CURRENT', 'Актуальная версия')
        )

        last_check_text = ''
        if last_check:
            last_check_text = texts.t('ADMIN_UPDATES_LAST_CHECK', '\n🕐 Последняя проверка: {time}').format(
                time=last_check.strftime('%d.%m.%Y %H:%M')
            )

        message = texts.t('ADMIN_UPDATES_MENU_TITLE', '🔄 <b>СИСТЕМА ОБНОВЛЕНИЙ</b>\n\n')
        message += texts.t('ADMIN_UPDATES_CURRENT', '📦 <b>Текущая версия:</b> <code>{version}</code>\n').format(
            version=current_version
        )
        message += texts.t('ADMIN_UPDATES_STATUS_LINE', '{icon} <b>Статус:</b> {status}\n\n').format(
            icon=status_icon, status=status_text
        )
        message += texts.t('ADMIN_UPDATES_REPO', '🔗 <b>Репозиторий:</b> {repo}{last_check}\n\n').format(
            repo=version_service.repo, last_check=last_check_text
        )
        message += texts.t(
            'ADMIN_UPDATES_HINT',
            'ℹ️ Система автоматически проверяет обновления каждый час и отправляет уведомления о новых версиях.',
        )

        await callback.message.edit_text(
            message, reply_markup=get_updates_keyboard(db_user.language), parse_mode='HTML'
        )
        await callback.answer()

    except Exception as e:
        if 'message is not modified' in str(e).lower():
            logger.debug('📝 Сообщение не изменено в show_updates_menu')
            await callback.answer()
            return
        logger.error('Ошибка показа меню обновлений', error=e)
        await callback.answer(texts.t('ADMIN_UPDATES_MENU_ERROR', '❌ Ошибка загрузки меню обновлений'), show_alert=True)


@admin_required
@error_handler
async def check_updates(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    await callback.answer(texts.t('ADMIN_UPDATES_CHECKING', '🔄 Проверяю обновления...'))

    try:
        has_updates, newer_releases = await version_service.check_for_updates(force=True)

        if not has_updates:
            message = texts.t(
                'ADMIN_UPDATES_NONE',
                '✅ <b>ОБНОВЛЕНИЯ НЕ НАЙДЕНЫ</b>\n\n'
                '📦 <b>Текущая версия:</b> <code>{version}</code>\n'
                '🎯 <b>Статус:</b> У вас установлена последняя версия\n\n'
                '🔗 <b>Репозиторий:</b> {repo}',
            ).format(version=version_service.current_version, repo=version_service.repo)

        else:
            updates_list = []
            for i, release in enumerate(newer_releases[:5]):
                icon = version_service.format_version_display(release).split()[0]
                updates_list.append(f'{i + 1}. {icon} <code>{release.tag_name}</code> • {release.formatted_date}')

            updates_text = '\n'.join(updates_list)
            more_text = (
                texts.t('ADMIN_UPDATES_MORE', '\n\n📋 И еще {count} обновлений...').format(
                    count=len(newer_releases) - 5
                )
                if len(newer_releases) > 5
                else ''
            )

            message = texts.t('ADMIN_UPDATES_FOUND_TITLE', '🆕 <b>НАЙДЕНЫ ОБНОВЛЕНИЯ</b>\n\n')
            message += texts.t('ADMIN_UPDATES_CURRENT', '📦 <b>Текущая версия:</b> <code>{version}</code>\n').format(
                version=version_service.current_version
            )
            message += texts.t('ADMIN_UPDATES_COUNT', '🎯 <b>Доступно обновлений:</b> {count}\n\n').format(
                count=len(newer_releases)
            )
            message += texts.t('ADMIN_UPDATES_LIST_HEADER', '📋 <b>Последние версии:</b>\n{list}{more}\n\n').format(
                list=updates_text, more=more_text
            )
            message += texts.t('ADMIN_UPDATES_REPO', '🔗 <b>Репозиторий:</b> {repo}').format(repo=version_service.repo)

        keyboard = get_updates_keyboard(db_user.language)

        if has_updates:
            keyboard.inline_keyboard.insert(
                -2,
                [
                    InlineKeyboardButton(
                        text=texts.t('ADMIN_UPDATES_BTN_DETAILS', '📋 Подробнее о версиях'),
                        callback_data='admin_updates_info',
                    )
                ],
            )

        await callback.message.edit_text(message, reply_markup=keyboard, parse_mode='HTML')

    except Exception as e:
        if 'message is not modified' in str(e).lower():
            logger.debug('📝 Сообщение не изменено в check_updates')
            return
        logger.error('Ошибка проверки обновлений', error=e)
        await callback.message.edit_text(
            texts.t(
                'ADMIN_UPDATES_CHECK_ERROR',
                '❌ <b>ОШИБКА ПРОВЕРКИ ОБНОВЛЕНИЙ</b>\n\n'
                'Не удалось связаться с сервером GitHub.\n'
                'Попробуйте позже.\n\n'
                '📦 <b>Текущая версия:</b> <code>{version}</code>',
            ).format(version=version_service.current_version),
            reply_markup=get_updates_keyboard(db_user.language),
            parse_mode='HTML',
        )


@admin_required
@error_handler
async def show_version_info(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    await callback.answer(texts.t('ADMIN_UPDATES_INFO_LOADING', '📋 Загружаю информацию о версиях...'))

    try:
        version_info = await version_service.get_version_info()

        current_version = version_info['current_version']
        current_release = version_info['current_release']
        newer_releases = version_info['newer_releases']
        has_updates = version_info['has_updates']
        last_check = version_info['last_check']

        current_info = texts.t('ADMIN_UPDATES_INFO_CURRENT', '📦 <b>ТЕКУЩАЯ ВЕРСИЯ</b>\n\n')

        if current_release:
            current_info += texts.t('ADMIN_UPDATES_INFO_TAG', '🏷️ <b>Версия:</b> <code>{tag}</code>\n').format(
                tag=current_release.tag_name
            )
            current_info += texts.t('ADMIN_UPDATES_INFO_DATE', '📅 <b>Дата релиза:</b> {date}\n').format(
                date=current_release.formatted_date
            )
            if current_release.short_description:
                current_info += texts.t('ADMIN_UPDATES_INFO_DESC', '📝 <b>Описание:</b>\n{desc}\n').format(
                    desc=current_release.short_description
                )
        else:
            current_info += texts.t('ADMIN_UPDATES_INFO_TAG', '🏷️ <b>Версия:</b> <code>{tag}</code>\n').format(
                tag=current_version
            )
            current_info += texts.t('ADMIN_UPDATES_INFO_UNAVAILABLE', 'ℹ️ <b>Статус:</b> Информация о релизе недоступна\n')

        message_parts = [current_info]

        if has_updates and newer_releases:
            updates_info = texts.t('ADMIN_UPDATES_INFO_AVAILABLE', '\n🆕 <b>ДОСТУПНЫЕ ОБНОВЛЕНИЯ</b>\n\n')

            for i, release in enumerate(newer_releases):
                icon = '🔥' if i == 0 else '📦'
                if release.prerelease:
                    icon = '🧪'
                elif release.is_dev:
                    icon = '🔧'

                updates_info += f'{icon} <b>{release.tag_name}</b>\n'
                updates_info += f'   📅 {release.formatted_date}\n'
                if release.short_description:
                    updates_info += f'   📝 {release.short_description}\n'
                updates_info += '\n'

            message_parts.append(updates_info.rstrip())

        system_info = texts.t('ADMIN_UPDATES_INFO_SYSTEM', '\n🔧 <b>СИСТЕМА ОБНОВЛЕНИЙ</b>\n\n')
        system_info += texts.t('ADMIN_UPDATES_REPO', '🔗 <b>Репозиторий:</b> {repo}\n').format(repo=version_service.repo)
        system_info += texts.t(
            'ADMIN_UPDATES_AUTO',
            '⚡ <b>Автопроверка:</b> {status}\n',
        ).format(
            status=texts.t('ADMIN_MAINT_ON', 'Включена')
            if version_service.enabled
            else texts.t('ADMIN_MAINT_OFF', 'Отключена')
        )
        system_info += texts.t('ADMIN_UPDATES_INTERVAL', '🕐 <b>Интервал:</b> Каждый час\n')

        if last_check:
            system_info += texts.t('ADMIN_UPDATES_LAST_CHECK', '🕐 <b>Последняя проверка:</b> {time}\n').format(
                time=last_check.strftime('%d.%m.%Y %H:%M')
            )

        message_parts.append(system_info.rstrip())

        final_message = '\n'.join(message_parts)

        if len(final_message) > 4000:
            final_message = final_message[:3900] + texts.t('ADMIN_UPDATES_TRUNCATED', '\n\n... (информация обрезана)')

        await callback.message.edit_text(
            final_message,
            reply_markup=get_version_info_keyboard(db_user.language),
            parse_mode='HTML',
            disable_web_page_preview=True,
        )

    except Exception as e:
        if 'message is not modified' in str(e).lower():
            logger.debug('📝 Сообщение не изменено в show_version_info')
            return
        logger.error('Ошибка получения информации о версиях', error=e)
        await callback.message.edit_text(
            texts.t(
                'ADMIN_UPDATES_INFO_ERROR',
                '❌ <b>ОШИБКА ЗАГРУЗКИ</b>\n\n'
                'Не удалось получить информацию о версиях.\n\n'
                '📦 <b>Текущая версия:</b> <code>{version}</code>',
            ).format(version=version_service.current_version),
            reply_markup=get_version_info_keyboard(db_user.language),
            parse_mode='HTML',
        )


def register_handlers(dp: Dispatcher):
    dp.callback_query.register(show_updates_menu, F.data == 'admin_updates')

    dp.callback_query.register(check_updates, F.data == 'admin_updates_check')

    dp.callback_query.register(show_version_info, F.data == 'admin_updates_info')
