# 📚 مستندات پروژه Remnawave Bedolaga Bot

## 🎯 خلاصه پروژه

| ویژگی | مقدار |
|-------|-------|
| **نام** | Remnawave Bedolaga Bot |
| **نوع** | Backend (ربات تلگرام + REST API) |
| **زبان** | Python 3.13+ |
| **معماری** | Monolith با Service-Oriented Architecture |
| **فریم‌ورک‌ها** | aiogram 3, FastAPI, SQLAlchemy |
| **دیتابیس** | PostgreSQL 15+ / SQLite |
| **استقرار** | Docker + Docker Compose |

## 📖 مرجع سریع

### پشته فناوری
- **ربات تلگرام:** aiogram 3.22.0
- **REST API:** FastAPI 0.115.6
- **ORM:** SQLAlchemy 2.0.43
- **کش:** Redis 5.0.1
- **زمان‌بندی:** APScheduler 3.11.0

### نقاط ورود
- **اصلی:** `main.py`
- **ربات:** `app/bot.py`
- **API:** `app/webapi/app.py`
- **پورت:** 8080

---

## 📁 مستندات تولیدشده

### معماری و ساختار

| سند | توضیح |
|-----|-------|
| [ساختار پروژه](./project-structure.md) | درخت منبع و سازماندهی کد |
| [پشته فناوری](./technology-stack.md) | فناوری‌ها، وابستگی‌ها و معماری |
| [مدل‌های داده](./data-models.md) | جداول SQLAlchemy و روابط |
| [قراردادهای API](./api-contracts.md) | مستندات REST API با ۱۵۰+ endpoint |

### راهنماها

| سند | توضیح |
|-----|-------|
| [راهنمای توسعه](./development-guide.md) | راه‌اندازی محیط، تست و بهترین شیوه‌ها |
| [موجودی مستندات](./existing-documentation-inventory.md) | لیست مستندات موجود |

---

## 📁 مستندات موجود

### راهنماهای اصلی (ریشه پروژه)

| سند | توضیح |
|-----|-------|
| [README.md](../README.md) | راهنمای جامع پروژه - نصب، پیکربندی، استفاده |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | راهنمای مشارکت |
| [SECURITY.md](../SECURITY.md) | سیاست امنیتی |

### مستندات فنی

| سند | موضوع |
|-----|-------|
| [contests-api.md](./contests-api.md) | API مسابقات |
| [menu_stats_api_usage.md](./menu_stats_api_usage.md) | استفاده از API آمار منو |
| [miniapp-setup.md](./miniapp-setup.md) | راه‌اندازی Mini App تلگرام |
| [persistent_cart_system.md](./persistent_cart_system.md) | سیستم سبد خرید پایدار |
| [project_structure_reference.md](./project_structure_reference.md) | مرجع ساختار پروژه |
| [referral_program_setting.md](./referral_program_setting.md) | تنظیمات برنامه ارجاع |
| [web-admin-integration.md](./web-admin-integration.md) | یکپارچه‌سازی پنل مدیریت وب |

---

## 🚀 شروع سریع

### برای توسعه‌دهندگان

```bash
# 1. کلون مخزن
git clone https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot.git
cd remnawave-bedolaga-telegram-bot

# 2. پیکربندی
cp .env.example .env
nano .env

# 3. راه‌اندازی با Docker
make up

# 4. بررسی وضعیت
docker compose logs -f bot
```

### برای ویژگی‌های جدید

1. **فقط ربات:** مرجع `app/handlers/` و `app/services/`
2. **فقط API:** مرجع `app/webapi/routes/` و `api-contracts.md`
3. **دیتابیس:** مرجع `data-models.md` و `app/database/`
4. **پرداخت:** مرجع `app/external/` و `app/services/payment_service.py`

---

## 🔗 لینک‌های مفید

### توسعه

- **Health Check:** `http://localhost:8080/health`
- **API Docs:** `http://localhost:8080/docs` (اگر فعال باشد)
- **لاگ‌ها:** `./logs/bot.log`

### منابع خارجی

- [مستندات Remnawave](https://docs.remna.st)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [aiogram Documentation](https://docs.aiogram.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)

---

## 📊 آمار پروژه

| معیار | مقدار |
|-------|-------|
| **سرویس‌های پشته فناوری** | ۱۵+ |
| **سیستم‌های پرداخت** | ۹ (Stars, YooKassa, CryptoBot, Heleket, Tribute, MulenPay, Pal24, Platega, WATA) |
| **ماژول‌های API** | ۳۲ |
| **جداول دیتابیس** | ۳۵+ |
| **فایل‌های سرویس** | ۶۸ |
| **هندلرهای ربات** | ۶۰+ |
| **مهاجرت‌های Alembic** | ۱۲ |

---

## 📅 اطلاعات تولید

| فیلد | مقدار |
|------|-------|
| **تاریخ تولید** | 2025-12-25 |
| **حالت اسکن** | exhaustive |
| **نسخه گردش‌کار** | 1.2.0 |
| **فایل وضعیت** | [project-scan-report.json](./project-scan-report.json) |

---

*این مستندات توسط گردش‌کار BMAD document-project تولید شده است.*
*برای بروزرسانی، گردش‌کار را مجدداً اجرا کنید.*

