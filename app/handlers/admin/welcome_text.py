import re

import structlog
from aiogram import Dispatcher, F, types
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.crud.welcome_text import (
    get_available_placeholders,
    get_current_welcome_text_or_default,
    get_current_welcome_text_settings,
    set_welcome_text,
    toggle_welcome_text_status,
)
from app.database.models import User
from app.keyboards.admin import get_welcome_text_keyboard
from app.localization.texts import get_texts
from app.states import AdminStates
from app.utils.decorators import admin_required, error_handler


logger = structlog.get_logger(__name__)


def validate_html_tags(text: str, texts) -> tuple[bool, str]:
    """
    Проверяет HTML-теги в тексте на соответствие требованиям Telegram API.

    Args:
        text: Текст для проверки

    Returns:
        Кортеж из (валидно ли, сообщение об ошибке или None)
    """
    allowed_tags = {
        'b',
        'strong',
        'i',
        'em',
        'u',
        'ins',
        's',
        'strike',
        'del',
        'code',
        'pre',
        'a',
    }

    placeholder_pattern = r'\{[^{}]+\}'
    clean_text = re.sub(placeholder_pattern, '', text)

    tag_pattern = r'<(/?)([a-zA-Z]+)(\s[^>]*)?>'
    tags_with_pos = [
        (m.group(1), m.group(2), m.group(3), m.start(), m.end()) for m in re.finditer(tag_pattern, clean_text)
    ]

    for closing, tag, attrs, start_pos, end_pos in tags_with_pos:
        tag_lower = tag.lower()

        if tag_lower not in allowed_tags:
            return (
                False,
                texts.t(
                    'ADMIN_WELCOME_HTML_UNSUPPORTED_TAG',
                    'Неподдерживаемый HTML-тег: <{tag}>. Используйте только теги: {allowed}',
                ).format(tag=tag, allowed=', '.join(sorted(allowed_tags))),
            )

        if tag_lower == 'a':
            if closing:
                continue
            if not attrs:
                return False, texts.t(
                    'ADMIN_WELCOME_HTML_A_HREF',
                    "Тег <a> должен содержать атрибут href, например: <a href='URL'>ссылка</a>",
                )

            if 'href=' not in attrs.lower():
                return False, texts.t(
                    'ADMIN_WELCOME_HTML_A_HREF',
                    "Тег <a> должен содержать атрибут href, например: <a href='URL'>ссылка</a>",
                )

            href_match = re.search(r'href\s*=\s*[\'"]([^\'"]+)[\'"]', attrs, re.IGNORECASE)
            if href_match:
                url = href_match.group(1)
                if not re.match(r'^https?://|^tg://', url, re.IGNORECASE):
                    return False, texts.t(
                        'ADMIN_WELCOME_HTML_A_URL',
                        'URL в теге <a> должен начинаться с http://, https:// или tg://. Найдено: {url}',
                    ).format(url=url)
            else:
                return False, texts.t(
                    'ADMIN_WELCOME_HTML_A_EXTRACT',
                    'Не удалось извлечь URL из атрибута href тега <a>',
                )

    stack = []
    for closing, tag, attrs, start_pos, end_pos in tags_with_pos:
        tag_lower = tag.lower()

        if tag_lower not in allowed_tags:
            continue

        if closing:
            if not stack:
                return False, texts.t(
                    'ADMIN_WELCOME_HTML_EXTRA_CLOSE',
                    'Лишний закрывающий тег: </{tag}>',
                ).format(tag=tag)

            last_opening_tag = stack.pop()
            if last_opening_tag.lower() != tag_lower:
                return False, texts.t(
                    'ADMIN_WELCOME_HTML_MISMATCH',
                    'Тег </{tag}> не соответствует открывающему тегу <{opening}>',
                ).format(tag=tag, opening=last_opening_tag)
        else:
            stack.append(tag)

    if stack:
        unclosed_tags = ', '.join([f'<{tag}>' for tag in stack])
        return False, texts.t(
            'ADMIN_WELCOME_HTML_UNCLOSED',
            'Незакрытые теги: {tags}',
        ).format(tags=unclosed_tags)

    return True, None


def get_telegram_formatting_info(texts) -> str:
    return texts.t(
        'ADMIN_WELCOME_FORMATTING_INFO',
        """
📝 <b>Поддерживаемые теги форматирования:</b>

• <code>&lt;b&gt;жирный текст&lt;/b&gt;</code> → <b>жирный текст</b>
• <code>&lt;i&gt;курсив&lt;/i&gt;</code> → <i>курсив</i>
• <code>&lt;u&gt;подчеркнутый&lt;/u&gt;</code> → <u>подчеркнутый</u>
• <code>&lt;s&gt;зачеркнутый&lt;/s&gt;</code> → <s>зачеркнутый</s>
• <code>&lt;code&gt;моноширинный&lt;/code&gt;</code> → <code>моноширинный</code>
• <code>&lt;pre&gt;блок кода&lt;/pre&gt;</code> → многострочный код
• <code>&lt;a href="URL"&gt;ссылка&lt;/a&gt;</code> → ссылка

⚠️ <b>ВНИМАНИЕ:</b> Используйте ТОЛЬКО указанные выше теги!
Любые другие HTML-теги не поддерживаются и будут отображаться как обычный текст.

❌ <b>НЕ используйте:</b> &lt;div&gt;, &lt;span&gt;, &lt;p&gt;, &lt;br&gt;, &lt;h1&gt;-&lt;h6&gt;, &lt;img&gt; и другие HTML-теги.
""",
    )


def _status_text(texts, is_enabled: bool) -> str:
    return (
        texts.t('ADMIN_WELCOME_STATUS_ENABLED', 'включено')
        if is_enabled
        else texts.t('ADMIN_WELCOME_STATUS_DISABLED', 'отключено')
    )


def _panel_body(texts, is_enabled: bool, extra: str = '') -> str:
    status_emoji = '🟢' if is_enabled else '🔴'
    status_text = _status_text(texts, is_enabled)
    return texts.t(
        'ADMIN_WELCOME_PANEL_BODY',
        '👋 Управление приветственным текстом\n\n'
        '{status_emoji} <b>Статус:</b> {status_text}\n\n'
        '{extra}'
        'Здесь вы можете управлять текстом, который показывается новым пользователям после регистрации.\n\n'
        '💡 Доступные плейсхолдеры для автозамены:',
    ).format(status_emoji=status_emoji, status_text=status_text, extra=extra)


@admin_required
@error_handler
async def show_welcome_text_panel(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    welcome_settings = await get_current_welcome_text_settings(db)

    await callback.message.edit_text(
        _panel_body(texts, welcome_settings['is_enabled']),
        reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
        parse_mode='HTML',
    )
    await callback.answer()


@admin_required
@error_handler
async def toggle_welcome_text(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    new_status = await toggle_welcome_text_status(db, db_user.id)

    action_text = (
        texts.t('ADMIN_WELCOME_ACTION_ENABLED', 'включены')
        if new_status
        else texts.t('ADMIN_WELCOME_ACTION_DISABLED', 'отключены')
    )
    extra = texts.t(
        'ADMIN_WELCOME_TOGGLED',
        '✅ Приветственные сообщения {action}!\n\n',
    ).format(action=action_text)

    await callback.message.edit_text(
        _panel_body(texts, new_status, extra=extra),
        reply_markup=get_welcome_text_keyboard(db_user.language, new_status),
        parse_mode='HTML',
    )
    await callback.answer()


@admin_required
@error_handler
async def show_current_welcome_text(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    welcome_settings = await get_current_welcome_text_settings(db)
    current_text = welcome_settings['text']
    is_enabled = welcome_settings['is_enabled']

    if not welcome_settings['id']:
        status = texts.t('ADMIN_WELCOME_DEFAULT_LABEL', '📝 Используется стандартный текст:')
    else:
        status = texts.t('ADMIN_WELCOME_CURRENT_LABEL', '📝 Текущий приветственный текст:')

    status_emoji = '🟢' if is_enabled else '🔴'
    status_text = _status_text(texts, is_enabled)

    placeholders = get_available_placeholders()
    placeholders_text = '\n'.join([f'• <code>{key}</code> - {desc}' for key, desc in placeholders.items()])

    await callback.message.edit_text(
        texts.t(
            'ADMIN_WELCOME_SHOW_TEXT',
            '{status_emoji} <b>Статус:</b> {status_text}\n\n'
            '{status}\n\n'
            '<code>{current_text}</code>\n\n'
            '💡 Доступные плейсхолдеры:\n{placeholders}',
        ).format(
            status_emoji=status_emoji,
            status_text=status_text,
            status=status,
            current_text=current_text,
            placeholders=placeholders_text,
        ),
        reply_markup=get_welcome_text_keyboard(db_user.language, is_enabled),
        parse_mode='HTML',
    )
    await callback.answer()


@admin_required
@error_handler
async def show_placeholders_help(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    welcome_settings = await get_current_welcome_text_settings(db)
    placeholders = get_available_placeholders()
    placeholders_text = '\n'.join([f'• <code>{key}</code>\n  {desc}' for key, desc in placeholders.items()])

    help_text = texts.t(
        'ADMIN_WELCOME_PLACEHOLDERS_HELP',
        '💡 Доступные плейсхолдеры для автозамены:\n\n'
        '{placeholders}\n\n'
        '📌 Примеры использования:\n'
        '• <code>Привет, {user_name}! Добро пожаловать!</code>\n'
        '• <code>Здравствуйте, {first_name}! Рады видеть вас!</code>\n'
        '• <code>Привет, {username}! Спасибо за регистрацию!</code>\n\n'
        "При отсутствии данных пользователя используется слово 'друг'.",
    ).format(placeholders=placeholders_text)

    await callback.message.edit_text(
        help_text,
        reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
        parse_mode='HTML',
    )
    await callback.answer()


@admin_required
@error_handler
async def show_formatting_help(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    welcome_settings = await get_current_welcome_text_settings(db)
    formatting_info = get_telegram_formatting_info(texts)

    await callback.message.edit_text(
        formatting_info,
        reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
        parse_mode='HTML',
    )
    await callback.answer()


@admin_required
@error_handler
async def start_edit_welcome_text(callback: types.CallbackQuery, state: FSMContext, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    welcome_settings = await get_current_welcome_text_settings(db)
    current_text = welcome_settings['text']

    placeholders = get_available_placeholders()
    placeholders_text = '\n'.join([f'• <code>{key}</code> - {desc}' for key, desc in placeholders.items()])

    await callback.message.edit_text(
        texts.t(
            'ADMIN_WELCOME_EDIT_PROMPT',
            '📝 Редактирование приветственного текста\n\n'
            'Текущий текст:\n'
            '<code>{current_text}</code>\n\n'
            '💡 Доступные плейсхолдеры:\n{placeholders}\n\n'
            'Отправьте новый текст:',
        ).format(current_text=current_text, placeholders=placeholders_text),
        parse_mode='HTML',
    )

    await state.set_state(AdminStates.editing_welcome_text)
    await callback.answer()


@admin_required
@error_handler
async def process_welcome_text_edit(message: types.Message, state: FSMContext, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    new_text = message.text.strip()

    if len(new_text) < 10:
        await message.answer(texts.t('ADMIN_WELCOME_TOO_SHORT', '❌ Текст слишком короткий! Минимум 10 символов.'))
        return

    if len(new_text) > 4000:
        await message.answer(texts.t('ADMIN_WELCOME_TOO_LONG', '❌ Текст слишком длинный! Максимум 4000 символов.'))
        return

    is_valid, error_msg = validate_html_tags(new_text, texts)
    if not is_valid:
        await message.answer(
            texts.t('ADMIN_WELCOME_HTML_ERROR', '❌ Ошибка в HTML-разметке:\n\n{error}').format(error=error_msg)
        )
        return

    success = await set_welcome_text(db, new_text, db_user.id)

    if success:
        welcome_settings = await get_current_welcome_text_settings(db)
        status_emoji = '🟢' if welcome_settings['is_enabled'] else '🔴'
        status_text = _status_text(texts, welcome_settings['is_enabled'])

        placeholders = get_available_placeholders()
        placeholders_text = '\n'.join([f'• <code>{key}</code>' for key in placeholders.keys()])

        await message.answer(
            texts.t(
                'ADMIN_WELCOME_SAVED',
                '✅ Приветственный текст успешно обновлен!\n\n'
                '{status_emoji} <b>Статус:</b> {status_text}\n\n'
                'Новый текст:\n'
                '<code>{new_text}</code>\n\n'
                '💡 Будут заменяться плейсхолдеры: {placeholders}',
            ).format(
                status_emoji=status_emoji,
                status_text=status_text,
                new_text=new_text,
                placeholders=placeholders_text,
            ),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
            parse_mode='HTML',
        )
    else:
        welcome_settings = await get_current_welcome_text_settings(db)
        await message.answer(
            texts.t('ADMIN_WELCOME_SAVE_ERROR', '❌ Ошибка при сохранении текста. Попробуйте еще раз.'),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
        )

    await state.clear()


@admin_required
@error_handler
async def reset_welcome_text(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    texts = get_texts(db_user.language)
    default_text = await get_current_welcome_text_or_default()
    success = await set_welcome_text(db, default_text, db_user.id)

    if success:
        welcome_settings = await get_current_welcome_text_settings(db)
        status_emoji = '🟢' if welcome_settings['is_enabled'] else '🔴'
        status_text = _status_text(texts, welcome_settings['is_enabled'])

        await callback.message.edit_text(
            texts.t(
                'ADMIN_WELCOME_RESET_SUCCESS',
                '✅ Приветственный текст сброшен на стандартный!\n\n'
                '{status_emoji} <b>Статус:</b> {status_text}\n\n'
                'Стандартный текст:\n'
                '<code>{default_text}</code>\n\n'
                '💡 Плейсхолдер <code>{user_name}</code> будет заменяться на имя пользователя',
            ).format(status_emoji=status_emoji, status_text=status_text, default_text=default_text),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
            parse_mode='HTML',
        )
    else:
        welcome_settings = await get_current_welcome_text_settings(db)
        await callback.message.edit_text(
            texts.t('ADMIN_WELCOME_RESET_ERROR', '❌ Ошибка при сбросе текста. Попробуйте еще раз.'),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
        )

    await callback.answer()


@admin_required
@error_handler
async def show_preview_welcome_text(callback: types.CallbackQuery, db_user: User, db: AsyncSession):
    from app.database.crud.welcome_text import get_welcome_text_for_user

    texts = get_texts(db_user.language)

    class TestUser:
        def __init__(self):
            self.first_name = texts.t('ADMIN_WELCOME_PREVIEW_NAME', 'Иван')
            self.username = 'test_user'

    test_user = TestUser()
    preview_text = await get_welcome_text_for_user(db, test_user)

    welcome_settings = await get_current_welcome_text_settings(db)

    if preview_text:
        await callback.message.edit_text(
            texts.t(
                'ADMIN_WELCOME_PREVIEW_ACTIVE',
                '👁️ Предварительный просмотр\n\n'
                "Как будет выглядеть текст для пользователя '{name}' (@test_user):\n\n"
                '<code>{preview_text}</code>',
            ).format(name=test_user.first_name, preview_text=preview_text),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
            parse_mode='HTML',
        )
    else:
        await callback.message.edit_text(
            texts.t(
                'ADMIN_WELCOME_PREVIEW_DISABLED',
                '👁️ Предварительный просмотр\n\n'
                '🔴 Приветственные сообщения отключены.\n'
                'Новые пользователи не будут получать приветственный текст после регистрации.',
            ),
            reply_markup=get_welcome_text_keyboard(db_user.language, welcome_settings['is_enabled']),
            parse_mode='HTML',
        )

    await callback.answer()


def register_welcome_text_handlers(dp: Dispatcher):
    dp.callback_query.register(show_welcome_text_panel, F.data == 'welcome_text_panel')

    dp.callback_query.register(toggle_welcome_text, F.data == 'toggle_welcome_text')

    dp.callback_query.register(show_current_welcome_text, F.data == 'show_welcome_text')

    dp.callback_query.register(show_placeholders_help, F.data == 'show_placeholders_help')

    dp.callback_query.register(show_formatting_help, F.data == 'show_formatting_help')

    dp.callback_query.register(show_preview_welcome_text, F.data == 'preview_welcome_text')

    dp.callback_query.register(start_edit_welcome_text, F.data == 'edit_welcome_text')

    dp.callback_query.register(reset_welcome_text, F.data == 'reset_welcome_text')

    dp.message.register(process_welcome_text_edit, AdminStates.editing_welcome_text)
