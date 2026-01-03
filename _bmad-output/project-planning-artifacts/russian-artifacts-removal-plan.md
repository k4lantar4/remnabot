# Russian Artifacts Removal Plan

**Project:** remnabot Multi-Tenant SaaS
**Author:** K4lantar4
**Date:** 2025-12-26
**Status:** IN PROGRESS
**Related:** Implementation Readiness Report 2025-12-26

---

## Executive Summary

### Scope of Contamination

This document outlines the complete removal strategy for Russian payment gateway integrations and Russian language artifacts from the remnabot codebase.

**Contamination Extent:**
- **65+ files** across 4 layers (External, Services, Handlers, Database)
- **7 database tables** with payment gateway data
- **6-7 migrations** requiring rollback
- **~15,000 lines of code** affected
- **10+ files** with Russian currency (kopek) references

**Timeline:** 3 weeks (15 working days)
**Risk Level:** HIGH - requires careful execution

---

## Russian Payment Gateways to Remove

### Gateway List

| Gateway | Status | Market | Reason for Removal |
|---------|--------|--------|-------------------|
| **YooKassa** | ❌ Remove | Russia | Russian market only |
| **Heleket** | ❌ Remove | Russia | Russian market only |
| **Tribute** | ❌ Remove | Russia | Russian market only |
| **MulenPay** | ❌ Remove | Russia | Russian market only |
| **Pal24** | ❌ Remove | Russia | Russian market only |
| **Platega** | ❌ Remove | Russia | Russian market only |
| **WATA** | ❌ Remove | Russia | Russian market only |

### Gateways to Keep

| Gateway | Status | Market | Reason |
|---------|--------|--------|--------|
| **ZarinPal** | ✅ Keep | Iran | Primary Iranian gateway |
| **Card-to-Card** | ✅ Keep | Iran | Manual approval, high trust |
| **CryptoBot** | ✅ Keep | International | Crypto payments |
| **Telegram Stars** | ⚠️ Evaluate | Global | Telegram native |

---

## Layer-by-Layer Analysis

### Layer 1: External (7 files, 1,480 lines)

#### Files for Complete Deletion

| File | Lines | Gateway | Action | Priority |
|------|-------|---------|--------|----------|
| `app/external/yookassa_webhook.py` | 394 | YooKassa | DELETE | P0 |
| `app/external/wata_webhook.py` | 262 | WATA | DELETE | P0 |
| `app/external/pal24_client.py` | 216 | Pal24 | DELETE | P0 |
| `app/external/heleket.py` | 174 | Heleket | DELETE | P0 |
| `app/external/pal24_webhook.py` | 162 | Pal24 | DELETE | P0 |
| `app/external/tribute.py` | 161 | Tribute | DELETE | P0 |
| `app/external/heleket_webhook.py` | 111 | Heleket | DELETE | P0 |

**Deletion Strategy:**
```bash
# Week 1, Day 3 - Safe to delete (no dependencies expected)
rm app/external/yookassa_webhook.py
rm app/external/wata_webhook.py
rm app/external/pal24_client.py
rm app/external/pal24_webhook.py
rm app/external/heleket.py
rm app/external/heleket_webhook.py
rm app/external/tribute.py
```

**Verification:**
- Grep for imports of these files
- Check if any handlers reference them
- Run tests after deletion

---

### Layer 2: Services (24 files, ~5,000 lines)

#### Gateway-Specific Service Files (Complete Deletion)

| File | Gateway | Action | Priority |
|------|---------|--------|----------|
| `app/services/wata_service.py` | WATA | DELETE | P0 |
| `app/services/yookassa_service.py` | YooKassa | DELETE | P0 |
| `app/services/tribute_service.py` | Tribute | DELETE | P0 |
| `app/services/mulenpay_service.py` | MulenPay | DELETE | P0 |
| `app/services/pal24_service.py` | Pal24 | DELETE | P0 |
| `app/services/platega_service.py` | Platega | DELETE | P0 |

#### Payment Module Files (Complete Deletion)

| File | Gateway | Action | Priority |
|------|---------|--------|----------|
| `app/services/payment/heleket.py` | Heleket | DELETE | P0 |
| `app/services/payment/mulenpay.py` | MulenPay | DELETE | P0 |
| `app/services/payment/pal24.py` | Pal24 | DELETE | P0 |
| `app/services/payment/tribute.py` | Tribute | DELETE | P0 |
| `app/services/payment/wata.py` | WATA | DELETE | P0 |
| `app/services/payment/platega.py` | Platega | DELETE | P0 |
| `app/services/payment/yookassa.py` | YooKassa | DELETE | P0 |

**Total for Deletion:** 13 files

#### Contaminated Core Service Files (Surgical Removal Required)

| File | Lines | Russian References | Action | Priority |
|------|-------|-------------------|--------|----------|
| `app/services/subscription_service.py` | 1,249 | Gateway imports, kopek | MODIFY | P0 |
| `app/services/user_service.py` | 1,139 | Payment history | MODIFY | P0 |
| `app/services/system_settings_service.py` | 1,470 | Gateway config | MODIFY | P1 |
| `app/services/payment_service.py` | TBD | Gateway orchestration | MODIFY | P0 |
| `app/services/payment_verification_service.py` | 828 | Gateway verification | MODIFY | P0 |
| `app/services/admin_notification_service.py` | 1,560 | Gateway notifications | MODIFY | P1 |
| `app/services/backup_service.py` | 1,556 | Gateway data backup | MODIFY | P2 |
| `app/services/poll_service.py` | TBD | Gateway polling | MODIFY | P2 |
| `app/services/payment/__init__.py` | TBD | Gateway exports | MODIFY | P0 |
| `app/services/payment/common.py` | TBD | Common gateway utils | MODIFY | P0 |

**Surgical Removal Strategy:**

For each file:
1. Search for gateway-specific imports
2. Remove import statements
3. Remove gateway-specific code blocks
4. Remove gateway enum references
5. Update tests
6. Verify functionality

**Example for `subscription_service.py`:**
```python
# BEFORE
from app.services.yookassa_service import YooKassaService
from app.services.wata_service import WataService

# AFTER - Remove these imports completely
```

---

### Layer 3: Handlers (23 files, ~8,000 lines)

#### Balance Handlers (Complete Deletion)

| File | Gateway | Action | Priority |
|------|---------|--------|----------|
| `app/handlers/balance/wata.py` | WATA | DELETE | P0 |
| `app/handlers/balance/yookassa.py` | YooKassa | DELETE | P0 |
| `app/handlers/balance/heleket.py` | Heleket | DELETE | P0 |
| `app/handlers/balance/mulenpay.py` | MulenPay | DELETE | P0 |
| `app/handlers/balance/pal24.py` | Pal24 | DELETE | P0 |
| `app/handlers/balance/platega.py` | Platega | DELETE | P0 |
| `app/handlers/balance/tribute.py` | Tribute | DELETE | P0 |

**Total for Deletion:** 7 files

#### Contaminated Core Handler Files (Surgical Removal Required)

| File | Lines | Russian References | Action | Priority |
|------|-------|-------------------|--------|----------|
| `app/handlers/subscription/purchase.py` | 3,455 | Gateway buttons, flows | MODIFY | P0 |
| `app/handlers/webhooks.py` | TBD | Gateway webhook routes | MODIFY | P0 |
| `app/handlers/simple_subscription.py` | 2,420 | Gateway options | MODIFY | P0 |
| `app/handlers/balance/main.py` | TBD | Gateway balance UI | MODIFY | P0 |
| `app/handlers/subscription/pricing.py` | TBD | Gateway-specific pricing | MODIFY | P1 |
| `app/handlers/subscription/promo.py` | TBD | Gateway promos | MODIFY | P1 |
| `app/handlers/subscription/common.py` | TBD | Shared gateway logic | MODIFY | P1 |
| `app/handlers/subscription/countries.py` | TBD | Gateway country rules | MODIFY | P2 |
| `app/handlers/server_status.py` | TBD | Gateway status | MODIFY | P2 |
| `app/handlers/polls.py` | TBD | Gateway polls | MODIFY | P2 |
| `app/handlers/admin/tickets.py` | 1,248 | Gateway support | MODIFY | P1 |
| `app/handlers/admin/promo_offers.py` | 2,387 | Gateway offers | MODIFY | P1 |
| `app/handlers/admin/payments.py` | TBD | Gateway admin UI | MODIFY | P0 |
| `app/handlers/admin/bot_configuration.py` | 2,800 | Gateway settings | MODIFY | P0 |

**Surgical Removal Strategy:**

For handler files:
1. Remove gateway-specific inline keyboard buttons
2. Remove gateway callback handlers
3. Remove gateway state machines
4. Update payment method selection UI
5. Update tests

**Example for `subscription/purchase.py`:**
```python
# BEFORE - Payment method selection
methods = [
    ("💳 YooKassa", "yookassa"),
    ("🏦 Heleket", "heleket"),
    # ... other Russian gateways
]

# AFTER - Only Iranian gateways
methods = [
    ("💳 ZarinPal", "zarinpal"),
    ("💳 کارت به کارت", "card_to_card"),
    ("💰 کیف پول", "wallet"),
]
```

---

### Layer 4: Database (7 tables, 6-7 migrations)

#### Database Tables for Deletion

| Table | Estimated Rows | Data Value | Action | Priority |
|-------|---------------|------------|--------|----------|
| `yookassa_payments` | TBD | Historical | ARCHIVE + DROP | P0 |
| `heleket_payments` | TBD | Historical | ARCHIVE + DROP | P0 |
| `mulenpay_payments` | TBD | Historical | ARCHIVE + DROP | P0 |
| `pal24_payments` | TBD | Historical | ARCHIVE + DROP | P0 |
| `wata_payments` | TBD | Historical | ARCHIVE + DROP | P0 |
| `platega_payments` | TBD | Historical | ARCHIVE + DROP | P0 |
| `tribute_payments` | TBD | Historical | ARCHIVE + DROP | P0 |

#### Database Models for Removal

**From `app/database/models.py`:**

```python
# REMOVE THESE CLASSES (Lines ~102-465):
class YooKassaPayment(Base):  # ~50 lines
class HeleketPayment(Base):   # ~60 lines
class MulenPayPayment(Base):  # ~45 lines
class Pal24Payment(Base):     # ~55 lines
class WataPayment(Base):      # ~50 lines
class PlategaPayment(Base):   # ~60 lines
# Total: ~320 lines to remove

# MODIFY THIS ENUM:
class PaymentMethod(Enum):
    # REMOVE:
    TRIBUTE = "tribute"
    YOOKASSA = "yookassa"
    HELEKET = "heleket"
    MULENPAY = "mulenpay"
    PAL24 = "pal24"
    WATA = "wata"
    PLATEGA = "platega"
    
    # KEEP:
    TELEGRAM_STARS = "telegram_stars"
    CRYPTOBOT = "cryptobot"
    MANUAL = "manual"
    
    # ADD:
    ZARINPAL = "zarinpal"
    CARD_TO_CARD = "card_to_card"
```

#### Migration Files

**Confirmed Migrations:**
- `2b3c1d4e5f6a_add_platega_payments.py` - ❌ ROLLBACK

**Expected Migrations (need audit):**
- `*_add_yookassa_payments.py` - ❌ ROLLBACK
- `*_add_heleket_payments.py` - ❌ ROLLBACK
- `*_add_mulenpay_payments.py` - ❌ ROLLBACK
- `*_add_pal24_payments.py` - ❌ ROLLBACK
- `*_add_wata_payments.py` - ❌ ROLLBACK
- `*_add_tribute_payments.py` - ❌ ROLLBACK (if exists)

**Migration Strategy:**

```bash
# Week 3, Days 1-3
# 1. Identify all gateway-related migrations
alembic history | grep -E "yookassa|heleket|tribute|mulen|pal24|platega|wata"

# 2. Create data archive migration
alembic revision -m "archive_russian_gateway_data"
# Exports data to JSON files for compliance/historical reference

# 3. Create rollback migration
alembic revision -m "drop_russian_gateway_tables"
# Drops all 7 tables

# 4. Execute in staging
alembic upgrade head

# 5. Verify
# Check no foreign key violations
# Check no orphaned data
```

---

## Currency Migration (Kopek → Toman)

### Files with "kopek" References

**Service Layer (10+ files):**
- `app/services/partner_stats_service.py`
- `app/services/promo_group_assignment.py`
- `app/services/pal24_service.py` (will be deleted)
- `app/services/admin_notification_service.py`
- `app/services/promocode_service.py`
- `app/services/reporting_service.py`
- `app/services/wata_service.py` (will be deleted)
- `app/services/poll_service.py`
- `app/services/subscription_service.py`
- `app/services/referral_service.py`

### Database Columns with "kopek"

**From Grep Analysis:**
- `yookassa_payments.amount_kopeks` (table will be dropped)
- `mulenpay_payments.amount_kopeks` (table will be dropped)
- `platega_payments.amount_kopeks` (table will be dropped)
- Likely in `subscriptions`, `pricing`, `transactions` tables

### Currency Conversion Strategy

**Conversion Rate:** TBD (requires business decision)
- Option 1: Direct conversion (e.g., 1 kopek = X tomans)
- Option 2: Rebase all prices (new pricing in tomans)

**Migration Approach:**

```python
# Week 3, Days 4-5
# Migration: add_toman_columns.py

def upgrade():
    # 1. Add new toman columns
    op.add_column('subscriptions', 
                  sa.Column('price_tomans', sa.Integer(), nullable=True))
    op.add_column('transactions', 
                  sa.Column('amount_tomans', sa.Integer(), nullable=True))
    # ... other tables
    
    # 2. Convert existing data
    # amount_tomans = amount_kopeks * CONVERSION_RATE
    
    # 3. Make toman columns non-nullable
    op.alter_column('subscriptions', 'price_tomans', nullable=False)
    
    # 4. Deprecate kopek columns (keep for now)
    # Drop in later migration after verification

def downgrade():
    # Rollback strategy
    pass
```

---

## Removal Execution Plan

### Week 1: Days 3-5 (Safe Deletions)

**Goal:** Remove all isolated files with no external dependencies

**Files to Delete (20 files):**
- 7 External layer files
- 13 Service layer gateway-specific files (6 individual + 7 payment module)

**Steps:**
1. Create feature branch: `cleanup/russian-gateways-phase1`
2. Delete all 20 files
3. Search for any imports of deleted files
4. Run tests
5. Commit with detailed message
6. Create PR for review

**Verification:**
```bash
# Check no imports remain
grep -r "from app.external.yookassa_webhook" app/
grep -r "from app.services.wata_service" app/
# ... for all deleted files

# Run tests
pytest tests/ -v
```

---

### Week 1: Days 6-7 + Week 2: Days 1-3 (Surgical Removal)

**Goal:** Remove Russian gateway code from contaminated core files

**Files to Modify (23 files):**
- 10 Service files (subscription_service, user_service, etc.)
- 13 Handler files (subscription/purchase, admin/bot_configuration, etc.)

**Process for Each File:**

1. **Analyze:**
   - Identify all Russian gateway references
   - Map dependencies
   - Plan removal strategy

2. **Modify:**
   - Remove gateway imports
   - Remove gateway-specific code blocks
   - Remove enum references
   - Update inline keyboards (handlers)
   - Update callback handlers (handlers)

3. **Test:**
   - Run unit tests for modified file
   - Run integration tests
   - Manual testing if critical

4. **Document:**
   - Note any business logic changes
   - Update comments/docstrings

**Priority Order:**
1. P0 files (blocking): payment_service.py, subscription/purchase.py, webhooks.py
2. P1 files (important): subscription_service.py, user_service.py, admin/payments.py
3. P2 files (nice to have): backup_service.py, polls.py

---

### Week 2: Days 6-7 (Database Preparation)

**Goal:** Prepare for database cleanup

**Tasks:**
1. **Audit:**
   - Count rows in each Russian gateway table
   - Identify foreign key constraints
   - Document data dependencies

2. **Archive Strategy:**
   - Decide: Keep historical data or not?
   - If keep: Create archive tables or JSON export
   - If not: Document decision for compliance

3. **Migration Plan:**
   - Write migration: `archive_russian_gateway_data.py`
   - Write migration: `drop_russian_gateway_tables.py`
   - Test migrations in local/staging

4. **Rollback Plan:**
   - Document emergency rollback procedure
   - Test rollback in staging
   - Prepare data restore scripts (if needed)

---

### Week 3: Days 1-3 (Database Cleanup)

**Goal:** Execute database table drops and model cleanup

**Tasks:**

1. **Backup (Critical):**
   ```bash
   # Full database backup before any changes
   pg_dump -h localhost -U postgres remnabot > backup_pre_cleanup_$(date +%Y%m%d).sql
   ```

2. **Archive Data (if decided):**
   ```bash
   alembic upgrade head  # Runs archive migration
   # Exports gateway payment data to JSON
   ```

3. **Drop Tables:**
   ```bash
   alembic upgrade head  # Runs drop migration
   ```

4. **Model Cleanup:**
   - Remove 7 payment model classes from `models.py` (~320 lines)
   - Remove 7 enum values from `PaymentMethod`
   - Add new enum values: `ZARINPAL`, `CARD_TO_CARD`

5. **Verification:**
   ```bash
   # Check tables dropped
   psql -U postgres -d remnabot -c "\dt" | grep -E "yookassa|heleket|tribute"
   # Should return nothing
   
   # Check no foreign key violations
   # Run application and monitor logs
   ```

---

### Week 3: Days 4-5 (Currency Migration)

**Goal:** Convert kopek → toman across all tables

**Tasks:**

1. **Business Decision:**
   - Finalize conversion rate or repricing strategy
   - Get approval from stakeholders

2. **Migration Creation:**
   ```python
   # add_toman_currency.py
   def upgrade():
       # Add toman columns to all financial tables
       # Convert existing kopek values
       # Set toman as primary, kopek as deprecated
   ```

3. **Code Updates:**
   - Update all service files using "kopek"
   - Update display logic (kopek → toman)
   - Update calculations
   - Update tests

4. **Verification:**
   ```bash
   # Check all prices displayed correctly
   # Check calculations correct
   # Check historical data integrity
   ```

---

### Week 3: Days 6-7 (Testing & Verification)

**Goal:** Comprehensive testing of all changes

**Testing Checklist:**

1. **Unit Tests:**
   - [ ] All service tests pass
   - [ ] All handler tests pass
   - [ ] All CRUD tests pass
   - [ ] No Russian gateway tests remain

2. **Integration Tests:**
   - [ ] Payment flow with ZarinPal works
   - [ ] Card-to-card flow works
   - [ ] Wallet flow works
   - [ ] No Russian gateway references in logs

3. **Manual Testing:**
   - [ ] Purchase subscription via ZarinPal
   - [ ] Purchase via card-to-card
   - [ ] Purchase via wallet
   - [ ] Admin payment approval works
   - [ ] All prices display in toman
   - [ ] No UI mentions Russian gateways

4. **Database Integrity:**
   - [ ] No orphaned foreign keys
   - [ ] All migrations reversible
   - [ ] Backup/restore works

5. **Code Quality:**
   - [ ] No Russian comments remain (if removing)
   - [ ] No "kopek" references remain
   - [ ] All TODO/FIXME addressed
   - [ ] Linter passes

---

## Risk Management

### High-Risk Activities

| Activity | Risk Level | Mitigation |
|----------|-----------|------------|
| **Database table drops** | 🔴 CRITICAL | Full backup, staging test, rollback plan |
| **Currency migration** | 🔴 HIGH | Double-check calculations, staging test |
| **Enum changes** | 🟠 MEDIUM | Update all references first |
| **Large file modifications** | 🟠 MEDIUM | Split files first (Week 1 Days 6-7) |

### Rollback Procedures

**If Database Migration Fails:**
```bash
# 1. Stop application
systemctl stop remnabot

# 2. Restore from backup
psql -U postgres remnabot < backup_pre_cleanup_YYYYMMDD.sql

# 3. Rollback code changes
git revert <commit-hash>

# 4. Restart
systemctl start remnabot
```

**If Code Changes Break Production:**
```bash
# 1. Revert to previous commit
git revert <commit-hash>

# 2. Deploy previous version
# 3. Investigate issue in staging
```

---

## Success Criteria

### Completion Checklist

- [ ] All 7 external files deleted
- [ ] All 13 gateway service files deleted
- [ ] All 7 balance handler files deleted
- [ ] All 10 core service files cleaned (no Russian references)
- [ ] All 13 core handler files cleaned (no Russian references)
- [ ] All 7 database tables dropped
- [ ] All 7 model classes removed from models.py
- [ ] All 7 PaymentMethod enum values removed
- [ ] All "kopek" references converted to "toman"
- [ ] All currency values migrated
- [ ] All tests passing
- [ ] Manual testing completed
- [ ] Documentation updated
- [ ] Code review approved

### Verification Commands

```bash
# No Russian gateway imports
grep -r "yookassa\|heleket\|tribute\|mulenpay\|pal24\|platega\|wata" app/ | grep -v ".pyc" | grep -v "__pycache__"

# No kopek references
grep -r "kopek" app/ | grep -v ".pyc" | grep -v "__pycache__"

# No Russian gateway tables
psql -U postgres -d remnabot -c "\dt" | grep -E "yookassa|heleket|tribute|mulen|pal24|platega|wata"

# All tests pass
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Timeline Summary

| Week | Days | Activity | Deliverable |
|------|------|----------|-------------|
| **1** | 1-2 | Audit + Planning | This document + database audit |
| **1** | 3-5 | Delete isolated files | 20 files deleted, tests pass |
| **1** | 6-7 | Split EXTREME files | 3 files split into modules |
| **2** | 1-3 | Surgical removal | 23 files cleaned |
| **2** | 4-5 | Split CRITICAL files | 4 files split |
| **2** | 6-7 | Database prep | Migration scripts ready |
| **3** | 1-3 | Database cleanup | 7 tables dropped |
| **3** | 4-5 | Currency migration | All kopek → toman |
| **3** | 6-7 | Testing | All tests pass |

**Total:** 3 weeks, 15 working days

---

## Next Steps

**Immediate (Today):**
1. ✅ Complete this document
2. 🔄 Perform database audit (row counts, foreign keys)
3. 🔄 Identify all migration files with Russian gateways
4. 🔄 Get stakeholder approval for currency conversion rate

**Tomorrow:**
1. Begin Week 1 Day 3: Delete isolated files
2. Update TODO list progress
3. Create feature branch for cleanup

---

**Document Status:** DRAFT → IN REVIEW
**Next Review:** After database audit completion
**Approval Required From:** K4lantar4

---

*Russian Artifacts Removal Plan - 2025-12-26*
*Part of Implementation Readiness Phase*

