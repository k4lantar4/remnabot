# Master Cleanup Guide - Russian Gateway Removal & Codebase Preparation

**Project:** remnabot Multi-Tenant SaaS Transformation
**Author:** K4lantar4
**Date:** 2025-12-26
**Duration:** 4 Weeks (20 Working Days)
**Status:** READY FOR EXECUTION

---

## 📋 Executive Summary

این یک **دستورالعمل کامل 4 هفته‌ای** برای:
1. ✅ حذف کامل درگاه‌های پرداخت روسی (65+ فایل، 7 جدول)
2. ✅ Split کردن فایل‌های بزرگ (15 فایل >1000 خط)
3. ✅ پاکسازی Database (7 جدول، currency migration)
4. ✅ آماده‌سازی برای Epic Creation

**هدف نهایی:** آماده کردن codebase برای شروع پیاده‌سازی multi-tenant SaaS

---

## 🗓️ Timeline Overview

| Week | Days | Focus | Deliverables |
|------|------|-------|--------------|
| **1** | 1-2 | Planning & Audit | ✅ Complete (done) |
| **1** | 3-5 | Delete 27 isolated files | 27 files deleted |
| **1** | 6-7 | Split 3 EXTREME files | 3 files → 15+ modules |
| **2** | 1-3 | Surgical removal (28 files) | Core files cleaned |
| **2** | 4-5 | Split 4 CRITICAL files | 4 files → 20+ modules |
| **2** | 6-7 | Database prep | Migration scripts ready |
| **3** | 1-3 | Database cleanup | 7 tables dropped |
| **3** | 4-5 | Currency migration | Kopek → Toman |
| **3** | 6-7 | Testing & verification | All tests pass |
| **4** | 1-2 | Missing FRs + Templates | PRD updated |
| **4** | 3-4 | Update docs | Architecture updated |
| **4** | 5 | Final readiness check | Approval |
| **4** | 6-7 | **BEGIN EPIC CREATION** | ✅ Ready |

---

## 📦 Prerequisites

### قبل از شروع:

- [ ] Git repository clean (no uncommitted changes)
- [ ] Database backup (even for dev/staging)
- [ ] Test environment ready
- [ ] All team members notified
- [ ] Branch strategy decided

### Tools Needed:

- Python 3.13+
- PostgreSQL 15+
- Git
- Code editor (VS Code recommended)
- Terminal/Shell access

---

# WEEK 1: Foundation Cleanup

## Days 1-2: Planning & Audit ✅ COMPLETE

**Status:** ✅ Done by PM
- Implementation Readiness Report
- Russian Artifacts Removal Plan
- Database Audit Report

**No action needed from dev.**

---

## Days 3-5: Delete Isolated Russian Gateway Files

### Goal
حذف 27 فایل مستقل که فقط مربوط به درگاه‌های روسی هستند.

### Files to Delete (27 total)

#### External Layer (7 files)

```bash
cd /path/to/remnabot
git checkout -b cleanup/week1-phase1-delete-files

# External files
rm app/external/yookassa_webhook.py       # 394 lines
rm app/external/wata_webhook.py           # 262 lines
rm app/external/pal24_client.py           # 216 lines
rm app/external/pal24_webhook.py          # 162 lines
rm app/external/heleket.py                # 174 lines
rm app/external/heleket_webhook.py        # 111 lines
rm app/external/tribute.py                # 161 lines
```

#### Service Layer - Individual (6 files)

```bash
rm app/services/wata_service.py
rm app/services/yookassa_service.py
rm app/services/tribute_service.py
rm app/services/mulenpay_service.py
rm app/services/pal24_service.py
rm app/services/platega_service.py
```

#### Service Layer - Payment Module (7 files)

```bash
rm app/services/payment/heleket.py
rm app/services/payment/mulenpay.py
rm app/services/payment/pal24.py
rm app/services/payment/tribute.py
rm app/services/payment/wata.py
rm app/services/payment/platega.py
rm app/services/payment/yookassa.py
```

#### Handler Layer - Balance (7 files)

```bash
rm app/handlers/balance/wata.py
rm app/handlers/balance/yookassa.py
rm app/handlers/balance/heleket.py
rm app/handlers/balance/mulenpay.py
rm app/handlers/balance/pal24.py
rm app/handlers/balance/platega.py
rm app/handlers/balance/tribute.py
```

### Verification

```bash
# Check deletions
git status | grep deleted | wc -l  # Should show 27

# Verify no imports remain (should return NOTHING)
rg "from app.external.yookassa_webhook" app/
rg "from app.services.wata_service" app/
rg "from app.services.payment.heleket" app/
rg "from app.handlers.balance.yookassa" app/

# Test application starts
python main.py  # Should start without errors
```

### Commit

```bash
git add -A
git commit -m "cleanup: Remove Russian payment gateway files (27 files)

- Delete 7 external gateway webhook files
- Delete 6 individual gateway service files
- Delete 7 payment module gateway files
- Delete 7 balance handler gateway files

Total: 27 files, ~3,000 lines removed

Part of: Week 1 Phase 1 - Isolated file deletion
Related: Russian Gateway Cleanup (4-week plan)"
```

### PR & Merge

```bash
git push origin cleanup/week1-phase1-delete-files
# Create PR, review, merge
```

**Expected Time:** 1-2 hours
**Risk:** Low (isolated files)

---

## Days 6-7: Split EXTREME Files (3 files)

### Goal
Split کردن 3 فایل EXTREME (>3000 خط) به modules کوچک‌تر.

### File 1: `app/handlers/admin/users.py` (5,298 lines)

**Current Structure:**
```
app/handlers/admin/users.py  (5,298 lines - MONOLITH)
```

**Target Structure:**
```
app/handlers/admin/users/
├── __init__.py              # Export main router
├── list.py                  # User listing, search, filter
├── details.py               # View/edit user details
├── subscriptions.py         # User subscription management
├── actions.py               # Ban, unban, delete actions
└── common.py                # Shared utilities, helpers
```

**Splitting Strategy:**

1. **Analyze file structure:**
```bash
# Find function definitions
grep -n "^def \|^async def " app/handlers/admin/users.py | head -20

# Find class definitions
grep -n "^class " app/handlers/admin/users.py
```

2. **Create directory:**
```bash
mkdir -p app/handlers/admin/users
```

3. **Split by functionality:**

**`list.py`** - User listing functions:
- `show_users_list()`
- `search_users()`
- `filter_users_by_status()`
- `paginate_users()`

**`details.py`** - User detail functions:
- `show_user_details()`
- `edit_user_info()`
- `view_user_stats()`

**`subscriptions.py`** - Subscription management:
- `show_user_subscriptions()`
- `manage_user_subscription()`
- `renew_user_subscription()`

**`actions.py`** - User actions:
- `ban_user()`
- `unban_user()`
- `delete_user()`
- `reset_user_password()`

**`common.py`** - Shared utilities:
- `get_user_by_id()`
- `format_user_info()`
- `validate_user_action()`

4. **Create `__init__.py`:**
```python
# app/handlers/admin/users/__init__.py
from .list import router as list_router
from .details import router as details_router
from .subscriptions import router as subscriptions_router
from .actions import router as actions_router

# Combine routers
router = Router()
router.include_router(list_router)
router.include_router(details_router)
router.include_router(subscriptions_router)
router.include_router(actions_router)
```

5. **Update imports in other files:**
```bash
# Find files importing users.py
rg "from app.handlers.admin.users import" app/
rg "from app.handlers.admin import users" app/

# Update to:
# from app.handlers.admin.users import router as users_router
```

6. **Test:**
```bash
python main.py  # Should start
pytest tests/handlers/admin/test_users.py -v
```

**Expected Time:** 1 day (8 hours)
**Risk:** Medium (large file, many dependencies)

---

### File 2: `app/handlers/subscription/purchase.py` (3,455 lines)

**Target Structure:**
```
app/handlers/subscription/purchase/
├── __init__.py              # Export main router
├── flow.py                  # Main purchase flow orchestration
├── payment.py               # Payment method selection
├── confirmation.py          # Confirmation screens
├── completion.py            # Success/failure handling
├── zarinpal.py              # ZarinPal-specific handlers
├── card_to_card.py          # Card-to-card specific handlers
└── wallet.py                # Wallet-specific handlers
```

**Splitting Strategy:**

**`flow.py`** - Main flow:
- `start_purchase_flow()`
- `handle_purchase_state()`
- `navigate_purchase_steps()`

**`payment.py`** - Payment selection:
- `show_payment_methods()`
- `select_payment_method()`
- `handle_payment_selection()`

**`confirmation.py`** - Confirmation:
- `show_purchase_summary()`
- `confirm_purchase()`
- `cancel_purchase()`

**`completion.py`** - Completion:
- `handle_purchase_success()`
- `handle_purchase_failure()`
- `send_confirmation_message()`

**`zarinpal.py`** - ZarinPal:
- `process_zarinpal_payment()`
- `handle_zarinpal_callback()`

**`card_to_card.py`** - Card-to-card:
- `process_card_payment()`
- `handle_receipt_upload()`

**`wallet.py`** - Wallet:
- `process_wallet_payment()`
- `check_wallet_balance()`

**Expected Time:** 1 day (8 hours)
**Risk:** Medium-High (critical purchase flow)

---

### File 3: `app/handlers/admin/remnawave.py` (3,282 lines)

**Target Structure:**
```
app/handlers/admin/remnawave/
├── __init__.py
├── servers.py               # Server management
├── protocols.py             # Protocol configuration
├── monitoring.py            # Server monitoring
└── sync.py                  # Synchronization
```

**Expected Time:** 0.5 day (4 hours)
**Risk:** Medium

---

### Verification After Splitting

```bash
# Check new structure
tree app/handlers/admin/users/
tree app/handlers/subscription/purchase/
tree app/handlers/admin/remnawave/

# Test imports
python -c "from app.handlers.admin.users import router"
python -c "from app.handlers.subscription.purchase import router"

# Run tests
pytest tests/ -v

# Test application
python main.py
```

### Commit

```bash
git add -A
git commit -m "refactor: Split EXTREME files into modules

- Split admin/users.py (5,298 lines) → users/ (6 modules)
- Split subscription/purchase.py (3,455 lines) → purchase/ (7 modules)
- Split admin/remnawave.py (3,282 lines) → remnawave/ (4 modules)

Total: 3 files → 17 modules
Lines reduced: ~12,000 → manageable modules

Part of: Week 1 Phase 2 - File splitting
Benefits: Better maintainability, AI model compatibility"
```

**Total Week 1 Time:** 3-4 days
**Deliverables:** 27 files deleted, 3 files split

---

# WEEK 2: Deep Cleanup

## Days 1-3: Surgical Removal from Core Files (28 files)

### Goal
حذف references به درگاه‌های روسی از فایل‌های core که contaminated هستند.

### Priority P0 Files (Must do first)

#### Services (6 files)

**1. `app/services/payment_service.py`**

**Find Russian gateway references:**
```bash
rg -i "yookassa|heleket|tribute|mulenpay|pal24|platega|wata" app/services/payment_service.py
```

**Remove:**
- Import statements for Russian gateway services
- Gateway-specific payment creation logic
- Gateway enum checks

**Example:**
```python
# BEFORE
from app.services.yookassa_service import YooKassaService
from app.services.wata_service import WataService

async def create_payment(method: PaymentMethod):
    if method == PaymentMethod.YOOKASSA:
        return await yookassa_service.create(...)
    elif method == PaymentMethod.WATA:
        return await wata_service.create(...)
    # ...

# AFTER
# Imports removed

async def create_payment(method: PaymentMethod):
    if method == PaymentMethod.ZARINPAL:
        return await zarinpal_service.create(...)
    elif method == PaymentMethod.CARD_TO_CARD:
        return await card_service.create(...)
    elif method == PaymentMethod.WALLET:
        return await wallet_service.create(...)
    # Russian gateways removed
```

**2. `app/services/subscription_service.py` (1,249 lines)**

**Find and remove:**
- Russian gateway imports
- Gateway-specific subscription logic
- Gateway payment method checks

**3. `app/services/user_service.py` (1,139 lines)**

**Find and remove:**
- Russian gateway payment history queries
- Gateway-specific user payment methods

**4. `app/services/payment_verification_service.py` (828 lines)**

**Find and remove:**
- Russian gateway verification logic
- Gateway-specific verification methods

**5. `app/services/payment/__init__.py`**

**Remove exports:**
```python
# BEFORE
from .heleket import HeleketService
from .yookassa import YooKassaService
# ...

# AFTER
# All Russian gateway exports removed
# Keep only: zarinpal, card_to_card, wallet
```

**6. `app/services/payment/common.py`**

**Remove:**
- Gateway-specific utility functions
- Gateway enum helpers

---

#### Handlers (5 files)

**1. `app/handlers/subscription/purchase.py` (now in purchase/ directory)**

**After splitting, clean each module:**
- Remove Russian gateway buttons from `payment.py`
- Remove Russian gateway callbacks
- Update payment method selection

**Example:**
```python
# BEFORE (in purchase/payment.py)
buttons = [
    InlineKeyboardButton("💳 YooKassa", callback_data="pay_yookassa"),
    InlineKeyboardButton("🏦 Heleket", callback_data="pay_heleket"),
    InlineKeyboardButton("💳 ZarinPal", callback_data="pay_zarinpal"),
]

# AFTER
buttons = [
    InlineKeyboardButton("💳 ZarinPal", callback_data="pay_zarinpal"),
    InlineKeyboardButton("💳 کارت به کارت", callback_data="pay_card"),
    InlineKeyboardButton("💰 کیف پول", callback_data="pay_wallet"),
]
```

**2. `app/handlers/webhooks.py`**

**Remove:**
- Russian gateway webhook routes
- Gateway webhook handlers

**3. `app/handlers/balance/main.py`**

**Remove:**
- Russian gateway balance handlers
- Gateway balance UI

**4. `app/handlers/admin/payments.py`**

**Remove:**
- Russian gateway admin UI
- Gateway payment management

**5. `app/handlers/admin/bot_configuration.py` (2,800 lines)**

**Remove:**
- Russian gateway configuration options
- Gateway settings UI

---

### Priority P1 Files (Important)

**Services (2 files):**
- `app/services/system_settings_service.py` (1,470 lines)
- `app/services/admin_notification_service.py` (1,560 lines)

**Handlers (6 files):**
- `app/handlers/simple_subscription.py` (2,420 lines)
- `app/handlers/subscription/pricing.py`
- `app/handlers/subscription/promo.py`
- `app/handlers/subscription/common.py`
- `app/handlers/admin/tickets.py` (1,248 lines)
- `app/handlers/admin/promo_offers.py` (2,387 lines)

---

### Priority P2 Files (Nice to have)

**Services (2 files):**
- `app/services/backup_service.py` (1,556 lines)
- `app/services/poll_service.py`

**Handlers (3 files):**
- `app/handlers/subscription/countries.py`
- `app/handlers/server_status.py`
- `app/handlers/polls.py`

---

### Surgical Removal Pattern (for each file)

**Step 1: Find references**
```bash
rg -i "yookassa|heleket|tribute|mulenpay|pal24|platega|wata" app/services/payment_service.py
```

**Step 2: Remove imports**
```python
# Delete these lines
from app.services.yookassa_service import YooKassaService
```

**Step 3: Remove code blocks**
```python
# Delete entire if/elif blocks for Russian gateways
if method == PaymentMethod.YOOKASSA:
    # ... entire block
```

**Step 4: Remove enum references**
```python
# Remove from lists/checks
if method in [PaymentMethod.YOOKASSA, PaymentMethod.HELEKET]:
    # Remove this check
```

**Step 5: Update tests**
```python
# Remove or skip gateway-specific tests
@pytest.mark.skip(reason="Russian gateway removed")
def test_yookassa_payment():
    pass
```

**Step 6: Verify**
```bash
# No Russian gateway references
rg -i "yookassa|heleket" app/services/payment_service.py
# Should return nothing

# Application starts
python main.py

# Tests pass
pytest tests/services/test_payment_service.py -v
```

---

### Verification After Surgical Removal

```bash
# Global check - should return minimal results (only in comments/docs)
rg -i "yookassa|heleket|tribute|mulenpay|pal24|platega|wata" app/ \
  --type py | grep -v ".pyc" | grep -v "#" | grep -v "test"

# Application starts
python main.py

# All tests pass
pytest tests/ -v
```

### Commit

```bash
git add -A
git commit -m "cleanup: Remove Russian gateway references from core files

- Clean 6 service files (payment_service, subscription_service, etc.)
- Clean 5 handler files (webhooks, balance, admin)
- Remove all Russian gateway imports, logic, and UI elements
- Update payment method selection to only Iranian gateways

Total: 28 files cleaned
Part of: Week 2 Phase 1 - Surgical removal"
```

**Expected Time:** 3 days
**Risk:** Medium (core files, need careful testing)

---

## Days 4-5: Split CRITICAL Files (4 files)

### Goal
Split کردن 4 فایل CRITICAL (2000-3000 خط).

### File 1: `app/handlers/admin/bot_configuration.py` (2,800 lines)

**Target Structure:**
```
app/handlers/admin/bot_configuration/
├── __init__.py
├── general.py               # General bot settings
├── payments.py              # Payment gateway settings
├── localization.py          # Language/localization
├── notifications.py         # Notification settings
└── advanced.py              # Advanced configuration
```

**Expected Time:** 0.5 day

---

### File 2: `app/services/remnawave_service.py` (2,691 lines)

**Target Structure:**
```
app/services/remnawave/
├── __init__.py
├── api_client.py            # API communication
├── server_management.py     # Server CRUD
├── protocol_config.py       # Protocol settings
└── monitoring.py            # Server monitoring
```

**Expected Time:** 0.5 day

---

### File 3: `app/handlers/simple_subscription.py` (2,420 lines)

**Target Structure:**
```
app/handlers/simple_subscription/
├── __init__.py
├── flow.py                  # Main subscription flow
├── selection.py             # Plan selection
├── payment.py               # Payment handling
└── completion.py            # Success/failure
```

**Expected Time:** 0.5 day

---

### File 4: `app/handlers/admin/promo_offers.py` (2,387 lines)

**Target Structure:**
```
app/handlers/admin/promo_offers/
├── __init__.py
├── list.py                  # Offer listing
├── create.py                # Create offers
├── edit.py                  # Edit offers
└── manage.py                # Offer management
```

**Expected Time:** 0.5 day

---

### Commit

```bash
git commit -m "refactor: Split CRITICAL files into modules

- Split admin/bot_configuration.py (2,800 lines) → 5 modules
- Split remnawave_service.py (2,691 lines) → 4 modules
- Split simple_subscription.py (2,420 lines) → 4 modules
- Split admin/promo_offers.py (2,387 lines) → 4 modules

Total: 4 files → 17 modules
Part of: Week 2 Phase 2 - File splitting"
```

**Expected Time:** 2 days
**Total Week 2 Time:** 5 days

---

## Days 6-7: Database Cleanup Preparation

### Goal
آماده کردن migration scripts برای حذف جداول.

### Step 1: Create Drop Tables Migration

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
    
    tables = [
        'platega_payments',
        'wata_payments',
        'pal24_payments',
        'mulenpay_payments',
        'heleket_payments',
        'yookassa_payments',
    ]
    
    for table in tables:
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        
        if table in inspector.get_table_names():
            print(f"Dropping table: {table}")
            op.drop_table(table)
        else:
            print(f"Table not found (skipping): {table}")

def downgrade():
    """Cannot recreate - restore from backup if needed"""
    raise NotImplementedError(
        "Cannot downgrade - restore from database backup"
    )
```

### Step 2: Test Migration Locally

```bash
# Backup (even for dev)
pg_dump -U postgres -d remnabot > backup_pre_drop_20251226.sql

# Test migration
alembic upgrade head

# Verify tables dropped
psql -U postgres -d remnabot
\dt *yookassa*
\dt *heleket*
# Should return "Did not find any relations"

# Test rollback (if needed)
# alembic downgrade -1
```

### Step 3: Update Models.py

**File:** `app/database/models.py`

**Actions:**

1. **Delete 6 model classes (~320 lines):**
   - `YooKassaPayment`
   - `HeleketPayment`
   - `MulenPayPayment`
   - `Pal24Payment`
   - `WataPayment`
   - `PlategaPayment`

2. **Update PaymentMethod enum:**
```python
# BEFORE
class PaymentMethod(Enum):
    TRIBUTE = "tribute"           # DELETE
    YOOKASSA = "yookassa"         # DELETE
    HELEKET = "heleket"           # DELETE
    MULENPAY = "mulenpay"         # DELETE
    PAL24 = "pal24"               # DELETE
    WATA = "wata"                 # DELETE
    PLATEGA = "platega"           # DELETE
    # ... keep others

# AFTER
class PaymentMethod(Enum):
    TELEGRAM_STARS = "telegram_stars"
    CRYPTOBOT = "cryptobot"
    MANUAL = "manual"
    ZARINPAL = "zarinpal"         # ADD
    CARD_TO_CARD = "card_to_card" # ADD
```

### Step 4: Verify

```bash
# Check models.py
rg "class.*Payment.*Base" app/database/models.py
# Should not show Russian gateway models

# Check enum
rg "YOOKASSA|HELEKET|PLATEGA" app/database/models.py
# Should return nothing

# Application starts
python main.py
```

### Commit

```bash
git commit -m "feat: Prepare database cleanup migration

- Create migration to drop 6 Russian gateway tables
- Update models.py: remove 6 payment model classes
- Update PaymentMethod enum: remove 7 Russian values, add 2 Iranian
- Test migration in local environment

Part of: Week 2 Phase 3 - Database preparation
Next: Week 3 - Execute database cleanup"
```

**Expected Time:** 1-2 days
**Total Week 2:** 5-6 days

---

# WEEK 3: Database & Currency

## Days 1-3: Execute Database Cleanup

### Goal
حذف 7 جدول Russian gateway از database.

### Step 1: Final Backup

```bash
# Full database backup
pg_dump -U postgres -d remnabot > backup_pre_cleanup_20251226.sql

# Verify backup
ls -lh backup_pre_cleanup_20251226.sql
```

### Step 2: Execute Migration

```bash
# Run migration
alembic upgrade head

# Expected output:
# INFO  [alembic.runtime.migration] Running upgrade 2b3c1d4e5f6a -> xxx, drop russian gateway tables
# Dropping table: platega_payments
# Dropping table: wata_payments
# ...
```

### Step 3: Verify Tables Dropped

```sql
-- Connect to database
psql -U postgres -d remnabot

-- Check tables
\dt *yookassa*
\dt *heleket*
\dt *platega*
\dt *wata*
\dt *pal24*
\dt *mulenpay*

-- Should all return: "Did not find any relations"
```

### Step 4: Verify Application

```bash
# Application should start
python main.py

# No database errors
# Check logs for any table not found errors
```

### Step 5: Update Code References

**Find any remaining references:**
```bash
rg "YooKassaPayment|HeleketPayment|PlategaPayment" app/
rg "yookassa_payments|heleket_payments|platega_payments" app/
```

**If found, remove or update.**

### Commit

```bash
git commit -m "feat: Drop Russian gateway database tables

- Execute migration to drop 6 payment gateway tables
- Remove 6 model classes from models.py
- Update PaymentMethod enum
- Verify application functionality

Tables dropped:
- yookassa_payments
- heleket_payments
- mulenpay_payments
- pal24_payments
- wata_payments
- platega_payments

Part of: Week 3 Phase 1 - Database cleanup"
```

**Expected Time:** 1 day
**Risk:** Medium (database changes)

---

## Days 4-5: Currency Migration (Kopek → Toman)

### Goal
تبدیل واحد پول از kopek (روسی) به toman (ایرانی).

### Step 1: Business Decision

**نیاز به تصمیم:**
- Conversion rate: 1 kopek = ? toman
- یا: Repricing کامل (قیمت‌های جدید در toman)

**اگر conversion rate:**
```python
# Example (needs business approval)
KOPEK_TO_TOMAN_RATE = 0.1  # 1 kopek = 0.1 toman
# یا
KOPEK_TO_TOMAN_RATE = 0.01  # 1 kopek = 0.01 toman
```

### Step 2: Identify All Kopek Columns

```bash
# Find kopek references in code
rg -i "kopek" app/ --type py

# Find in database models
rg "amount_kopeks|price_kopeks" app/database/models.py

# Expected tables:
# - subscriptions (price_kopeks?)
# - transactions (amount_kopeks?)
# - pricing (amount_kopeks?)
# - promocodes (discount_kopeks?)
```

### Step 3: Create Currency Migration

**File:** `migrations/alembic/versions/yyy_convert_kopek_to_toman.py`

```python
"""convert kopek to toman

Revision ID: yyy
Revises: xxx (drop_russian_gateway_tables)
Create Date: 2025-12-26

"""
from alembic import op
import sqlalchemy as sa

revision = 'yyy'
down_revision = 'xxx'

# CONVERSION RATE - NEEDS BUSINESS APPROVAL
KOPEK_TO_TOMAN_RATE = 0.1  # TODO: Get from business

def upgrade():
    """Convert kopek columns to toman"""
    
    # 1. Add toman columns
    op.add_column('subscriptions', 
                  sa.Column('price_tomans', sa.Integer(), nullable=True))
    op.add_column('transactions', 
                  sa.Column('amount_tomans', sa.Integer(), nullable=True))
    # ... other tables
    
    # 2. Convert data
    # amount_tomans = amount_kopeks * KOPEK_TO_TOMAN_RATE
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE subscriptions 
        SET price_tomans = CAST(price_kopeks * :rate AS INTEGER)
        WHERE price_kopeks IS NOT NULL
    """), {"rate": KOPEK_TO_TOMAN_RATE})
    
    # ... similar for other tables
    
    # 3. Make toman columns non-nullable (after verification)
    # op.alter_column('subscriptions', 'price_tomans', nullable=False)

def downgrade():
    """Rollback conversion"""
    # Remove toman columns
    op.drop_column('subscriptions', 'price_tomans')
    op.drop_column('transactions', 'amount_tomans')
    # ...
```

### Step 4: Update Service Code

**Find and update all kopek references:**

```python
# BEFORE
price_kopeks = subscription.price_kopeks
amount_kopeks = transaction.amount_kopeks

# AFTER
price_tomans = subscription.price_tomans
amount_tomans = transaction.amount_tomans
```

**Files to update:**
- All service files using kopek
- All handler files displaying prices
- All calculation logic

### Step 5: Update Display Logic

```python
# BEFORE
f"Price: {price_kopeks} kopek"

# AFTER
f"Price: {price_tomans:,} تومان"
```

### Step 6: Test

```bash
# Run migration
alembic upgrade head

# Verify data
psql -U postgres -d remnabot
SELECT price_kopeks, price_tomans FROM subscriptions LIMIT 10;
# Check conversion correct

# Test application
python main.py

# Test payment flows
# - Prices display in toman
# - Calculations correct
```

### Commit

```bash
git commit -m "feat: Convert currency from kopek to toman

- Add toman columns to all financial tables
- Convert existing kopek values to toman
- Update all service/handler code to use toman
- Update display logic (kopek → toman)

Conversion rate: 1 kopek = 0.1 toman (TBD - needs approval)

Part of: Week 3 Phase 2 - Currency migration"
```

**Expected Time:** 2 days
**Risk:** Medium (financial calculations)

---

## Days 6-7: Testing & Verification

### Goal
تست کامل تمام تغییرات.

### Test Checklist

#### Code Quality

- [ ] No Russian gateway imports
```bash
rg -i "yookassa|heleket|tribute|mulenpay|pal24|platega|wata" app/ \
  --type py | grep -v ".pyc" | grep -v "#" | grep -v "test"
# Should return minimal (only in comments/docs)
```

- [ ] No kopek references
```bash
rg -i "kopek" app/ --type py | grep -v ".pyc" | grep -v "#"
# Should return nothing
```

- [ ] All imports valid
```bash
python -m py_compile app/**/*.py
# Should not error
```

#### Application Tests

- [ ] Application starts
```bash
python main.py
# Should start without errors
```

- [ ] All unit tests pass
```bash
pytest tests/ -v
# All tests should pass
```

- [ ] Integration tests pass
```bash
pytest tests/integration/ -v
```

#### Manual Testing

- [ ] Purchase flow works (ZarinPal)
- [ ] Purchase flow works (Card-to-Card)
- [ ] Purchase flow works (Wallet)
- [ ] Admin can approve payments
- [ ] Prices display in toman
- [ ] No Russian gateway options visible
- [ ] Database queries work
- [ ] No errors in logs

#### Database Verification

- [ ] No Russian gateway tables
```sql
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND (table_name LIKE '%yookassa%' 
    OR table_name LIKE '%heleket%'
    OR table_name LIKE '%platega%');
-- Should return 0 rows
```

- [ ] Currency columns correct
```sql
SELECT price_tomans, amount_tomans FROM subscriptions LIMIT 5;
-- Should show toman values
```

### Final Verification Script

```bash
#!/bin/bash
# final_verification.sh

echo "=== Code Quality ==="
echo "Russian gateway references:"
rg -i "yookassa|heleket|platega" app/ --type py | wc -l

echo "Kopek references:"
rg -i "kopek" app/ --type py | wc -l

echo "=== Application ==="
python main.py &
APP_PID=$!
sleep 5
if ps -p $APP_PID > /dev/null; then
    echo "✅ Application started"
    kill $APP_PID
else
    echo "❌ Application failed to start"
    exit 1
fi

echo "=== Tests ==="
pytest tests/ -v --tb=short

echo "=== Database ==="
psql -U postgres -d remnabot -c "
SELECT COUNT(*) as russian_tables 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND (table_name LIKE '%yookassa%' 
    OR table_name LIKE '%heleket%');
"

echo "✅ Verification complete"
```

### Commit

```bash
git commit -m "test: Complete verification of Russian gateway cleanup

- All Russian gateway references removed
- All kopek references converted to toman
- All tests passing
- Application functional
- Database clean

Part of: Week 3 Phase 3 - Testing & verification
Status: Ready for Week 4"
```

**Expected Time:** 1-2 days
**Total Week 3:** 4-5 days

---

# WEEK 4: Finalization & Epic Creation

## Days 1-2: Add Missing FRs + Template Integration

### Goal
اضافه کردن FRهای مفقود و template integration specs.

### Step 1: Add Missing FRs to PRD

**File:** `_bmad-output/prd.md`

**Add these sections:**

#### FR14b: Basic Tenant Admin Dashboard

```markdown
#### FR14b: Basic Tenant Admin Dashboard

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR14b.1 | سیستم باید داشبورد Tenant Admin با آمار کلیدی نمایش دهد | P0 | آمار: کاربران فعال، درآمد امروز، پرداخت‌های در انتظار |
| FR14b.2 | سیستم باید دسترسی به داشبورد از Reply Keyboard امکان‌پذیر باشد | P0 | دکمه "📊 داشبورد" در منوی Admin |
```

#### FR14c: Tenant Admin User List

```markdown
#### FR14c: Tenant Admin User List

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR14c.1 | سیستم باید Tenant Admin بتواند لیست کاربران خود را مشاهده کند | P0 | لیست با pagination |
| FR14c.2 | سیستم باید جستجو و فیلتر کاربران امکان‌پذیر باشد | P1 | جستجو بر اساس telegram_id، status |
```

#### FR14d: Tenant Settings UI

```markdown
#### FR14d: Tenant Settings UI

| ID | Requirement | Priority | Acceptance Criteria |
|----|-------------|----------|---------------------|
| FR14d.1 | سیستم باید Tenant Admin بتواند تنظیمات را تغییر دهد | P0 | card_number، default_language، trial_days |
| FR14d.2 | سیستم باید تغییرات تنظیمات را validate کند | P0 | Validation errors نمایش داده شود |
```

### Step 2: Create Template Integration Specs

**File:** `_bmad-output/project-planning-artifacts/template-integration-spec.md`

```markdown
# Template Integration Specification

## Overview
Integration of UX-defined templates into codebase architecture.

## Template Files to Create

### 1. Message Templates
**File:** `app/localization/templates.py`

```python
from enum import Enum

class MessageTemplate(Enum):
    WELCOME = "welcome"
    LIST = "list"
    DETAIL = "detail"
    CONFIRMATION = "confirmation"
    SUCCESS = "success"
    ERROR = "error"
```

### 2. Keyboard Layouts
**File:** `app/localization/keyboards.py`

```python
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

END_USER_MAIN = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 خرید"), KeyboardButton(text="👤 حساب")],
        [KeyboardButton(text="💳 کیف"), KeyboardButton(text="🆘 پشتیبانی")],
    ],
    resize_keyboard=True
)

TENANT_ADMIN_MAIN = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 داشبورد"), KeyboardButton(text="👥 کاربران")],
        [KeyboardButton(text="💰 مالی"), KeyboardButton(text="⚙️ تنظیمات")],
    ],
    resize_keyboard=True
)
```

### 3. Emoji Constants
**File:** `app/localization/emoji.py`

```python
class Emoji:
    SUCCESS = "✅"
    ERROR = "❌"
    WARNING = "⚠️"
    INFO = "ℹ️"
    MONEY = "💰"
    CARD = "💳"
    USER = "👤"
    PACKAGE = "📦"
    # ... etc
```
```

### Step 3: Update Architecture Document

**File:** `_bmad-output/architecture.md`

**Add section:**

```markdown
## Template Integration

### Message Templates
- Location: `app/localization/templates.py`
- Usage: Handler methods reference templates
- Mapping: See template-integration-spec.md

### Keyboard Layouts
- Location: `app/localization/keyboards.py`
- Usage: Reply keyboards for navigation
- Defined in: UX Design Specification
```

### Commit

```bash
git commit -m "docs: Add missing FRs and template integration specs

- Add FR14b: Basic Tenant Admin Dashboard
- Add FR14c: Tenant Admin User List
- Add FR14d: Tenant Settings UI
- Create template integration specification
- Update Architecture document

Part of: Week 4 Phase 1 - Documentation updates"
```

**Expected Time:** 1 day

---

## Days 3-4: Update PRD & Architecture Documents

### Goal
به‌روزرسانی PRD و Architecture با تغییرات انجام شده.

### Step 1: Update PRD

**File:** `_bmad-output/prd.md`

**Add section to Implementation Phases:**

```markdown
### فاز ۰ - Pre-MVP Cleanup (هفته ۱-۳)

**Scope:**
- حذف درگاه‌های پرداخت روسی (65+ فایل، 7 جدول)
- Split فایل‌های بزرگ (15 فایل)
- تبدیل ارز (kopek → toman)
- آماده‌سازی codebase

**Deliverables:**
- ✅ Codebase تمیز از Russian artifacts
- ✅ فایل‌های قابل مدیریت (<1000 خط)
- ✅ Database تمیز
- ✅ Currency در toman
```

### Step 2: Update Architecture

**File:** `_bmad-output/architecture.md`

**Add section:**

```markdown
## Pre-MVP Cleanup Completed

### Russian Gateway Removal
- 27 isolated files deleted
- 28 core files cleaned
- 7 database tables dropped
- PaymentMethod enum updated

### File Refactoring
- 7 large files split into modules
- Better maintainability
- AI model compatibility improved

### Currency Migration
- Kopek → Toman conversion complete
- All financial calculations updated
```

### Commit

```bash
git commit -m "docs: Update PRD and Architecture with cleanup progress

- Document Phase 0 (Pre-MVP Cleanup)
- Update Architecture with completed work
- Add cleanup achievements

Part of: Week 4 Phase 2 - Documentation finalization"
```

**Expected Time:** 1 day

---

## Day 5: Final Readiness Check

### Goal
بررسی نهایی آمادگی برای Epic Creation.

### Readiness Checklist

- [ ] All Russian gateway files removed
- [ ] All contaminated files cleaned
- [ ] All large files split
- [ ] Database tables dropped
- [ ] Currency converted
- [ ] All tests passing
- [ ] Application functional
- [ ] PRD updated with missing FRs
- [ ] Architecture updated
- [ ] Template specs created
- [ ] Documentation complete

### Final Report

**Create:** `_bmad-output/project-planning-artifacts/final-readiness-report.md`

```markdown
# Final Readiness Report

**Date:** 2025-12-26
**Status:** ✅ READY FOR EPIC CREATION

## Cleanup Summary

### Files Removed: 27
### Files Modified: 28
### Files Split: 7 → 34 modules
### Database Tables Dropped: 7
### Currency Migrated: Kopek → Toman

## Readiness Score: 95% ✅

### Remaining Items:
- [ ] Business approval for currency conversion rate
- [ ] Final stakeholder review

## Recommendation: PROCEED TO EPIC CREATION ✅
```

### Approval

**Get approval from:**
- [ ] K4lantar4 (PM)
- [ ] Technical Lead (if applicable)
- [ ] Stakeholders

### Commit

```bash
git commit -m "docs: Final readiness check complete

- All cleanup tasks completed
- Readiness score: 95%
- Ready for Epic Creation

Status: ✅ APPROVED FOR EPIC CREATION"
```

**Expected Time:** 0.5 day

---

## Days 6-7: BEGIN EPIC CREATION ✅

### Goal
شروع ایجاد Epic‌ها و User Story‌ها.

### Next Steps

1. **Run Epic Creation Workflow:**
```
@bmad/bmm/workflows/create-epics-and-stories
```

2. **Input Documents:**
- PRD: `_bmad-output/prd.md`
- Architecture: `_bmad-output/architecture.md`
- UX: `_bmad-output/project-planning-artifacts/ux-design-specification.md`

3. **Expected Output:**
- Epics & Stories document
- Organized by phases
- Complete acceptance criteria

---

# 📊 Summary & Metrics

## Total Work Completed

| Category | Count |
|----------|-------|
| **Files Deleted** | 27 |
| **Files Modified** | 28 |
| **Files Split** | 7 → 34 modules |
| **Database Tables Dropped** | 7 |
| **Lines Removed** | ~15,000 |
| **Lines Refactored** | ~20,000 |
| **Time Spent** | 4 weeks |

## Quality Metrics

- ✅ **Code Quality:** Improved (no Russian artifacts)
- ✅ **Maintainability:** Improved (smaller files)
- ✅ **AI Compatibility:** Improved (manageable file sizes)
- ✅ **Database Clean:** Yes (no Russian tables)
- ✅ **Currency Consistent:** Yes (all toman)

## Risk Assessment

| Risk | Status | Mitigation |
|------|--------|------------|
| Data Loss | ✅ Low | Dev/staging, no production data |
| Breaking Changes | ✅ Low | Comprehensive testing |
| Import Errors | ✅ Low | Verification scripts |
| Database Issues | ✅ Low | Backup + rollback plan |

---

# 🚨 Troubleshooting Guide

## Common Issues

### Issue 1: Import Errors After Deletion

**Error:**
```
ImportError: cannot import name 'YooKassaService'
```

**Solution:**
1. Find file with error
2. Remove import line
3. Check if file needs surgical removal (Week 2)
4. Note in PR

### Issue 2: Tests Failing

**Error:**
```
test_yookassa_payment ... FAILED
```

**Solution:**
```python
@pytest.mark.skip(reason="Russian gateway removed")
def test_yookassa_payment():
    pass
```

### Issue 3: Database Migration Fails

**Error:**
```
alembic.util.exc.CommandError: Can't locate revision identified by 'xxx'
```

**Solution:**
1. Check migration history: `alembic history`
2. Verify down_revision correct
3. If needed, restore from backup

### Issue 4: Application Won't Start

**Error:**
```
AttributeError: 'NoneType' object has no attribute 'yookassa_service'
```

**Solution:**
1. Find reference in code
2. Remove or replace with Iranian gateway
3. Test again

---

# 📞 Support & Questions

## Resources

- **Master Plan:** `russian-artifacts-removal-plan.md`
- **Execution Guide:** `cleanup-execution-guide.md`
- **Database Audit:** `database-audit-report.md`
- **Readiness Report:** `implementation-readiness-report-2025-12-26.md`

## Contact

- **PM:** K4lantar4
- **Questions:** Create issue or ask in PR

---

# ✅ Definition of Done

این Guide زمانی Complete است که:

1. ✅ Week 1: 27 files deleted, 3 files split
2. ✅ Week 2: 28 files cleaned, 4 files split, DB prep done
3. ✅ Week 3: 7 tables dropped, currency migrated, tests pass
4. ✅ Week 4: FRs added, docs updated, Epic creation started

**Total Duration:** 4 weeks (20 working days)
**Status:** Ready for execution

---

**Master Cleanup Guide - Complete**
**Version:** 1.0
**Last Updated:** 2025-12-26
**Next Review:** After Week 1 completion

---

*این Guide شامل تمام مراحل 4 هفته‌ای cleanup و آماده‌سازی codebase است.*

