# نقشه راه تبدیل به سیستم چندمستاجری (Multi-Tenant)

## 📋 خلاصه اجرایی

**هدف:** تبدیل ربات تک‌مستاجری به سیستم چندمستاجری با قابلیت‌های زیر:
- ربات اصلی به عنوان درگاه مادر برای کاربران عادی
- سیستم دریافت ربات‌های جدید با API Token اختصاصی
- ساختار دیتابیس چندمستاجری با روابط صحیح
- دو روش پرداخت: کارت به کارت و زرین‌پال
- پلن‌های اختصاصی برای هر مستاجر

**تاریخ ایجاد:** 2025-12-12  
**وضعیت:** در حال تحلیل

---

## 🎯 اهداف کسب‌وکار

### چرا چندمستاجری؟
1. **مقیاس‌پذیری:** امکان ارائه سرویس به چندین ربات مستقل
2. **جداسازی داده:** هر مستاجر داده‌های مستقل خود را دارد
3. **سفارشی‌سازی:** هر مستاجر می‌تواند پلن‌ها و تنظیمات خود را داشته باشد
4. **درآمدزایی:** امکان ارائه پلتفرم به سایر کسب‌وکارها

### الزامات کلیدی
- ✅ هر مستاجر (ربات) باید API Token اختصاصی داشته باشد
- ✅ ربات اصلی به عنوان درگاه مادر باقی بماند
- ✅ هر مستاجر می‌تواند پلن‌های اختصاصی تعریف کند
- ✅ دو روش پرداخت: کارت به کارت + زرین‌پال
- ✅ فلو کامل پرداخت کارت به کارت با دریافت رسید

---

## 🔍 تحلیل وضعیت فعلی

### معماری فعلی
- **نوع:** Monolith Backend (Python)
- **پترن:** Service-Oriented Architecture (Layered)
- **دیتابیس:** PostgreSQL 15+ (SQLite برای dev)
- **فریمورک:** aiogram 3.22, FastAPI 0.115

### مدل‌های دیتابیس فعلی (بدون چندمستاجری)
```
User (telegram_id unique)
  └─ Subscription (user_id unique)
  └─ Transaction (user_id)
  └─ Ticket (user_id)
  └─ PromoGroup (user_id)
```

### نقاط تغییر کلیدی
1. **Bot Token:** فعلاً یک `BOT_TOKEN` در config
2. **User Model:** بدون `bot_id` - همه کاربران در یک ربات
3. **Subscription:** بدون `bot_id` - همه اشتراک‌ها در یک ربات
4. **Transaction:** بدون `bot_id` - همه تراکنش‌ها در یک ربات
5. **Payment Methods:** تنظیمات پرداخت سراسری (نه per-bot)
6. **Plans:** قیمت‌ها و پلن‌ها سراسری (نه per-bot)

---

## 🏗️ طراحی معماری جدید

### 1. مدل دیتابیس چندمستاجری

#### جدول جدید: `bots` (Tenants)
```sql
CREATE TABLE bots (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    telegram_bot_token VARCHAR(255) UNIQUE NOT NULL,
    api_token VARCHAR(255) UNIQUE NOT NULL,  -- برای دسترسی API
    api_token_hash VARCHAR(255) NOT NULL,   -- hash شده برای امنیت
    is_master BOOLEAN DEFAULT FALSE,        -- ربات اصلی/مادر
    is_active BOOLEAN DEFAULT TRUE,
    
    -- تنظیمات پرداخت کارت به کارت
    card_to_card_enabled BOOLEAN DEFAULT FALSE,
    card_number VARCHAR(50),
    card_holder_name VARCHAR(255),
    card_receipt_topic_id INTEGER,          -- Topic ID برای ارسال نوتیف رسید
    
    -- تنظیمات زرین‌پال
    zarinpal_enabled BOOLEAN DEFAULT FALSE,
    zarinpal_merchant_id VARCHAR(255),
    zarinpal_sandbox BOOLEAN DEFAULT FALSE,
    
    -- تنظیمات عمومی
    default_language VARCHAR(5) DEFAULT 'fa',
    support_username VARCHAR(255),
    admin_chat_id BIGINT,
    admin_topic_id INTEGER,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bots_api_token_hash ON bots(api_token_hash);
CREATE INDEX idx_bots_telegram_token ON bots(telegram_bot_token);
```

#### تغییرات در جدول `users`
```sql
ALTER TABLE users 
    ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
    DROP CONSTRAINT users_telegram_id_key;  -- حذف unique constraint قبلی

-- ایجاد unique constraint جدید: telegram_id + bot_id
CREATE UNIQUE INDEX idx_users_telegram_bot ON users(telegram_id, bot_id);
```

#### تغییرات در سایر جداول
```sql
-- همه جداول اصلی باید bot_id داشته باشند
ALTER TABLE subscriptions ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;
ALTER TABLE transactions ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;
ALTER TABLE tickets ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;
ALTER TABLE promo_groups ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;
ALTER TABLE server_squads ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;
ALTER TABLE promocodes ADD COLUMN bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE;

-- و سایر جداول مرتبط...
```

### 2. مدل جدید: `bot_plans` (پلن‌های اختصاصی هر مستاجر)
```sql
CREATE TABLE bot_plans (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    period_days INTEGER NOT NULL,
    price_kopeks INTEGER NOT NULL,
    traffic_limit_gb INTEGER DEFAULT 0,  -- 0 = unlimited
    device_limit INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_bot_plans_bot_id ON bot_plans(bot_id);
```

### 3. مدل جدید: `card_to_card_payments` (پرداخت کارت به کارت)
```sql
CREATE TABLE card_to_card_payments (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    transaction_id INTEGER REFERENCES transactions(id),
    
    amount_kopeks INTEGER NOT NULL,
    tracking_number VARCHAR(50) UNIQUE NOT NULL,  -- شماره پیگیری
    
    -- اطلاعات رسید
    receipt_type VARCHAR(20),  -- 'image', 'text', 'both'
    receipt_text TEXT,
    receipt_image_file_id VARCHAR(255),  -- Telegram file_id
    
    -- وضعیت
    status VARCHAR(20) DEFAULT 'pending',  -- pending, approved, rejected, cancelled
    admin_reviewed_by INTEGER REFERENCES users(id),
    admin_reviewed_at TIMESTAMP,
    admin_notes TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_card_payments_bot_user ON card_to_card_payments(bot_id, user_id);
CREATE INDEX idx_card_payments_tracking ON card_to_card_payments(tracking_number);
CREATE INDEX idx_card_payments_status ON card_to_card_payments(status);
```

### 4. مدل جدید: `zarinpal_payments` (پرداخت زرین‌پال)
```sql
CREATE TABLE zarinpal_payments (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER REFERENCES bots(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    transaction_id INTEGER REFERENCES transactions(id),
    
    amount_kopeks INTEGER NOT NULL,
    zarinpal_authority VARCHAR(255) UNIQUE,  -- Authority از زرین‌پال
    zarinpal_ref_id VARCHAR(255),             -- RefID پس از پرداخت موفق
    status VARCHAR(20) DEFAULT 'pending',    -- pending, paid, failed, cancelled
    
    callback_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_zarinpal_bot_user ON zarinpal_payments(bot_id, user_id);
CREATE INDEX idx_zarinpal_authority ON zarinpal_payments(zarinpal_authority);
```

---

## 🔄 فلو پرداخت کارت به کارت

### مراحل فلو:
1. **کاربر گزینه پرداخت کارت به کارت را انتخاب می‌کند**
   - ربات متن تمپلیت با شماره کارت و نام دارنده کارت را نمایش می‌دهد
   - این اطلاعات از `bots.card_number` و `bots.card_holder_name` خوانده می‌شود

2. **کاربر رسید را ارسال می‌کند**
   - می‌تواند تصویر، متن، یا هر دو ارسال کند
   - ربات رسید را دریافت و ذخیره می‌کند
   - یک شماره پیگیری منحصر به فرد به کاربر داده می‌شود

3. **ارسال نوتیف به ادمین**
   - رسید به همراه دکمه‌های "تایید" و "رد" به Topic تنظیم شده (`bots.card_receipt_topic_id`) ارسال می‌شود
   - شامل اطلاعات: کاربر، مبلغ، شماره پیگیری، رسید

4. **بررسی و تایید/رد توسط ادمین**
   - ادمین رسید را بررسی می‌کند
   - در صورت تایید: تراکنش تکمیل می‌شود، سفارش ثبت می‌شود
   - در صورت رد: به کاربر اطلاع داده می‌شود

5. **ثبت سفارش**
   - پس از تایید پرداخت، سفارش (Subscription) ثبت می‌شود
   - به کاربر اطلاع داده می‌شود

---

## 🔄 فلو پرداخت زرین‌پال

### مراحل فلو:
1. **کاربر گزینه پرداخت زرین‌پال را انتخاب می‌کند**
2. **ایجاد درخواست پرداخت**
   - ارسال درخواست به API زرین‌پال
   - دریافت `authority` و `payment_url`
3. **هدایت کاربر به درگاه**
   - کاربر به `payment_url` هدایت می‌شود
4. **بازگشت از درگاه (Callback)**
   - پس از پرداخت، زرین‌پال به callback URL ما redirect می‌کند
   - بررسی `authority` و دریافت `ref_id`
5. **تایید پرداخت و ثبت سفارش**
   - در صورت موفقیت: تراکنش تکمیل، سفارش ثبت
   - در صورت شکست: به کاربر اطلاع داده می‌شود

---

## 📦 تغییرات کد

### 1. مدل‌های دیتابیس (`app/database/models.py`)

#### مدل جدید: `Bot`
```python
class Bot(Base):
    __tablename__ = "bots"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    telegram_bot_token = Column(String(255), unique=True, nullable=False, index=True)
    api_token = Column(String(255), unique=True, nullable=False)
    api_token_hash = Column(String(255), nullable=False, index=True)
    is_master = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    
    # Card-to-card settings
    card_to_card_enabled = Column(Boolean, default=False)
    card_number = Column(String(50), nullable=True)
    card_holder_name = Column(String(255), nullable=True)
    card_receipt_topic_id = Column(Integer, nullable=True)
    
    # Zarinpal settings
    zarinpal_enabled = Column(Boolean, default=False)
    zarinpal_merchant_id = Column(String(255), nullable=True)
    zarinpal_sandbox = Column(Boolean, default=False)
    
    # General settings
    default_language = Column(String(5), default='fa')
    support_username = Column(String(255), nullable=True)
    admin_chat_id = Column(BigInteger, nullable=True)
    admin_topic_id = Column(Integer, nullable=True)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    users = relationship("User", back_populates="bot")
    subscriptions = relationship("Subscription", back_populates="bot")
    transactions = relationship("Transaction", back_populates="bot")
    # ... سایر روابط
```

#### تغییرات در `User`
```python
class User(Base):
    # ... فیلدهای موجود
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Relationship
    bot = relationship("Bot", back_populates="users")
    
    # Unique constraint: telegram_id + bot_id
    __table_args__ = (
        UniqueConstraint('telegram_id', 'bot_id', name='uq_user_telegram_bot'),
    )
```

### 2. تغییرات در `app/bot.py`

#### پشتیبانی از چند ربات
```python
# به جای یک bot، باید یک dictionary از bots داشته باشیم
active_bots: Dict[int, Bot] = {}  # bot_id -> Bot instance
active_dispatchers: Dict[int, Dispatcher] = {}  # bot_id -> Dispatcher

async def setup_bot(bot_config: Bot) -> tuple[Bot, Dispatcher]:
    """Setup a single bot instance"""
    bot = Bot(
        token=bot_config.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # ... setup dispatcher, middlewares, handlers
    
    return bot, dp

async def initialize_all_bots():
    """Initialize all active bots from database"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Bot).where(Bot.is_active == True)
        )
        bots = result.scalars().all()
        
        for bot_config in bots:
            bot, dp = await setup_bot(bot_config)
            active_bots[bot_config.id] = bot
            active_dispatchers[bot_config.id] = dp
```

### 3. Middleware جدید: `BotContextMiddleware`

```python
class BotContextMiddleware(BaseMiddleware):
    """Middleware to inject bot context into handlers"""
    
    async def __call__(
        self,
        handler: Callable,
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # تشخیص bot_id از event
        # اضافه کردن bot context به data
        data['bot_id'] = current_bot_id
        data['bot'] = current_bot_instance
        return await handler(event, data)
```

### 4. تغییرات در Services

#### `PaymentService` - پشتیبانی از چندمستاجری
```python
class PaymentService:
    async def process_card_to_card_payment(
        self,
        db: AsyncSession,
        bot_id: int,
        user_id: int,
        amount_kopeks: int,
        receipt_data: Dict[str, Any]
    ) -> CardToCardPayment:
        """Process card-to-card payment with receipt"""
        # ایجاد payment record
        # تولید tracking number
        # ارسال نوتیف به ادمین
        pass
    
    async def process_zarinpal_payment(
        self,
        db: AsyncSession,
        bot_id: int,
        user_id: int,
        amount_kopeks: int
    ) -> ZarinpalPayment:
        """Process Zarinpal payment"""
        # ایجاد payment request
        # ارسال به زرین‌پال API
        pass
```

### 5. Handler جدید: پرداخت کارت به کارت

```python
# app/handlers/payment/card_to_card.py

async def handle_card_to_card_selection(
    callback: types.CallbackQuery,
    db_user: User,
    state: FSMContext
):
    """نمایش اطلاعات کارت و درخواست رسید"""
    bot = await get_bot_by_id(db_user.bot_id)
    
    card_info = f"""
💳 پرداخت کارت به کارت

شماره کارت: {bot.card_number}
دارنده کارت: {bot.card_holder_name}

لطفاً رسید پرداخت را ارسال کنید.
می‌توانید تصویر، متن، یا هر دو ارسال کنید.
"""
    
    await callback.message.answer(card_info)
    await state.set_state(CardToCardPaymentState.waiting_for_receipt)

async def handle_receipt_received(
    message: types.Message,
    db_user: User,
    state: FSMContext
):
    """دریافت و ذخیره رسید"""
    # استخراج receipt (image/text)
    # ایجاد CardToCardPayment record
    # تولید tracking number
    # ارسال نوتیف به ادمین
    pass

async def handle_payment_approval(
    callback: types.CallbackQuery,
    payment_id: int
):
    """تایید پرداخت توسط ادمین"""
    # تایید payment
    # تکمیل transaction
    # ثبت سفارش
    pass
```

### 6. یکپارچه‌سازی زرین‌پال

```python
# app/external/zarinpal.py

class ZarinpalClient:
    def __init__(self, merchant_id: str, sandbox: bool = False):
        self.merchant_id = merchant_id
        self.sandbox = sandbox
        self.base_url = "https://sandbox.zarinpal.com" if sandbox else "https://api.zarinpal.com"
    
    async def create_payment_request(
        self,
        amount: int,  # به تومان
        callback_url: str,
        description: str
    ) -> Dict[str, Any]:
        """ایجاد درخواست پرداخت"""
        # ارسال درخواست به زرین‌پال
        pass
    
    async def verify_payment(
        self,
        authority: str,
        amount: int
    ) -> Dict[str, Any]:
        """تایید پرداخت"""
        # تایید پرداخت با زرین‌پال
        pass
```

---

## 🔐 سیستم API Token

### ایجاد و مدیریت Token
```python
# app/services/bot_service.py

class BotService:
    @staticmethod
    def generate_api_token() -> str:
        """تولید API token جدید"""
        import secrets
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def hash_api_token(token: str) -> str:
        """Hash کردن token برای ذخیره امن"""
        import hashlib
        return hashlib.sha256(token.encode()).hexdigest()
    
    async def create_bot(
        self,
        db: AsyncSession,
        name: str,
        telegram_bot_token: str,
        **kwargs
    ) -> Bot:
        """ایجاد ربات جدید"""
        api_token = self.generate_api_token()
        api_token_hash = self.hash_api_token(api_token)
        
        bot = Bot(
            name=name,
            telegram_bot_token=telegram_bot_token,
            api_token=api_token,  # فقط یکبار نمایش می‌شود
            api_token_hash=api_token_hash,
            **kwargs
        )
        
        db.add(bot)
        await db.commit()
        await db.refresh(bot)
        
        return bot  # api_token در response برگردانده می‌شود
```

### Authentication Middleware برای API
```python
# app/webapi/middleware.py

async def verify_api_token(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
) -> Bot:
    """بررسی و اعتبارسنجی API token"""
    api_token = request.headers.get("X-API-Token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    
    if not api_token:
        raise HTTPException(status_code=401, detail="API token required")
    
    token_hash = BotService.hash_api_token(api_token)
    
    result = await db.execute(
        select(Bot).where(Bot.api_token_hash == token_hash, Bot.is_active == True)
    )
    bot = result.scalar_one_or_none()
    
    if not bot:
        raise HTTPException(status_code=401, detail="Invalid API token")
    
    return bot
```

---

## 📊 Migration Strategy

### مرحله 1: آماده‌سازی
1. ✅ ایجاد مدل `Bot` در دیتابیس
2. ✅ ایجاد migration برای اضافه کردن `bot_id` به جداول موجود
3. ✅ ایجاد ربات اصلی (master) در دیتابیس

### مرحله 2: Migration داده‌های موجود
```python
# Migration script: migrate_to_multi_tenant.py

async def migrate_existing_data():
    """تبدیل داده‌های موجود به چندمستاجری"""
    async with AsyncSessionLocal() as session:
        # 1. ایجاد ربات اصلی
        master_bot = Bot(
            name="Master Bot",
            telegram_bot_token=settings.BOT_TOKEN,
            api_token=BotService.generate_api_token(),
            is_master=True,
            is_active=True
        )
        session.add(master_bot)
        await session.flush()
        
        # 2. اختصاص همه کاربران به ربات اصلی
        await session.execute(
            update(User).values(bot_id=master_bot.id)
        )
        
        # 3. اختصاص همه subscriptions به ربات اصلی
        await session.execute(
            update(Subscription).values(bot_id=master_bot.id)
        )
        
        # 4. و سایر جداول...
        
        await session.commit()
```

### مرحله 3: تغییرات کد
1. تغییر `app/bot.py` برای پشتیبانی چند ربات
2. اضافه کردن `BotContextMiddleware`
3. تغییر همه handlers برای استفاده از `bot_id`
4. تغییر services برای پشتیبانی چندمستاجری
5. اضافه کردن handlers پرداخت کارت به کارت
6. یکپارچه‌سازی زرین‌پال

### مرحله 4: تست
1. تست ربات اصلی
2. تست ایجاد ربات جدید
3. تست پرداخت کارت به کارت
4. تست پرداخت زرین‌پال
5. تست API Token

---

## ⚠️ ریسک‌ها و چالش‌ها

### ریسک‌های فنی
1. **Migration داده‌ها:** باید با دقت انجام شود تا داده‌ها از دست نروند
2. **Performance:** اضافه شدن `bot_id` به همه queries ممکن است performance را تحت تاثیر قرار دهد
3. **Backward Compatibility:** باید مطمئن شویم کدهای قدیمی همچنان کار می‌کنند

### راه‌حل‌ها
1. **Backup قبل از Migration:** حتماً backup کامل بگیرید
2. **Indexing:** ایجاد index مناسب روی `bot_id` در همه جداول
3. **Gradual Rollout:** به صورت تدریجی rollout کنید

---

## 📝 چک‌لیست پیاده‌سازی

### فاز 1: پایه چندمستاجری
- [ ] ایجاد مدل `Bot` در دیتابیس
- [ ] Migration برای اضافه کردن `bot_id` به جداول
- [ ] تغییر `User` model
- [ ] تغییر `Subscription` model
- [ ] تغییر `Transaction` model
- [ ] تغییر سایر models مرتبط
- [ ] Migration script برای داده‌های موجود

### فاز 2: Bot Management
- [ ] `BotService` برای مدیریت ربات‌ها
- [ ] API endpoints برای ایجاد/ویرایش/حذف ربات
- [ ] سیستم API Token
- [ ] Authentication middleware

### فاز 3: Multi-Bot Support
- [ ] تغییر `app/bot.py` برای پشتیبانی چند ربات
- [ ] `BotContextMiddleware`
- [ ] تغییر handlers برای استفاده از `bot_id`
- [ ] تغییر services

### فاز 4: پرداخت کارت به کارت
- [ ] مدل `CardToCardPayment`
- [ ] Handler برای انتخاب پرداخت کارت به کارت
- [ ] Handler برای دریافت رسید
- [ ] سیستم ارسال نوتیف به ادمین
- [ ] Handler برای تایید/رد پرداخت
- [ ] ثبت سفارش پس از تایید

### فاز 5: پرداخت زرین‌پال
- [ ] مدل `ZarinpalPayment`
- [ ] `ZarinpalClient` برای ارتباط با API
- [ ] Handler برای ایجاد درخواست پرداخت
- [ ] Callback handler برای بازگشت از درگاه
- [ ] تایید پرداخت و ثبت سفارش

### فاز 6: پلن‌های اختصاصی
- [ ] مدل `BotPlan`
- [ ] CRUD operations برای پلن‌ها
- [ ] تغییر `SubscriptionService` برای استفاده از `BotPlan`
- [ ] API endpoints برای مدیریت پلن‌ها

### فاز 7: تست و مستندسازی
- [ ] Unit tests
- [ ] Integration tests
- [ ] تست migration
- [ ] مستندسازی API
- [ ] راهنمای استفاده

---

## 🚀 مراحل بعدی

1. **تایید طراحی:** بررسی و تایید این نقشه راه
2. **شروع پیاده‌سازی:** شروع از فاز 1
3. **Review دوره‌ای:** بررسی پیشرفت در هر فاز

---

## 📚 منابع و مراجع

- [Zarinpal API Documentation](https://docs.zarinpal.com/)
- [aiogram Multi-Bot Guide](https://docs.aiogram.dev/en/latest/dispatcher/multi-bot.html)
- [SQLAlchemy Multi-Tenancy Patterns](https://docs.sqlalchemy.org/en/20/orm/examples.html#module-examples.vertical_sharding)

---

**نکته:** این سند یک سند زنده است و در طول پیاده‌سازی به‌روزرسانی می‌شود.














