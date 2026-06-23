# fa-i18n Examples

## Handler — wrap one string

**Before:**
```python
await callback.answer('Некорректная страница', show_alert=True)
```

**After:**
```python
texts = get_texts(db_user.language)
await callback.answer(
    texts.t('FEATURE_INVALID_PAGE', 'Некорректная страница'),
    show_alert=True,
)
```

**fa.json:**
```json
"FEATURE_INVALID_PAGE": "صفحه نامعتبر است"
```

---

## Handler — formatted body with price

```python
texts = get_texts(db_user.language)
price = texts.format_price(amount_kopeks)
await callback.message.edit_text(
    texts.t('FEATURE_PRICE_LINE', 'Стоимость: {price}').format(price=price),
)
```

**fa.json** (placeholder name must match `ru.json`):
```json
"FEATURE_PRICE_LINE": "هزینه: {price}"
```

---

## Handler — Jalali date for fa users

```python
from app.utils.jalali_datetime import format_user_datetime

texts = get_texts(db_user.language)
end = format_user_datetime(subscription.end_date, language=db_user.language)
text = texts.t('FEATURE_EXPIRES', 'До: {end_date}').format(end_date=end)
```

---

## Keyboard button

```python
def get_feature_keyboard(language: str) -> InlineKeyboardMarkup:
    texts = get_texts(language)
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=texts.t('FEATURE_BTN', 'Открыть'),
                callback_data='menu_feature',
            ),
        ]],
    )
```

---

## fa.json only (key already wrapped in code)

If grep shows `texts.t('BALANCE_BUTTON_DEFAULT', ...)` and only the value is Cyrillic in `fa.json`:

```json
"BALANCE_BUTTON_DEFAULT": "💰 موجودی: {balance}"
```

Do **not** edit the handler.

---

## Cabinet route parity

When bot shows `SUBSCRIPTION_EXPIRED_NOTIFY`, ensure API responses use the same key:

```python
from app.localization.texts import get_texts

texts = get_texts(user.language)
return {"message": texts.t("SUBSCRIPTION_EXPIRED_NOTIFY", "Подписка истекла")}
```

Add matching key to `cabinet/src/locales/fa.json` if the React page displays it via i18n.

---

## Miniapp

```python
text = get_texts(_normalize_language_code(user)).t(
    "MINIAPP_DEVICE_LIMIT",
    "Достигнут лимит устройств",
)
```

---

## Cabinet React date

```tsx
import { formatUserDate } from '../utils/formatDate';

// lang from user settings / i18n
<span>{formatUserDate(subscription.expires_at, lang)}</span>
```

---

## Wrong vs right

| Wrong | Right |
|-------|-------|
| `texts = get_texts('fa')` at module level | `texts = get_texts(db_user.language)` inside handler |
| `"قیمت: 50000 تومان"` hardcoded | `texts.format_price(50000)` in `.format(price=...)` |
| `"تعرفه شما منقضی شد"` new KEY without ru mirror | Copy KEY name from `ru.json`, Persian only in `fa.json` |
| `format(end_date, '%d.%m.%Y')` for all users | `format_user_datetime(end_date, language=user.language)` |
| Edit handler + `purchase.py` in one commit | One handler per commit |
