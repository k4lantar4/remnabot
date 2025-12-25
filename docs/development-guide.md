# راهنمای توسعه

## پیش‌نیازها

| ابزار | نسخه | توضیح |
|-------|------|-------|
| **Python** | 3.13+ | آخرین نسخه پایدار |
| **Docker** | 24.0+ | برای استقرار |
| **Docker Compose** | 2.0+ | orchestration |
| **Make** | - | اختیاری، برای دستورات میانبر |
| **PostgreSQL** | 15+ | دیتابیس production |
| **Redis** | 7+ | کش و سشن |

## راه‌اندازی محیط توسعه

### روش ۱: Docker (توصیه شده)

```bash
# 1. کلون کردن مخزن
git clone https://github.com/Fr1ngg/remnawave-bedolaga-telegram-bot.git
cd remnawave-bedolaga-telegram-bot

# 2. ایجاد فایل پیکربندی
cp .env.example .env
nano .env  # ویرایش تنظیمات

# 3. ایجاد دایرکتوری‌ها
mkdir -p ./logs ./data ./data/backups ./data/referral_qr
chmod -R 755 ./logs ./data

# 4. اجرا با Docker Compose
docker compose up -d

# 5. بررسی وضعیت
docker compose ps
docker compose logs -f bot
```

### روش ۲: محیط محلی

```bash
# 1. ایجاد محیط مجازی
python -m venv venv
source venv/bin/activate  # Linux/Mac
# یا
.\venv\Scripts\activate  # Windows

# 2. نصب وابستگی‌ها
pip install -r requirements.txt

# 3. پیکربندی
cp .env.example .env
nano .env

# 4. اجرا
python main.py
```

## ساختار فایل `.env`

### تنظیمات ضروری

```env
# ربات
BOT_TOKEN=1234567890:AABBCCdd...
ADMIN_IDS=123456789,987654321

# دیتابیس (در Docker)
DATABASE_MODE=auto
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=remnawave_bot
POSTGRES_USER=remnawave_user
POSTGRES_PASSWORD=secure_password_123

# Redis
REDIS_URL=redis://redis:6379/0

# Remnawave API
REMNAWAVE_API_URL=https://your-panel.com
REMNAWAVE_API_KEY=your_api_key
```

### حالت‌های دیتابیس

| مقدار `DATABASE_MODE` | توضیح |
|----------------------|-------|
| `auto` | PostgreSQL در Docker، SQLite محلی |
| `postgresql` | همیشه PostgreSQL |
| `sqlite` | همیشه SQLite |

## دستورات Make

```bash
make up              # راه‌اندازی کانتینرها
make down            # توقف کانتینرها
make reload          # ری‌استارت
make reload-follow   # ری‌استارت با لاگ
make logs            # نمایش لاگ‌ها
make test            # اجرای تست‌ها
make help            # نمایش همه دستورات
```

## ساختار پروژه برای توسعه‌دهندگان

```
app/
├── bot.py              # تنظیم و راه‌اندازی ربات
├── config.py           # کلاس Settings با Pydantic
├── states.py           # FSM States برای مکالمات
│
├── handlers/           # هندلرهای ربات (بر اساس ویژگی)
│   ├── admin/          # هندلرهای مدیریت
│   ├── balance/        # مدیریت موجودی
│   ├── subscription/   # مدیریت اشتراک
│   └── ...
│
├── services/           # منطق کسب‌وکار
│   ├── user_service.py
│   ├── subscription_service.py
│   ├── payment_service.py
│   └── ...
│
├── database/
│   ├── models.py       # مدل‌های SQLAlchemy
│   ├── database.py     # اتصال و سشن
│   └── crud/           # عملیات CRUD
│
├── webapi/             # REST API با FastAPI
│   ├── app.py          # اپلیکیشن FastAPI
│   ├── routes/         # روت‌های API
│   └── schemas/        # اسکیماهای Pydantic
│
└── external/           # یکپارچه‌سازی‌های خارجی
    ├── remnawave_api.py
    └── ...payment providers
```

## افزودن ویژگی جدید

### ۱. افزودن هندلر جدید

```python
# app/handlers/my_feature.py
from aiogram import Router
from aiogram.types import Message

router = Router()

@router.message(F.text == "my_command")
async def my_handler(message: Message):
    await message.answer("Hello!")

# در app/handlers/__init__.py ثبت کنید:
from . import my_feature
dp.include_router(my_feature.router)
```

### ۲. افزودن سرویس جدید

```python
# app/services/my_service.py
class MyService:
    async def do_something(self, data: dict):
        # منطق کسب‌وکار
        pass

my_service = MyService()
```

### ۳. افزودن روت API جدید

```python
# app/webapi/routes/my_route.py
from fastapi import APIRouter

router = APIRouter(prefix="/my-route", tags=["my-feature"])

@router.get("/")
async def get_items():
    return {"items": []}

# در app/webapi/app.py ثبت کنید
from .routes import my_route
app.include_router(my_route.router)
```

### ۴. افزودن مدل جدید

```python
# در app/database/models.py
class MyModel(Base):
    __tablename__ = "my_models"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.now())

# سپس مهاجرت ایجاد کنید:
alembic revision --autogenerate -m "Add my_models table"
alembic upgrade head
```

## تست‌نویسی

### ساختار تست‌ها

```
tests/
├── conftest.py              # fixtures عمومی
├── crud/                    # تست‌های CRUD
├── services/               # تست‌های سرویس
├── external/               # تست‌های یکپارچه‌سازی
├── webserver/              # تست‌های API
└── utils/                  # تست‌های ابزارها
```

### اجرای تست‌ها

```bash
# همه تست‌ها
pytest

# با پوشش کد
pytest --cov=app

# فقط یک ماژول
pytest tests/services/

# با جزئیات
pytest -v

# در Docker
make test
```

### نوشتن تست

```python
# tests/services/test_my_service.py
import pytest
from app.services.my_service import my_service

@pytest.fixture
def sample_data():
    return {"key": "value"}

@pytest.mark.asyncio
async def test_do_something(sample_data):
    result = await my_service.do_something(sample_data)
    assert result is not None
```

## مهاجرت دیتابیس

```bash
# ایجاد مهاجرت جدید
alembic revision --autogenerate -m "Description of changes"

# اجرای مهاجرت‌ها
alembic upgrade head

# برگشت به نسخه قبل
alembic downgrade -1

# نمایش وضعیت
alembic current
alembic history
```

## لاگ‌گیری

```python
import logging

logger = logging.getLogger(__name__)

# استفاده
logger.info("Message")
logger.warning("Warning message")
logger.error("Error: %s", error)
```

### سطوح لاگ (تنظیم در `.env`)

```env
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
LOG_FILE=logs/bot.log
```

## بهترین شیوه‌ها

### ۱. استفاده از AsyncIO

```python
# ✅ صحیح
async def get_user(user_id: int):
    async with get_session() as session:
        return await session.get(User, user_id)

# ❌ اشتباه
def get_user_sync(user_id: int):
    # عملیات همزمان در محیط async
    pass
```

### ۲. مدیریت خطا

```python
from aiogram.types import Message

async def handler(message: Message):
    try:
        await do_something()
    except SomeError as e:
        logger.error("Error: %s", e)
        await message.answer("خطایی رخ داد")
```

### ۳. استفاده از Transaction

```python
async with get_session() as session:
    async with session.begin():
        user = await session.get(User, user_id)
        user.balance_kopeks += amount
        # commit خودکار در پایان
```

### ۴. Type Hints

```python
from typing import Optional, List

async def get_users(
    status: Optional[str] = None,
    limit: int = 100
) -> List[User]:
    ...
```

## عیب‌یابی

### مشکلات رایج

| مشکل | راه‌حل |
|------|--------|
| ربات پاسخ نمی‌دهد | بررسی `BOT_TOKEN` و لاگ‌ها |
| خطای دیتابیس | بررسی اتصال PostgreSQL/SQLite |
| webhook کار نمی‌کند | بررسی `WEBHOOK_URL` و SSL |
| API در دسترس نیست | بررسی `WEB_API_ENABLED=true` |

### دستورات مفید

```bash
# لاگ‌های ربات
docker compose logs -f bot

# وضعیت کانتینرها
docker compose ps

# ورود به شل کانتینر
docker compose exec bot bash

# اتصال به دیتابیس
docker compose exec postgres psql -U remnawave_user -d remnawave_bot

# تست Redis
docker compose exec redis redis-cli ping
```

## Health Checks

```bash
# وضعیت کلی
curl http://localhost:8080/health/unified

# وضعیت webhook تلگرام
curl http://localhost:8080/health/telegram-webhook

# وضعیت پرداخت‌ها
curl http://localhost:8080/health/payment-webhooks
```

---

*تولید شده توسط گردش‌کار document-project در 2025-12-25*

