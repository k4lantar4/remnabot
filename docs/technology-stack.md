# پشته فناوری پروژه

## خلاصه اجرایی

**Remnawave Bedolaga Bot** یک ربات تلگرام مدرن و مقیاس‌پذیر برای مدیریت اشتراک‌های VPN است که با معماری AsyncIO و پشته فناوری مدرن Python توسعه یافته است.

## جدول فناوری‌ها

### هسته اپلیکیشن

| دسته | فناوری | نسخه | توضیح |
|------|--------|------|-------|
| **زبان برنامه‌نویسی** | Python | 3.13+ | آخرین نسخه پایدار با پشتیبانی AsyncIO |
| **فریم‌ورک ربات** | aiogram | 3.22.0 | فریم‌ورک مدرن و async برای Telegram Bot API |
| **فریم‌ورک REST API** | FastAPI | 0.115.6 | API سریع و مدرن با مستندسازی خودکار |
| **سرور ASGI** | uvicorn | 0.32.1 | سرور ASGI با عملکرد بالا |
| **اعتبارسنجی داده** | Pydantic | 2.11.9 | اعتبارسنجی قوی با Type Hints |
| **تنظیمات** | pydantic-settings | 2.10.1 | مدیریت تنظیمات از فایل .env |

### دیتابیس و ذخیره‌سازی

| دسته | فناوری | نسخه | توضیح |
|------|--------|------|-------|
| **دیتابیس اصلی** | PostgreSQL | 15+ | دیتابیس رابطه‌ای production |
| **دیتابیس توسعه** | SQLite | - | دیتابیس سبک برای توسعه محلی |
| **ORM** | SQLAlchemy | 2.0.43 | ORM مدرن با پشتیبانی async |
| **مهاجرت** | Alembic | 1.16.5 | مدیریت نسخه‌های schema |
| **درایور PostgreSQL** | asyncpg | 0.30.0 | درایور async برای PostgreSQL |
| **درایور SQLite** | aiosqlite | 0.21.0 | درایور async برای SQLite |
| **کش** | Redis | 5.0.1 | کش در حافظه و سشن‌ها |

### شبکه و ارتباطات

| دسته | فناوری | نسخه | توضیح |
|------|--------|------|-------|
| **HTTP Client** | aiohttp | 3.12.15 | کلاینت HTTP async |
| **HTTP Server** | Flask | 3.1.0 | برای webhooks PayPalych |
| **فایل‌ها** | aiofiles | 23.2.1 | عملیات فایل async |

### سیستم پرداخت

| سیستم | فناوری | نسخه | توضیح |
|-------|--------|------|-------|
| **Telegram Stars** | داخلی | - | پرداخت داخلی تلگرام |
| **YooKassa** | yookassa | 3.9.0 | SDK رسمی YooKassa |
| **CryptoBot** | API | - | پرداخت کریپتو |
| **Heleket** | API | - | پرداخت کریپتو |
| **Tribute** | API | - | پرداخت تلگرام |
| **MulenPay** | API | - | پرداخت SBP |
| **PayPalych/Pal24** | API | - | کارت و SBP |
| **Platega** | API | - | کارت و SBP |
| **WATA** | API | - | کارت و SBP |

### زمان‌بندی و وظایف

| دسته | فناوری | نسخه | توضیح |
|------|--------|------|-------|
| **زمان‌بندی** | APScheduler | 3.11.0 | زمان‌بندی وظایف پس‌زمینه |
| **تاریخ/زمان** | python-dateutil | 2.9.0 | ابزارهای تاریخ و زمان |
| **منطقه زمانی** | pytz | 2023.4 | پشتیبانی منطقه زمانی |

### امنیت و رمزنگاری

| دسته | فناوری | نسخه | توضیح |
|------|--------|------|-------|
| **رمزنگاری** | cryptography | 41.0.0+ | رمزنگاری و امنیت |
| **QR Code** | qrcode[pil] | 7.4.2 | تولید کد QR |

### نظارت و لاگ‌گیری

| دسته | فناوری | نسخه | توضیح |
|------|--------|------|-------|
| **لاگ ساختاریافته** | structlog | 23.2.0 | لاگ‌گیری ساختاریافته |
| **مالیات** | nalogo | - | صدور رسید مالیاتی |

### ابزارهای توسعه

| دسته | فناوری | نسخه | توضیح |
|------|--------|------|-------|
| **تست** | pytest | - | فریم‌ورک تست |
| **تست async** | pytest-asyncio | - | پشتیبانی async در تست |
| **محیط** | python-dotenv | 1.1.1 | بارگذاری .env |
| **YAML** | PyYAML | 6.0.2 | پردازش فایل‌های YAML |
| **نسخه‌بندی** | packaging | 23.2 | مدیریت نسخه‌ها |

## معماری استقرار

### Docker

```dockerfile
# ایمیج پایه
FROM python:3.13-slim

# Multi-stage build برای کاهش حجم
# نسخه: v2.9.3

# پورت: 8080
# Healthcheck: /health
```

### سرویس‌ها (Docker Compose)

| سرویس | ایمیج | پورت | توضیح |
|-------|-------|------|-------|
| **bot** | python:3.13-slim (custom) | 8080 | اپلیکیشن اصلی |
| **postgres** | postgres:15-alpine | 5432 | دیتابیس |
| **redis** | redis:7-alpine | 6379 | کش |

### شبکه Docker

- **bot_network**: شبکه داخلی بین سرویس‌ها
- **remnawave-network**: شبکه اختیاری برای اتصال به پنل Remnawave

## الگوهای معماری

### الگوی اصلی: Service-Oriented Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Presentation Layer                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Handlers   │  │  Keyboards  │  │   WebAPI Routes     │  │
│  │  (aiogram)  │  │  (Inline/   │  │    (FastAPI)        │  │
│  │             │  │   Reply)    │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Business Logic Layer                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Services   │  │ Middlewares │  │     Validators      │  │
│  │  (68 files) │  │  (auth,     │  │                     │  │
│  │             │  │ throttling) │  │                     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Access Layer                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │    CRUD     │  │   Models    │  │    Migrations       │  │
│  │ (36 files)  │  │ (SQLAlchemy)│  │    (Alembic)        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      External Layer                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  Remnawave  │  │   Payment   │  │      Telegram       │  │
│  │    API      │  │  Providers  │  │        API          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### الگوهای طراحی استفاده شده

| الگو | استفاده |
|------|---------|
| **Repository Pattern** | CRUD operations در `app/database/crud/` |
| **Service Layer** | منطق کسب‌وکار در `app/services/` |
| **Middleware Pattern** | میان‌افزارها در `app/middlewares/` |
| **Factory Pattern** | ایجاد اتصال دیتابیس |
| **Singleton Pattern** | تنظیمات `settings` |
| **State Machine (FSM)** | مدیریت وضعیت مکالمات با aiogram |
| **Dependency Injection** | FastAPI dependencies |

## پیکربندی

### مدل تنظیمات (Pydantic Settings)

پیکربندی از طریق فایل `.env` و کلاس `Settings` در `app/config.py` مدیریت می‌شود:

- **۴۰۰+ پارامتر قابل تنظیم**
- اعتبارسنجی خودکار با Pydantic
- پشتیبانی از مقادیر پیش‌فرض
- تشخیص خودکار محیط (Docker/Local)

### دسته‌بندی تنظیمات

| دسته | تعداد پارامتر | توضیح |
|------|--------------|-------|
| **ربات** | ~20 | توکن، ادمین‌ها، webhook |
| **دیتابیس** | ~10 | اتصال PostgreSQL/SQLite |
| **پرداخت** | ~100 | تنظیمات ۹ سیستم پرداخت |
| **اشتراک** | ~30 | قیمت‌گذاری، ترافیک، دستگاه |
| **ارجاع** | ~10 | کمیسیون و پاداش |
| **مانیتورینگ** | ~15 | نظارت و تعمیرات |
| **API وب** | ~15 | تنظیمات REST API |
| **بکاپ** | ~10 | پشتیبان‌گیری خودکار |

## مدل‌های داده

### مدل‌های اصلی (SQLAlchemy)

| مدل | توضیح | روابط |
|-----|-------|-------|
| `User` | کاربران | subscriptions, transactions |
| `Subscription` | اشتراک‌ها | user, server_squad |
| `Transaction` | تراکنش‌ها | user, payments |
| `ServerSquad` | سرورها | subscriptions, promo_groups |
| `PromoCode` | کدهای تخفیف | usages |
| `PromoGroup` | گروه‌های تخفیف | users, squads |
| `Ticket` | تیکت‌های پشتیبانی | user, messages |

### مدل‌های پرداخت

| مدل | سیستم پرداخت |
|-----|-------------|
| `YooKassaPayment` | YooKassa |
| `CryptoBotPayment` | CryptoBot |
| `HeleketPayment` | Heleket |
| `TributePayment` | Tribute |
| `Pal24Payment` | PayPalych |
| `WataPayment` | WATA |
| `PlategaPayment` | Platega |

### Enums

```python
class UserStatus(Enum):
    ACTIVE, BLOCKED, DELETED

class SubscriptionStatus(Enum):
    TRIAL, ACTIVE, EXPIRED, DISABLED, PENDING

class TransactionType(Enum):
    DEPOSIT, WITHDRAWAL, SUBSCRIPTION_PAYMENT, REFUND, REFERRAL_REWARD

class PaymentMethod(Enum):
    TELEGRAM_STARS, TRIBUTE, YOOKASSA, CRYPTOBOT,
    HELEKET, MULENPAY, PAL24, WATA, PLATEGA, MANUAL
```

## عملکرد و مقیاس‌پذیری

### توصیه‌های منابع

| کاربران | RAM | CPU | دیسک |
|---------|-----|-----|------|
| 1,000 | 512MB | 1 vCPU | 10GB |
| 10,000 | 2GB | 2 vCPU | 50GB |
| 50,000 | 4GB | 4 vCPU | 100GB |
| 100,000+ | 8GB+ | 8+ vCPU | 200GB+ |

### بهینه‌سازی‌ها

- **AsyncIO**: تمام عملیات I/O به صورت async
- **Connection Pooling**: استفاده از pool اتصالات دیتابیس
- **Redis Caching**: کش سشن و سبد خرید
- **Background Tasks**: وظایف پس‌زمینه با APScheduler

---

*تولید شده توسط گردش‌کار document-project در 2025-12-25*

