# مدل‌های داده

## خلاصه

پروژه از **SQLAlchemy ORM** برای مدیریت دیتابیس استفاده می‌کند با پشتیبانی از PostgreSQL (production) و SQLite (توسعه).

- **ORM:** SQLAlchemy 2.0
- **مهاجرت:** Alembic
- **تعداد جداول:** ۳۵+ جدول
- **تعداد مهاجرت‌ها:** ۱۲ نسخه

## نمودار روابط

```
┌─────────────┐       ┌───────────────┐       ┌──────────────┐
│    User     │──1:1──│ Subscription  │──N:N──│ ServerSquad  │
└─────────────┘       └───────────────┘       └──────────────┘
       │                     │                       │
       │1:N                  │1:N                    │N:N
       ▼                     ▼                       ▼
┌─────────────┐       ┌───────────────┐       ┌──────────────┐
│ Transaction │       │DiscountOffer  │       │  PromoGroup  │
└─────────────┘       └───────────────┘       └──────────────┘
       │
       │1:1
       ▼
┌─────────────────┐
│ Payment Tables  │
│ (YooKassa,      │
│  CryptoBot,     │
│  Heleket, etc.) │
└─────────────────┘
```

## مدل‌های اصلی

### User (کاربران)

```python
class User(Base):
    __tablename__ = "users"
```

| فیلد | نوع | توضیح |
|------|-----|-------|
| `id` | Integer | کلید اصلی |
| `telegram_id` | BigInteger | شناسه تلگرام (منحصر به فرد) |
| `username` | String(255) | نام کاربری تلگرام |
| `first_name` | String(255) | نام |
| `last_name` | String(255) | نام خانوادگی |
| `status` | String(20) | وضعیت: active, blocked, deleted |
| `language` | String(5) | زبان: ru, en |
| `balance_toman` | Integer | موجودی به کوپک |
| `remnawave_uuid` | String(255) | شناسه Remnawave |
| `referred_by_id` | ForeignKey | معرف |
| `referral_code` | String(20) | کد معرفی |
| `promo_group_id` | ForeignKey | گروه تخفیف |
| `has_had_paid_subscription` | Boolean | آیا اشتراک پولی داشته |
| `has_made_first_topup` | Boolean | آیا اولین شارژ را انجام داده |
| `created_at` | DateTime | تاریخ ایجاد |
| `last_activity` | DateTime | آخرین فعالیت |

**روابط:**
- `subscription` → Subscription (1:1)
- `transactions` → Transaction (1:N)
- `referrals` → User (1:N)
- `promo_group` → PromoGroup (N:1)

---

### Subscription (اشتراک)

```python
class Subscription(Base):
    __tablename__ = "subscriptions"
```

| فیلد | نوع | توضیح |
|------|-----|-------|
| `id` | Integer | کلید اصلی |
| `user_id` | ForeignKey | کاربر (منحصر به فرد) |
| `status` | String(20) | وضعیت: trial, active, expired, disabled, pending |
| `is_trial` | Boolean | آیا آزمایشی است |
| `start_date` | DateTime | تاریخ شروع |
| `end_date` | DateTime | تاریخ پایان |
| `traffic_limit_gb` | Integer | محدودیت ترافیک (0 = نامحدود) |
| `traffic_used_gb` | Float | ترافیک مصرفی |
| `device_limit` | Integer | تعداد دستگاه |
| `subscription_url` | String | لینک اشتراک |
| `subscription_crypto_link` | String | لینک رمزنگاری |
| `connected_squads` | JSON | سرورهای متصل |
| `autopay_enabled` | Boolean | پرداخت خودکار فعال |
| `autopay_days_before` | Integer | روز قبل از پرداخت خودکار |
| `remnawave_short_uuid` | String(255) | شناسه کوتاه Remnawave |

**وضعیت‌ها (Enum):**
```python
class SubscriptionStatus(Enum):
    TRIAL = "trial"
    ACTIVE = "active"
    EXPIRED = "expired"
    DISABLED = "disabled"
    PENDING = "pending"
```

---

### Transaction (تراکنش)

```python
class Transaction(Base):
    __tablename__ = "transactions"
```

| فیلد | نوع | توضیح |
|------|-----|-------|
| `id` | Integer | کلید اصلی |
| `user_id` | ForeignKey | کاربر |
| `type` | String | نوع: deposit, withdrawal, subscription_payment, refund, referral_reward |
| `amount_kopeks` | Integer | مبلغ به کوپک |
| `description` | Text | توضیحات |
| `payment_method` | String | روش پرداخت |
| `external_id` | String | شناسه خارجی |
| `created_at` | DateTime | تاریخ ایجاد |

**انواع تراکنش (Enum):**
```python
class TransactionType(Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    SUBSCRIPTION_PAYMENT = "subscription_payment"
    REFUND = "refund"
    REFERRAL_REWARD = "referral_reward"
    POLL_REWARD = "poll_reward"
```

---

### ServerSquad (سرور)

```python
class ServerSquad(Base):
    __tablename__ = "server_squads"
```

| فیلد | نوع | توضیح |
|------|-----|-------|
| `id` | Integer | کلید اصلی |
| `uuid` | String(255) | شناسه منحصر به فرد |
| `name` | String(255) | نام سرور |
| `display_name` | String(255) | نام نمایشی |
| `country_code` | String(10) | کد کشور |
| `is_enabled` | Boolean | فعال |
| `is_trial_pool` | Boolean | در استخر آزمایشی |
| `is_paid_pool` | Boolean | در استخر پولی |
| `extra_price_kopeks` | Integer | قیمت اضافی |
| `description` | Text | توضیحات |

**روابط:**
- `allowed_promo_groups` → PromoGroup (N:N)

---

### PromoGroup (گروه تخفیف)

```python
class PromoGroup(Base):
    __tablename__ = "promo_groups"
```

| فیلد | نوع | توضیح |
|------|-----|-------|
| `id` | Integer | کلید اصلی |
| `name` | String(255) | نام (منحصر به فرد) |
| `priority` | Integer | اولویت |
| `server_discount_percent` | Integer | درصد تخفیف سرور |
| `traffic_discount_percent` | Integer | درصد تخفیف ترافیک |
| `device_discount_percent` | Integer | درصد تخفیف دستگاه |
| `period_discounts` | JSON | تخفیفات دوره‌ای |
| `auto_assign_total_spent_kopeks` | Integer | آستانه تخصیص خودکار |
| `is_default` | Boolean | پیش‌فرض |

---

### PromoCode (کد تخفیف)

```python
class PromoCode(Base):
    __tablename__ = "promo_codes"
```

| فیلد | نوع | توضیح |
|------|-----|-------|
| `id` | Integer | کلید اصلی |
| `code` | String(50) | کد (منحصر به فرد) |
| `type` | String | نوع: balance, subscription_days, trial_subscription, promo_group |
| `value` | Integer | مقدار |
| `max_uses` | Integer | حداکثر استفاده |
| `current_uses` | Integer | تعداد استفاده فعلی |
| `expires_at` | DateTime | تاریخ انقضا |
| `is_active` | Boolean | فعال |
| `is_one_time_per_user` | Boolean | یکبار برای هر کاربر |

**انواع کد تخفیف (Enum):**
```python
class PromoCodeType(Enum):
    BALANCE = "balance"
    SUBSCRIPTION_DAYS = "subscription_days"
    TRIAL_SUBSCRIPTION = "trial_subscription"
    PROMO_GROUP = "promo_group"
```

---

## مدل‌های پرداخت

### YooKassaPayment

```python
class YooKassaPayment(Base):
    __tablename__ = "yookassa_payments"
```

| فیلد | نوع | توضیح |
|------|-----|-------|
| `yookassa_payment_id` | String(255) | شناسه YooKassa |
| `amount_kopeks` | Integer | مبلغ |
| `status` | String(50) | وضعیت |
| `is_paid` | Boolean | پرداخت شده |
| `confirmation_url` | Text | لینک تأیید |

### CryptoBotPayment

```python
class CryptoBotPayment(Base):
    __tablename__ = "cryptobot_payments"
```

| فیلد | نوع | توضیح |
|------|-----|-------|
| `invoice_id` | String(255) | شناسه فاکتور |
| `amount` | String(50) | مبلغ |
| `asset` | String(10) | ارز دیجیتال |
| `status` | String(50) | وضعیت |

### HeleketPayment

```python
class HeleketPayment(Base):
    __tablename__ = "heleket_payments"
```

### MulenPayPayment

```python
class MulenPayPayment(Base):
    __tablename__ = "mulenpay_payments"
```

### Pal24Payment

```python
class Pal24Payment(Base):
    __tablename__ = "pal24_payments"
```

### WataPayment

```python
class WataPayment(Base):
    __tablename__ = "wata_payments"
```

### PlategaPayment

```python
class PlategaPayment(Base):
    __tablename__ = "platega_payments"
```

---

## مدل‌های پشتیبانی

### Ticket (تیکت)

| فیلد | نوع | توضیح |
|------|-----|-------|
| `id` | Integer | کلید اصلی |
| `user_id` | ForeignKey | کاربر |
| `subject` | String | موضوع |
| `status` | String | وضعیت: open, in_progress, resolved, closed |
| `priority` | String | اولویت: low, normal, high, urgent |

### TicketMessage (پیام تیکت)

| فیلد | نوع | توضیح |
|------|-----|-------|
| `ticket_id` | ForeignKey | تیکت |
| `sender_type` | String | فرستنده: user, admin |
| `content` | Text | محتوا |
| `attachment_file_id` | String | شناسه فایل پیوست |

---

## مدل‌های بازاریابی

### AdvertisingCampaign (کمپین تبلیغاتی)

| فیلد | نوع | توضیح |
|------|-----|-------|
| `id` | Integer | کلید اصلی |
| `code` | String(100) | کد کمپین |
| `name` | String(255) | نام |
| `balance_bonus_kopeks` | Integer | پاداش موجودی |
| `trial_days_bonus` | Integer | پاداش روز آزمایشی |
| `is_active` | Boolean | فعال |

### Broadcast (رساندن)

| فیلد | نوع | توضیح |
|------|-----|-------|
| `id` | Integer | کلید اصلی |
| `text` | Text | متن |
| `target_audience` | String | مخاطب هدف |
| `status` | String | وضعیت |
| `sent_count` | Integer | تعداد ارسال |

---

## روش‌های پرداخت (Enum)

```python
class PaymentMethod(Enum):
    TELEGRAM_STARS = "telegram_stars"
    TRIBUTE = "tribute"
    YOOKASSA = "yookassa"
    CRYPTOBOT = "cryptobot"
    HELEKET = "heleket"
    MULENPAY = "mulenpay"
    PAL24 = "pal24"
    WATA = "wata"
    PLATEGA = "platega"
    MANUAL = "manual"
```

---

## مهاجرت‌ها (Alembic)

| نسخه | توضیح |
|------|-------|
| `1b2e3d4f5a6b` | افزودن حالت پین و آخرین پین کاربر |
| `1f5f3a3f5a4d` | افزودن گروه‌های تخفیف و FK کاربر |
| `2b3c1d4e5f6a` | افزودن پرداخت‌های Platega |
| `4b6b0f58c8f9` | افزودن تخفیفات دوره‌ای به گروه‌های تخفیف |
| `5d1f1f8b2e9a` | افزودن کمپین‌های تبلیغاتی |
| `5f2a3e099427` | افزودن فیلدهای رسانه به پیام‌های سنجاق‌شده |
| `7a3c0b8f5b84` | افزودن ارسال قبل از منو به پیام‌های سنجاق‌شده |
| `8fd1e338eb45` | افزودن جدول اعلان‌های ارسال‌شده |
| `9f0f2d5a1c7b` | افزودن جداول نظرسنجی |
| `c2f9c3b5f5c4` | افزودن جدول رویدادهای اشتراک |
| `c9c71d04f0a1` | افزودن جدول پیام‌های سنجاق‌شده |
| `e3c1e0b5b4a7` | افزودن درصد کمیسیون ارجاع به کاربران |

---

## ایندکس‌ها

| جدول | ایندکس | فیلدها |
|------|--------|--------|
| `users` | PRIMARY | `id` |
| `users` | UNIQUE | `telegram_id` |
| `users` | INDEX | `status` |
| `subscriptions` | PRIMARY | `id` |
| `subscriptions` | UNIQUE | `user_id` |
| `transactions` | PRIMARY | `id` |
| `transactions` | INDEX | `user_id`, `created_at` |
| `promo_codes` | UNIQUE | `code` |
| `server_squads` | UNIQUE | `uuid` |

---

*تولید شده توسط گردش‌کار document-project در 2025-12-25*
*تعداد کل جداول: ۳۵+*
