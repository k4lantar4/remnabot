# Detailed Implementation Guide - Multi-Tenant Migration

**Version:** 2.0  
**Date:** 2025-12-14  
**Status:** Ready for AI-Assisted Implementation

---

## 🎯 هدف این راهنما

این راهنما دستورالعمل‌های **step-by-step** و **copy-paste ready** برای پیاده‌سازی کامل migration به multi-tenant را فراهم می‌کند. هر increment شامل:

- ✅ **دستورالعمل‌های دقیق** (خط به خط)
- ✅ **کدهای آماده** (copy-paste)
- ✅ **Acceptance Criteria کامل** (قابل تست)
- ✅ **Test Commands** (برای verification)
- ✅ **Troubleshooting** (راهنمای حل مشکل)

**استفاده:** این راهنما برای AI Assistant (مثل Cursor AI) طراحی شده تا بتواند بدون نیاز به تفکر، فقط دستورات را دنبال کند.

---

## 📋 Phase 1: Foundation

### Increment 1.1: Database Schema - New Tables

**Status:** ✅ **COMPLETED**  
**Priority:** 🔴 Critical  
**Time:** 2 hours  
**Dependencies:** None  
**Files to Create:** `migrations/001_create_multi_tenant_tables.sql`

#### Step-by-Step Instructions

**Step 1: Create Migration File**

```bash
# Create migrations directory if it doesn't exist
mkdir -p migrations

# Create migration file
touch migrations/001_create_multi_tenant_tables.sql
```

**Step 2: Add SQL to File**

Copy the complete SQL from `docs/multi-tenant/01-database-schema.md` sections:
- `bots` table (lines 26-67)
- `bot_feature_flags` table (lines 82-96)
- `bot_configurations` table (lines 113-125)
- `tenant_payment_cards` table (lines 134-155)
- `bot_plans` table (lines 170-187)
- `card_to_card_payments` table (lines 196-219)
- `zarinpal_payments` table (lines 228-245)

**Step 3: Run Migration on Test Database**

```bash
# Create test database if it doesn't exist
createdb remnawave_bot_test

# Run migration
psql remnawave_bot_test < migrations/001_create_multi_tenant_tables.sql
```

**Step 4: Verify Tables Created**

```sql
-- Connect to test database
psql remnawave_bot_test

-- Check all 7 tables exist
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN (
    'bots', 
    'bot_feature_flags', 
    'bot_configurations', 
    'tenant_payment_cards', 
    'bot_plans', 
    'card_to_card_payments', 
    'zarinpal_payments'
);

-- Should return 7 rows
```

**Step 5: Verify Indexes**

```sql
-- Check indexes for bots table
SELECT indexname 
FROM pg_indexes 
WHERE tablename = 'bots';

-- Should return: idx_bots_api_token_hash, idx_bots_telegram_token, idx_bots_is_master, idx_bots_is_active

-- Check indexes for other tables
SELECT tablename, indexname 
FROM pg_indexes 
WHERE tablename IN ('bot_feature_flags', 'bot_configurations', 'tenant_payment_cards', 'bot_plans', 'card_to_card_payments', 'zarinpal_payments')
ORDER BY tablename, indexname;
```

**Step 6: Test Foreign Keys**

```sql
-- Test foreign key constraint on bot_feature_flags
INSERT INTO bots (name, telegram_bot_token, api_token, api_token_hash) 
VALUES ('Test Bot', 'test_token', 'test_api_token', 'test_hash');

-- Get bot_id
SELECT id FROM bots WHERE name = 'Test Bot';

-- Insert feature flag (should work)
INSERT INTO bot_feature_flags (bot_id, feature_key, enabled) 
VALUES ((SELECT id FROM bots WHERE name = 'Test Bot'), 'test_feature', true);

-- Try to insert with invalid bot_id (should fail)
INSERT INTO bot_feature_flags (bot_id, feature_key, enabled) 
VALUES (99999, 'test_feature', true);
-- Expected: ERROR: insert or update on table "bot_feature_flags" violates foreign key constraint

-- Cleanup
DELETE FROM bot_feature_flags WHERE bot_id = (SELECT id FROM bots WHERE name = 'Test Bot');
DELETE FROM bots WHERE name = 'Test Bot';
```

#### Acceptance Criteria

- ✅ All 7 tables created successfully
- ✅ All indexes created (verify count matches expected)
- ✅ Foreign keys working (test insert with invalid bot_id fails)
- ✅ No errors in migration script
- ✅ Test database migration successful

#### Troubleshooting

**Error: "relation already exists"**
- Solution: Drop tables first: `DROP TABLE IF EXISTS bots CASCADE;` (repeat for all 7 tables)

**Error: "permission denied"**
- Solution: Check database user permissions: `\du` in psql

**Error: "syntax error"**
- Solution: Check SQL syntax, ensure all quotes are correct

---

### Increment 1.2: Database Models - New Models

**Status:** ✅ **COMPLETED**  
**Priority:** 🔴 Critical  
**Time:** 3 hours  
**Dependencies:** Increment 1.1  
**Files to Modify:** `app/database/models.py`

#### Step-by-Step Instructions

**Step 1: Open models.py**

```bash
# Open the file
code app/database/models.py
# Or: vim app/database/models.py
```

**Step 2: Find Insertion Point**

Find line with `Base = declarative_base()` (usually around line 25).

**Step 3: Add Bot Model**

Add after `Base = declarative_base()`:

```python
class Bot(Base):
    __tablename__ = "bots"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    telegram_bot_token = Column(String(255), unique=True, nullable=False, index=True)
    api_token = Column(String(255), unique=True, nullable=False)
    api_token_hash = Column(String(128), nullable=False, index=True)
    is_master = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Card-to-card settings
    card_to_card_enabled = Column(Boolean, default=False, nullable=False)
    card_receipt_topic_id = Column(Integer, nullable=True)
    
    # Zarinpal settings
    zarinpal_enabled = Column(Boolean, default=False, nullable=False)
    zarinpal_merchant_id = Column(String(255), nullable=True)
    zarinpal_sandbox = Column(Boolean, default=False, nullable=False)
    
    # General settings
    default_language = Column(String(5), default='fa', nullable=False)
    support_username = Column(String(255), nullable=True)
    admin_chat_id = Column(BigInteger, nullable=True)
    admin_topic_id = Column(Integer, nullable=True)
    notification_group_id = Column(BigInteger, nullable=True)
    notification_topic_id = Column(Integer, nullable=True)
    
    # Wallet & billing
    wallet_balance_kopeks = Column(BigInteger, default=0, nullable=False)
    traffic_consumed_bytes = Column(BigInteger, default=0, nullable=False)
    traffic_sold_bytes = Column(BigInteger, default=0, nullable=False)
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    users = relationship("User", back_populates="bot", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="bot", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="bot", cascade="all, delete-orphan")
    feature_flags = relationship("BotFeatureFlag", back_populates="bot", cascade="all, delete-orphan")
    configurations = relationship("BotConfiguration", back_populates="bot", cascade="all, delete-orphan")
    payment_cards = relationship("TenantPaymentCard", back_populates="bot", cascade="all, delete-orphan")
    plans = relationship("BotPlan", back_populates="bot", cascade="all, delete-orphan")
    card_payments = relationship("CardToCardPayment", back_populates="bot", cascade="all, delete-orphan")
    zarinpal_payments_rel = relationship("ZarinpalPayment", back_populates="bot", cascade="all, delete-orphan")
```

**Step 4: Add BotFeatureFlag Model**

```python
class BotFeatureFlag(Base):
    __tablename__ = "bot_feature_flags"
    
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    feature_key = Column(String(100), primary_key=True, nullable=False)
    enabled = Column(Boolean, default=False, nullable=False)
    config = Column(JSONB, default={}, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    bot = relationship("Bot", back_populates="feature_flags")
```

**Step 5: Add BotConfiguration Model**

```python
class BotConfiguration(Base):
    __tablename__ = "bot_configurations"
    
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    config_key = Column(String(100), primary_key=True, nullable=False)
    config_value = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    bot = relationship("Bot", back_populates="configurations")
```

**Step 6: Add TenantPaymentCard Model**

```python
class TenantPaymentCard(Base):
    __tablename__ = "tenant_payment_cards"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    card_number = Column(String(50), nullable=False)
    card_holder_name = Column(String(255), nullable=False)
    rotation_strategy = Column(String(20), default='round_robin', nullable=False)
    rotation_interval_minutes = Column(Integer, default=60, nullable=True)
    weight = Column(Integer, default=1, nullable=False)
    success_count = Column(Integer, default=0, nullable=False)
    failure_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    last_used_at = Column(DateTime, nullable=True)
    current_usage_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    bot = relationship("Bot", back_populates="payment_cards")
```

**Step 7: Add BotPlan Model**

```python
class BotPlan(Base):
    __tablename__ = "bot_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    period_days = Column(Integer, nullable=False)
    price_kopeks = Column(Integer, nullable=False)
    traffic_limit_gb = Column(Integer, default=0, nullable=True)
    device_limit = Column(Integer, default=1, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    bot = relationship("Bot", back_populates="plans")
```

**Step 8: Add CardToCardPayment Model**

```python
class CardToCardPayment(Base):
    __tablename__ = "card_to_card_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    card_id = Column(Integer, ForeignKey("tenant_payment_cards.id", ondelete="SET NULL"), nullable=True)
    amount_kopeks = Column(Integer, nullable=False)
    tracking_number = Column(String(50), unique=True, nullable=False, index=True)
    receipt_type = Column(String(20), nullable=True)  # 'image', 'text', 'both'
    receipt_text = Column(Text, nullable=True)
    receipt_image_file_id = Column(String(255), nullable=True)
    status = Column(String(20), default='pending', nullable=False, index=True)  # pending, approved, rejected, cancelled
    admin_reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_reviewed_at = Column(DateTime, nullable=True)
    admin_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    bot = relationship("Bot", back_populates="card_payments")
    user = relationship("User")
    transaction = relationship("Transaction")
    card = relationship("TenantPaymentCard")
```

**Step 9: Add ZarinpalPayment Model**

```python
class ZarinpalPayment(Base):
    __tablename__ = "zarinpal_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
    amount_kopeks = Column(Integer, nullable=False)
    zarinpal_authority = Column(String(255), unique=True, nullable=True, index=True)
    zarinpal_ref_id = Column(String(255), nullable=True)
    status = Column(String(20), default='pending', nullable=False)  # pending, paid, failed, cancelled
    callback_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    bot = relationship("Bot", back_populates="zarinpal_payments_rel")
    user = relationship("User")
    transaction = relationship("Transaction")
```

**Step 10: Update User Model**

Find `User` model and add:

```python
# In User model, add:
bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=True, index=True)

# Update __table_args__ to include composite unique constraint:
__table_args__ = (
    UniqueConstraint('telegram_id', 'bot_id', name='uq_user_telegram_bot'),
)

# Add relationship:
bot = relationship("Bot", back_populates="users")
```

**Step 11: Update Other Models**

For each of these models, add `bot_id` column and relationship:
- `Subscription`
- `Transaction`
- `Ticket`
- `PromoCode`
- `PromoGroup`
- All payment models (yookassa_payments, cryptobot_payments, etc.)

Example pattern:
```python
bot_id = Column(Integer, ForeignKey("bots.id", ondelete="CASCADE"), nullable=True, index=True)
bot = relationship("Bot", back_populates="subscriptions")  # Adjust relationship name
```

**Step 12: Test Imports**

```python
# Create test file: test_models.py
from app.database.models import (
    Bot, BotFeatureFlag, BotConfiguration, TenantPaymentCard,
    BotPlan, CardToCardPayment, ZarinpalPayment, User, Subscription
)

print("All models imported successfully!")
```

Run:
```bash
python test_models.py
```

**Step 13: Test Relationships**

```python
# test_relationships.py
from app.database.models import Bot, BotFeatureFlag

# Test relationship access
bot = Bot()
print(bot.feature_flags)  # Should not error
print("Relationships working!")
```

#### Acceptance Criteria

- ✅ All 7 new models added to models.py
- ✅ All models have correct column definitions matching schema
- ✅ All relationships defined correctly
- ✅ User model updated with bot_id and unique constraint
- ✅ Other models (Subscription, Transaction, etc.) updated with bot_id
- ✅ No import errors when importing models
- ✅ Relationships accessible (test with `bot.feature_flags`)

#### Troubleshooting

**Error: "Cannot find module"**
- Solution: Check import paths, ensure you're in project root

**Error: "Column already exists"**
- Solution: Check if bot_id already added, remove duplicate

**Error: "Relationship error"**
- Solution: Check relationship names match in both models (back_populates)

---

### Increment 1.3: Bot CRUD Operations

**Status:** ✅ **COMPLETED**  
**Priority:** 🔴 Critical  
**Time:** 2 hours  
**Dependencies:** Increment 1.2  
**Files to Create:** `app/database/crud/bot.py`

#### Step-by-Step Instructions

**Step 1: Create CRUD File**

```bash
touch app/database/crud/bot.py
```

**Step 2: Add Imports and Helper Functions**

```python
import secrets
import hashlib
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.database.models import Bot


def generate_api_token() -> str:
    """Generate a secure API token."""
    return secrets.token_urlsafe(32)


def hash_api_token(token: str) -> str:
    """Hash API token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()
```

**Step 3: Add Get Functions**

```python
async def get_bot_by_id(db: AsyncSession, bot_id: int) -> Optional[Bot]:
    """Get bot by ID."""
    result = await db.execute(
        select(Bot).where(Bot.id == bot_id)
    )
    return result.scalar_one_or_none()


async def get_bot_by_token(db: AsyncSession, telegram_token: str) -> Optional[Bot]:
    """Get bot by Telegram bot token."""
    result = await db.execute(
        select(Bot).where(Bot.telegram_bot_token == telegram_token)
    )
    return result.scalar_one_or_none()


async def get_bot_by_api_token(db: AsyncSession, api_token: str) -> Optional[Bot]:
    """Get bot by API token (hashed)."""
    token_hash = hash_api_token(api_token)
    result = await db.execute(
        select(Bot).where(Bot.api_token_hash == token_hash)
    )
    return result.scalar_one_or_none()


async def get_master_bot(db: AsyncSession) -> Optional[Bot]:
    """Get master bot."""
    result = await db.execute(
        select(Bot).where(Bot.is_master == True, Bot.is_active == True)
    )
    return result.scalar_one_or_none()


async def get_active_bots(db: AsyncSession) -> List[Bot]:
    """Get all active bots."""
    result = await db.execute(
        select(Bot).where(Bot.is_active == True)
    )
    return list(result.scalars().all())
```

**Step 4: Add Create Function**

```python
async def create_bot(
    db: AsyncSession,
    name: str,
    telegram_bot_token: str,
    is_master: bool = False,
    is_active: bool = True,
    **kwargs
) -> tuple[Bot, str]:
    """
    Create a new bot.
    Returns: (Bot instance, plain API token)
    """
    # Generate API token
    api_token = generate_api_token()
    api_token_hash = hash_api_token(api_token)
    
    bot = Bot(
        name=name,
        telegram_bot_token=telegram_bot_token,
        api_token=api_token,  # Store plain token temporarily (will be removed after first read)
        api_token_hash=api_token_hash,
        is_master=is_master,
        is_active=is_active,
        **kwargs
    )
    
    db.add(bot)
    await db.commit()
    await db.refresh(bot)
    
    return bot, api_token
```

**Step 5: Add Update Functions**

```python
async def update_bot(
    db: AsyncSession,
    bot_id: int,
    **kwargs
) -> Optional[Bot]:
    """Update bot fields."""
    result = await db.execute(
        update(Bot)
        .where(Bot.id == bot_id)
        .values(**kwargs)
        .returning(Bot)
    )
    await db.commit()
    return result.scalar_one_or_none()


async def deactivate_bot(db: AsyncSession, bot_id: int) -> bool:
    """Deactivate a bot."""
    result = await db.execute(
        update(Bot)
        .where(Bot.id == bot_id)
        .values(is_active=False)
    )
    await db.commit()
    return result.rowcount > 0


async def activate_bot(db: AsyncSession, bot_id: int) -> bool:
    """Activate a bot."""
    result = await db.execute(
        update(Bot)
        .where(Bot.id == bot_id)
        .values(is_active=True)
    )
    await db.commit()
    return result.rowcount > 0
```

**Step 6: Add Delete Function**

```python
async def delete_bot(db: AsyncSession, bot_id: int) -> bool:
    """Delete a bot (cascade will delete related data)."""
    bot = await get_bot_by_id(db, bot_id)
    if not bot:
        return False
    
    await db.delete(bot)
    await db.commit()
    return True
```

**Step 7: Test CRUD Operations**

Create `test_bot_crud.py`:

```python
import asyncio
from app.database.database import AsyncSessionLocal
from app.database.crud.bot import (
    create_bot, get_bot_by_id, get_bot_by_token,
    get_bot_by_api_token, get_active_bots, update_bot, delete_bot
)


async def test_bot_crud():
    async with AsyncSessionLocal() as db:
        # Test create
        bot, api_token = await create_bot(
            db,
            name="Test Bot",
            telegram_bot_token="123456:ABC-DEF"
        )
        print(f"Created bot: {bot.id}, API token: {api_token[:20]}...")
        
        # Test get by id
        found_bot = await get_bot_by_id(db, bot.id)
        assert found_bot is not None
        print("Get by ID: OK")
        
        # Test get by token
        found_bot = await get_bot_by_token(db, "123456:ABC-DEF")
        assert found_bot is not None
        print("Get by token: OK")
        
        # Test get by API token
        found_bot = await get_bot_by_api_token(db, api_token)
        assert found_bot is not None
        print("Get by API token: OK")
        
        # Test update
        updated = await update_bot(db, bot.id, name="Updated Bot")
        assert updated.name == "Updated Bot"
        print("Update: OK")
        
        # Test get active bots
        active = await get_active_bots(db)
        assert len(active) > 0
        print("Get active bots: OK")
        
        # Test delete
        deleted = await delete_bot(db, bot.id)
        assert deleted
        print("Delete: OK")
        
        print("All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_bot_crud())
```

Run:
```bash
python test_bot_crud.py
```

#### Acceptance Criteria

- ✅ `create_bot` creates bot and returns API token
- ✅ `get_bot_by_id` retrieves bot correctly
- ✅ `get_bot_by_token` finds bot by Telegram token
- ✅ `get_bot_by_api_token` finds bot by API token (hashed)
- ✅ `get_master_bot` returns master bot
- ✅ `get_active_bots` returns all active bots
- ✅ `update_bot` updates bot fields
- ✅ `delete_bot` deletes bot (cascade works)
- ✅ All test cases pass

#### Troubleshooting

**Error: "api_token column doesn't exist"**
- Solution: Remove `api_token` column from create - it's only shown once, then only hash is stored

**Error: "Token hash mismatch"**
- Solution: Ensure using same hashing function in get and create

---

*[Continue with remaining increments... Due to length, I'll create this as a separate comprehensive file]*

---

## 📝 Notes for AI Assistant

When implementing each increment:

1. **Read the increment completely** before starting
2. **Follow steps in order** - don't skip steps
3. **Test after each step** - don't wait until the end
4. **Check acceptance criteria** - verify each item
5. **If error occurs** - check troubleshooting section first
6. **Commit after completion** - use clear commit messages

**Commit Message Format:**
```
feat(multi-tenant): [Increment X.Y] - [Brief description]

- [What was done]
- [Key changes]
- [Tests added/updated]
```

---

**Next Steps:**
- Continue with Increment 1.4 (Feature Flag CRUD)
- Then Increment 1.5 (Bot Context Middleware)
- Then Phase 2 increments...
