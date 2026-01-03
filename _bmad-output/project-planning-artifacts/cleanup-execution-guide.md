# Russian Gateway Cleanup - Execution Guide

**Project:** remnabot Multi-Tenant SaaS
**Author:** K4lantar4
**Date:** 2025-12-26
**Strategy:** Delete without Archive (dev/staging, no data)
**Status:** READY TO EXECUTE

---

## Quick Reference

### Decision Summary

**Archive Strategy:** ❌ No Archive (Delete Direct)
- **Environment:** Dev/Staging
- **Data Status:** No production data exists
- **Rationale:** Fastest cleanup, no compliance requirements
- **Approved:** K4lantar4, 2025-12-26

### Cleanup Scope

| Layer | Files to Delete | Files to Modify | Tables to Drop |
|-------|----------------|-----------------|----------------|
| External | 7 | 0 | - |
| Services | 13 | 11 | - |
| Handlers | 7 | 16 | - |
| Database | - | 1 (models.py) | 7 |
| **Total** | **27** | **28** | **7** |

---

## Week 1, Days 3-5: Delete Isolated Files (27 files)

### Checklist of Files to Delete

#### External Layer (7 files)

```bash
# Delete these files directly
rm app/external/yookassa_webhook.py       # 394 lines
rm app/external/wata_webhook.py           # 262 lines
rm app/external/pal24_client.py           # 216 lines
rm app/external/heleket.py                # 174 lines
rm app/external/pal24_webhook.py          # 162 lines
rm app/external/tribute.py                # 161 lines
rm app/external/heleket_webhook.py        # 111 lines
```

- [ ] yookassa_webhook.py
- [ ] wata_webhook.py
- [ ] pal24_client.py
- [ ] heleket.py
- [ ] pal24_webhook.py
- [ ] tribute.py
- [ ] heleket_webhook.py

#### Service Layer - Individual Files (6 files)

```bash
# Delete gateway-specific service files
rm app/services/wata_service.py
rm app/services/yookassa_service.py
rm app/services/tribute_service.py
rm app/services/mulenpay_service.py
rm app/services/pal24_service.py
rm app/services/platega_service.py
```

- [ ] wata_service.py
- [ ] yookassa_service.py
- [ ] tribute_service.py
- [ ] mulenpay_service.py
- [ ] pal24_service.py
- [ ] platega_service.py

#### Service Layer - Payment Module (7 files)

```bash
# Delete payment module gateway files
rm app/services/payment/heleket.py
rm app/services/payment/mulenpay.py
rm app/services/payment/pal24.py
rm app/services/payment/tribute.py
rm app/services/payment/wata.py
rm app/services/payment/platega.py
rm app/services/payment/yookassa.py
```

- [ ] services/payment/heleket.py
- [ ] services/payment/mulenpay.py
- [ ] services/payment/pal24.py
- [ ] services/payment/tribute.py
- [ ] services/payment/wata.py
- [ ] services/payment/platega.py
- [ ] services/payment/yookassa.py

#### Handler Layer - Balance Handlers (7 files)

```bash
# Delete balance handler gateway files
rm app/handlers/balance/wata.py
rm app/handlers/balance/yookassa.py
rm app/handlers/balance/heleket.py
rm app/handlers/balance/mulenpay.py
rm app/handlers/balance/pal24.py
rm app/handlers/balance/platega.py
rm app/handlers/balance/tribute.py
```

- [ ] handlers/balance/wata.py
- [ ] handlers/balance/yookassa.py
- [ ] handlers/balance/heleket.py
- [ ] handlers/balance/mulenpay.py
- [ ] handlers/balance/pal24.py
- [ ] handlers/balance/platega.py
- [ ] handlers/balance/tribute.py

### Execution Script

**Create feature branch:**
```bash
cd /home/k4lantar4/dev/remnabot.worktrees/dev5-from-upstream
git checkout -b cleanup/russian-gateways-phase1
```

**Delete all 27 files:**
```bash
# External (7 files)
rm app/external/yookassa_webhook.py
rm app/external/wata_webhook.py
rm app/external/pal24_client.py
rm app/external/pal24_webhook.py
rm app/external/heleket.py
rm app/external/heleket_webhook.py
rm app/external/tribute.py

# Services - Individual (6 files)
rm app/services/wata_service.py
rm app/services/yookassa_service.py
rm app/services/tribute_service.py
rm app/services/mulenpay_service.py
rm app/services/pal24_service.py
rm app/services/platega_service.py

# Services - Payment Module (7 files)
rm app/services/payment/heleket.py
rm app/services/payment/mulenpay.py
rm app/services/payment/pal24.py
rm app/services/payment/tribute.py
rm app/services/payment/wata.py
rm app/services/payment/platega.py
rm app/services/payment/yookassa.py

# Handlers - Balance (7 files)
rm app/handlers/balance/wata.py
rm app/handlers/balance/yookassa.py
rm app/handlers/balance/heleket.py
rm app/handlers/balance/mulenpay.py
rm app/handlers/balance/pal24.py
rm app/handlers/balance/platega.py
rm app/handlers/balance/tribute.py
```

**Verify deletions:**
```bash
# Should show 27 deleted files
git status

# Check no imports remain (should return nothing)
rg "from app.external.yookassa_webhook" app/
rg "from app.services.wata_service" app/
rg "from app.services.payment.heleket" app/
rg "from app.handlers.balance.yookassa" app/
```

**Commit:**
```bash
git add -A
git commit -m "cleanup: Remove Russian payment gateway files (27 files)

- Delete 7 external gateway webhook files
- Delete 6 individual gateway service files  
- Delete 7 payment module gateway files
- Delete 7 balance handler gateway files

Total: 27 files, ~3,000 lines removed

Related: Russian Artifacts Removal Plan
Environment: dev/staging, no production data"
```

---

## Week 1, Days 6-7 + Week 2, Days 1-3: Modify Core Files (28 files)

### Files Requiring Surgical Removal

#### Priority P0 (Blocking - Must do first)

**Services:**
- [ ] `app/services/payment_service.py` - Gateway orchestration
- [ ] `app/services/subscription_service.py` (1,249 lines)
- [ ] `app/services/user_service.py` (1,139 lines)
- [ ] `app/services/payment_verification_service.py` (828 lines)
- [ ] `app/services/payment/__init__.py` - Gateway exports
- [ ] `app/services/payment/common.py` - Common gateway utils

**Handlers:**
- [ ] `app/handlers/subscription/purchase.py` (3,455 lines) ⚠️ EXTREME
- [ ] `app/handlers/webhooks.py` - Gateway webhook routes
- [ ] `app/handlers/balance/main.py` - Gateway balance UI
- [ ] `app/handlers/admin/payments.py` - Gateway admin UI
- [ ] `app/handlers/admin/bot_configuration.py` (2,800 lines) ⚠️ CRITICAL

#### Priority P1 (Important)

**Services:**
- [ ] `app/services/system_settings_service.py` (1,470 lines)
- [ ] `app/services/admin_notification_service.py` (1,560 lines)

**Handlers:**
- [ ] `app/handlers/simple_subscription.py` (2,420 lines) ⚠️ CRITICAL
- [ ] `app/handlers/subscription/pricing.py`
- [ ] `app/handlers/subscription/promo.py`
- [ ] `app/handlers/subscription/common.py`
- [ ] `app/handlers/admin/tickets.py` (1,248 lines)
- [ ] `app/handlers/admin/promo_offers.py` (2,387 lines) ⚠️ CRITICAL

#### Priority P2 (Nice to have)

**Services:**
- [ ] `app/services/backup_service.py` (1,556 lines)
- [ ] `app/services/poll_service.py`

**Handlers:**
- [ ] `app/handlers/subscription/countries.py`
- [ ] `app/handlers/server_status.py`
- [ ] `app/handlers/polls.py`

### Surgical Removal Pattern

**For each file, remove:**

1. **Imports:**
```python
# REMOVE these imports
from app.services.yookassa_service import YooKassaService
from app.services.wata_service import WataService
from app.external.heleket import HeleketAPI
# etc.
```

2. **Gateway References in Code:**
```python
# REMOVE gateway-specific code blocks
if payment_method == PaymentMethod.YOOKASSA:
    result = await yookassa_service.create_payment(...)
elif payment_method == PaymentMethod.HELEKET:
    result = await heleket_service.create_payment(...)
# etc.
```

3. **Inline Keyboard Buttons (in handlers):**
```python
# REMOVE Russian gateway buttons
buttons = [
    InlineKeyboardButton(text="💳 YooKassa", callback_data="pay_yookassa"),  # REMOVE
    InlineKeyboardButton(text="🏦 Heleket", callback_data="pay_heleket"),    # REMOVE
    # ... REMOVE all Russian gateway buttons
    
    # KEEP Iranian gateways
    InlineKeyboardButton(text="💳 ZarinPal", callback_data="pay_zarinpal"),  # KEEP
    InlineKeyboardButton(text="💳 کارت به کارت", callback_data="pay_card"),  # KEEP
]
```

4. **Callback Handlers:**
```python
# REMOVE gateway-specific callback handlers
@router.callback_query(F.data == "pay_yookassa")
async def process_yookassa_payment(callback: CallbackQuery):
    # REMOVE entire function
    pass
```

5. **Enum References:**
```python
# REMOVE enum checks
if method in [PaymentMethod.YOOKASSA, PaymentMethod.HELEKET, ...]:
    # REMOVE this block
```

### Example: Cleaning `subscription/purchase.py`

**Before (fragment):**
```python
from app.services.yookassa_service import YooKassaService
from app.services.wata_service import WataService

async def show_payment_methods(message: Message):
    methods = [
        ("💳 YooKassa", "yookassa"),
        ("🏦 Heleket", "heleket"),
        ("💳 ZarinPal", "zarinpal"),
    ]
    # ...

@router.callback_query(F.data == "pay_yookassa")
async def process_yookassa(callback: CallbackQuery):
    # Russian gateway logic
    pass
```

**After (cleaned):**
```python
# Imports removed

async def show_payment_methods(message: Message):
    methods = [
        ("💳 ZarinPal", "zarinpal"),       # Iranian
        ("💳 کارت به کارت", "card_to_card"), # Iranian
        ("💰 کیف پول", "wallet"),           # Wallet
    ]
    # ...

# yookassa callback handler removed completely
```

---

## Week 2, Days 6-7: Database Cleanup Preparation

### Migration Files to Create

#### 1. Drop Russian Gateway Tables

**File:** `migrations/alembic/versions/xxx_drop_russian_gateway_tables.py`

```python
"""drop russian gateway tables

Revision ID: xxx
Revises: 2b3c1d4e5f6a
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa

revision = 'xxx'
down_revision = '2b3c1d4e5f6a'  # platega_payments migration

def upgrade():
    """Drop all Russian gateway payment tables"""
    
    # Tables to drop
    tables = [
        'platega_payments',   # Has migration
        'wata_payments',      # From models.py
        'pal24_payments',     # From models.py
        'mulenpay_payments',  # From models.py
        'heleket_payments',   # From models.py
        'yookassa_payments',  # From models.py
    ]
    
    for table in tables:
        # Check if table exists
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        
        if table in inspector.get_table_names():
            print(f"Dropping table: {table}")
            op.drop_table(table)
        else:
            print(f"Table not found (skipping): {table}")

def downgrade():
    """Cannot recreate tables - restore from backup if needed"""
    raise NotImplementedError(
        "Cannot downgrade - tables were created in old migrations. "
        "Restore from database backup if rollback is required."
    )
```

#### 2. Update Models.py

**File:** `app/database/models.py`

**Actions:**

1. **Delete Model Classes (~320 lines):**
```python
# DELETE THESE CLASSES (lines ~102-466):
class YooKassaPayment(Base):     # ~102-149
    # ... delete entire class

class HeleketPayment(Base):      # ~200-263
    # ... delete entire class

class MulenPayPayment(Base):     # ~266-306
    # ... delete entire class

class Pal24Payment(Base):        # ~309-368
    # ... delete entire class

class WataPayment(Base):         # ~371-418
    # ... delete entire class

class PlategaPayment(Base):      # ~421-466
    # ... delete entire class
```

2. **Update PaymentMethod Enum:**
```python
# BEFORE
class PaymentMethod(Enum):
    TELEGRAM_STARS = "telegram_stars"
    TRIBUTE = "tribute"           # DELETE
    YOOKASSA = "yookassa"         # DELETE
    CRYPTOBOT = "cryptobot"       # KEEP
    HELEKET = "heleket"           # DELETE
    MULENPAY = "mulenpay"         # DELETE
    PAL24 = "pal24"               # DELETE
    WATA = "wata"                 # DELETE
    PLATEGA = "platega"           # DELETE
    MANUAL = "manual"             # KEEP

# AFTER
class PaymentMethod(Enum):
    TELEGRAM_STARS = "telegram_stars"
    CRYPTOBOT = "cryptobot"
    MANUAL = "manual"
    ZARINPAL = "zarinpal"         # ADD
    CARD_TO_CARD = "card_to_card" # ADD
```

---

## Week 3: Database Execution + Currency Migration

### Days 1-3: Execute Database Cleanup

```bash
# 1. Full backup
cd /home/k4lantar4/dev/remnabot.worktrees/dev5-from-upstream
pg_dump -U postgres -d remnabot > backup_pre_cleanup_20251226.sql

# 2. Run migration
alembic upgrade head

# 3. Verify tables dropped
psql -U postgres -d remnabot
\dt *yookassa*
\dt *heleket*
\dt *platega*
# Should return "Did not find any relations"

# 4. Check application starts
python main.py
# Should start without errors
```

### Days 4-5: Currency Migration (TBD)

**Note:** Requires business decision on conversion rate or repricing strategy.

**Checklist:**
- [ ] Decide conversion rate (kopek → toman)
- [ ] Identify all tables with kopek columns
- [ ] Create migration to add toman columns
- [ ] Update all service/handler code
- [ ] Test all financial calculations

---

## Verification & Testing

### After Each Phase

**Code Verification:**
```bash
# No Russian gateway imports
rg -i "yookassa|heleket|tribute|mulenpay|pal24|platega|wata" app/ \
  --type py | grep -v ".pyc"
# Should return no results

# No kopek references (after currency migration)
rg -i "kopek" app/ --type py | grep -v ".pyc"
# Should return no results
```

**Database Verification:**
```sql
-- No Russian gateway tables
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND (table_name LIKE '%yookassa%' 
    OR table_name LIKE '%heleket%'
    OR table_name LIKE '%platega%'
    OR table_name LIKE '%wata%'
    OR table_name LIKE '%pal24%'
    OR table_name LIKE '%mulenpay%');
-- Should return 0 rows
```

**Application Testing:**
```bash
# Run tests
pytest tests/ -v

# Start application
python main.py

# Test payment flow manually
# - ZarinPal should work
# - Card-to-card should work
# - Wallet should work
# - No Russian gateway options visible
```

---

## Success Criteria

### Phase 1 Complete (Week 1 Days 3-5)
- [ ] 27 files deleted
- [ ] Git commit created
- [ ] No import errors when running app
- [ ] Tests pass

### Phase 2 Complete (Week 1-2)
- [ ] 28 files modified
- [ ] All Russian gateway references removed
- [ ] Payment flows updated (ZarinPal, Card, Wallet only)
- [ ] Tests updated and passing

### Phase 3 Complete (Week 3)
- [ ] 7 database tables dropped
- [ ] 6 model classes removed from models.py
- [ ] PaymentMethod enum updated
- [ ] Database clean
- [ ] Application functional

---

## Quick Start

**To begin cleanup NOW:**

```bash
# 1. Create branch
cd /home/k4lantar4/dev/remnabot.worktrees/dev5-from-upstream
git checkout -b cleanup/russian-gateways

# 2. Delete 27 files (copy-paste from above)
# ... execute deletion commands

# 3. Verify
git status
rg "from app.external.yookassa" app/

# 4. Commit
git add -A
git commit -m "cleanup: Remove Russian payment gateway files (27 files)"

# 5. Continue with modifications
# ... follow guides above
```

---

**Status:** READY TO EXECUTE
**Next Action:** Begin Week 1 Days 3-5 - Delete 27 isolated files
**Estimated Time:** 1-2 hours for file deletion

---

*Cleanup Execution Guide - 2025-12-26*
*Based on Russian Artifacts Removal Plan*
*Strategy: Delete without Archive (dev/staging)*

