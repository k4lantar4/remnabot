# Bot User Handler Templates

Use these as starting points. Rename `feature` and `FEATURE` consistently before editing.

## Minimal Callback Handler

```python
import structlog
from aiogram import Dispatcher, F, types

from app.database.models import User
from app.keyboards.inline import get_feature_keyboard
from app.localization.texts import get_texts


logger = structlog.get_logger(__name__)


async def show_feature(callback: types.CallbackQuery, db_user: User) -> None:
    texts = get_texts(db_user.language)
    await callback.answer()
    await callback.message.edit_text(
        texts.t('FEATURE_TITLE', '<b>Название функции</b>'),
        reply_markup=get_feature_keyboard(db_user.language),
        disable_web_page_preview=True,
    )


def register_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(show_feature, F.data == 'menu_feature')
```

## Callback Handler With Validation

```python
async def handle_feature_page(callback: types.CallbackQuery, db_user: User) -> None:
    texts = get_texts(db_user.language)

    try:
        _, page_str = callback.data.split(':', 1)
        page = int(page_str)
    except (AttributeError, IndexError, ValueError):
        await callback.answer(
            texts.t('FEATURE_INVALID_PAGE', 'Некорректная страница'),
            show_alert=True,
        )
        return

    await callback.answer()
    await callback.message.edit_text(
        texts.t('FEATURE_PAGE_TITLE', '<b>Страница {page}</b>').format(page=page),
        reply_markup=get_feature_keyboard(db_user.language),
    )
```

## Multi-Step FSM Handler

```python
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.states import FeatureStates


async def start_feature(callback: types.CallbackQuery, db_user: User, state: FSMContext) -> None:
    texts = get_texts(db_user.language)
    await state.set_state(FeatureStates.waiting_input)
    await callback.answer()
    await callback.message.edit_text(
        texts.t('FEATURE_INPUT_PROMPT', 'Введите значение:'),
        reply_markup=get_feature_cancel_keyboard(db_user.language),
    )


async def process_feature_input(
    message: types.Message,
    db_user: User,
    db: AsyncSession,
    state: FSMContext,
) -> None:
    texts = get_texts(db_user.language)
    value = (message.text or '').strip()

    if not value:
        await message.answer(texts.t('FEATURE_INPUT_EMPTY', 'Значение не может быть пустым'))
        return

    await state.clear()
    await message.answer(
        texts.t('FEATURE_INPUT_SAVED', 'Сохранено: {value}').format(value=value),
    )


async def cancel_feature(callback: types.CallbackQuery, db_user: User, state: FSMContext) -> None:
    texts = get_texts(db_user.language)
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.t('FEATURE_CANCELLED', 'Действие отменено'))


def register_handlers(dp: Dispatcher) -> None:
    dp.callback_query.register(start_feature, F.data == 'menu_feature')
    dp.message.register(process_feature_input, FeatureStates.waiting_input, F.text)
    dp.callback_query.register(cancel_feature, F.data == 'feature_cancel')
```

## FSM State

Add only when the feature needs multi-step input.

```python
class FeatureStates(StatesGroup):
    waiting_input = State()
```

## Inline Keyboard Builder

```python
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.localization.loader import DEFAULT_LANGUAGE
from app.localization.texts import get_texts


def get_feature_keyboard(language: str = DEFAULT_LANGUAGE) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=texts.t('FEATURE_ACTION_BTN', 'Выполнить'),
                    callback_data='feature_action',
                ),
            ],
            [
                InlineKeyboardButton(
                    text=texts.t('BACK_TO_MAIN_MENU', '⬅️ Главное меню'),
                    callback_data='main_menu',
                ),
            ],
        ],
    )
```

## Locale Keys

Use a stable prefix for each feature. Keep placeholder names identical in code and JSON.

```json
{
  "FEATURE_TITLE": "<b>عنوان قابلیت</b>",
  "FEATURE_ACTION_BTN": "انجام دادن",
  "FEATURE_INVALID_PAGE": "صفحه نامعتبر است",
  "FEATURE_INPUT_PROMPT": "مقدار را وارد کنید:",
  "FEATURE_INPUT_EMPTY": "مقدار نمی‌تواند خالی باشد",
  "FEATURE_INPUT_SAVED": "ذخیره شد: {value}",
  "FEATURE_CANCELLED": "عملیات لغو شد"
}
```

## bot.py Registration

Import the module near peer user handlers, then register it in `setup_bot()`.

```python
from app.handlers import feature
```

```python
feature.register_handlers(dp)
```
