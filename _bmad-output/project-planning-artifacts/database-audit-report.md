# Database Audit Report - Russian Payment Gateways

**Project:** remnabot Multi-Tenant SaaS
**Author:** K4lantar4
**Date:** 2025-12-26
**Purpose:** Identify all Russian payment gateway database artifacts for removal
**Related:** Russian Artifacts Removal Plan

---

## Executive Summary

### Audit Scope

Complete audit of database layer to identify:
1. Russian payment gateway tables
2. Migration files creating these tables
3. Foreign key dependencies
4. Currency (kopek) usage in columns

### Key Findings

**Database Tables:** 7 Russian gateway tables identified in `models.py`
**Migration Files:** 1 confirmed (Platega), 6 expected but not found in current migrations
**Foreign Keys:** Standard pattern - user_id, transaction_id
**Currency Columns:** Multiple tables using "amount_kopeks"

---

## Russian Gateway Tables

### Confirmed in models.py

| Table Name | Model Class | Lines in models.py | Status |
|------------|-------------|-------------------|--------|
| `yookassa_payments` | YooKassaPayment | ~102-149 | ✅ Confirmed |
| `heleket_payments` | HeleketPayment | ~200-263 | ✅ Confirmed |
| `mulenpay_payments` | MulenPayPayment | ~266-306 | ✅ Confirmed |
| `pal24_payments` | Pal24Payment | ~309-368 | ✅ Confirmed |
| `wata_payments` | WataPayment | ~371-418 | ✅ Confirmed |
| `platega_payments` | PlategaPayment | ~421-466 | ✅ Confirmed |
| `tribute_payments` | TributePayment | TBD | ⚠️ Not found in grep |

**Total:** 6 confirmed tables + 1 possible (Tribute)

### Table Structure Analysis

**Common Pattern (all gateway tables):**

```sql
CREATE TABLE {gateway}_payments (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    {gateway}_specific_id VARCHAR/INTEGER,
    amount_kopeks INTEGER NOT NULL,        -- ⚠️ Russian currency
    currency VARCHAR DEFAULT 'RUB',        -- ⚠️ Russian currency
    status VARCHAR,
    is_paid BOOLEAN,
    paid_at DATETIME,
    transaction_id INTEGER,
    created_at DATETIME,
    updated_at DATETIME,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE SET NULL
);
```

### Foreign Key Dependencies

**Incoming (pointing TO gateway tables):**
- None identified - gateway tables are leaf nodes

**Outgoing (pointing FROM gateway tables):**
- `user_id` → `users.id` (ON DELETE CASCADE)
- `transaction_id` → `transactions.id` (ON DELETE SET NULL)

**Impact of Deletion:**
- ✅ Safe to drop - no tables reference gateway tables
- ⚠️ Will cascade delete if users are deleted (but we're dropping tables anyway)
- ✅ Transactions will have transaction_id set to NULL (acceptable)

---

## Migration Files Analysis

### Confirmed Migration Files

#### 1. Platega Payments

**File:** `2b3c1d4e5f6a_add_platega_payments.py`
**Down Revision:** `9f0f2d5a1c7b` (add_polls_tables)
**Status:** ✅ Found

**Details:**
- Creates `platega_payments` table
- Creates 5 indexes
- Has proper downgrade() function
- Uses `amount_kopeks` column
- Uses `currency` with default 'RUB'

**Rollback Strategy:**
```python
# Already has downgrade function
def downgrade() -> None:
    op.drop_index(...)
    op.drop_table("platega_payments")
```

### Missing Migration Files

**Expected but NOT found in current migrations:**

| Gateway | Expected Migration | Status |
|---------|-------------------|--------|
| YooKassa | `*_add_yookassa_payments.py` | ❌ Not found |
| Heleket | `*_add_heleket_payments.py` | ❌ Not found |
| MulenPay | `*_add_mulenpay_payments.py` | ❌ Not found |
| Pal24 | `*_add_pal24_payments.py` | ❌ Not found |
| WATA | `*_add_wata_payments.py` | ❌ Not found |
| Tribute | `*_add_tribute_payments.py` | ❌ Not found |

**Possible Explanations:**
1. Tables created in initial migration (before Alembic)
2. Tables created manually in database
3. Migrations deleted/squashed in past
4. Tables in older migration history not in current versions/

**Implication:**
- Need to create manual DROP TABLE migrations
- Cannot rely on migration downgrade
- Must verify tables exist in actual database before dropping

### Migration Timeline

**Current Migrations (12 files):**
1. `1b2e3d4f5a6b` - add_pinned_start_mode_and_user_last_pin
2. `1f5f3a3f5a4d` - add_promo_groups_and_user_fk
3. `2b3c1d4e5f6a` - add_platega_payments ⚠️ **RUSSIAN GATEWAY**
4. `4b6b0f58c8f9` - add_period_discounts_to_promo_groups
5. `5d1f1f8b2e9a` - add_advertising_campaigns
6. `5f2a3e099427` - add_media_fields_to_pinned_messages
7. `7a3c0b8f5b84` - add_send_before_menu_to_pinned_messages
8. `8fd1e338eb45` - add_sent_notifications_table
9. `9f0f2d5a1c7b` - add_polls_tables
10. `c2f9c3b5f5c4` - add_subscription_events_table
11. `c9c71d04f0a1` - add_pinned_messages_table
12. `e3c1e0b5b4a7` - add_referral_commission_percent_to_users

**Action Required:**
- Rollback migration `2b3c1d4e5f6a` (Platega)
- Create new migration to drop other 6 gateway tables

---

## Currency (Kopek) Usage

### Database Columns

**From models.py analysis:**

| Table | Column | Type | Default | Action |
|-------|--------|------|---------|--------|
| `yookassa_payments` | `amount_kopeks` | INTEGER | - | DROP with table |
| `mulenpay_payments` | `amount_kopeks` | INTEGER | - | DROP with table |
| `platega_payments` | `amount_kopeks` | INTEGER | - | DROP with table |
| `heleket_payments` | `amount_*` | INTEGER | - | DROP with table |
| `pal24_payments` | `amount_*` | INTEGER | - | DROP with table |
| `wata_payments` | `amount_*` | INTEGER | - | DROP with table |

**Note:** Gateway tables will be dropped entirely, so no need to migrate kopek columns in these tables.

### Core Tables (Need Migration)

**Expected kopek usage in core tables:**
- `subscriptions.price_kopeks` (probable)
- `transactions.amount_kopeks` (probable)
- `pricing.amount_kopeks` (probable)
- `promocodes.discount_kopeks` (probable)

**Action Required:**
- Audit core tables for kopek columns
- Create migration: add toman columns
- Convert data: kopek → toman
- Deprecate kopek columns

---

## Data Volume Analysis

### Row Count Estimation

**Status:** ⚠️ REQUIRES DATABASE ACCESS

To complete this section, run:

```sql
-- Connect to database
psql -U postgres -d remnabot

-- Count rows in each gateway table
SELECT 'yookassa_payments' as table_name, COUNT(*) as row_count FROM yookassa_payments
UNION ALL
SELECT 'heleket_payments', COUNT(*) FROM heleket_payments
UNION ALL
SELECT 'mulenpay_payments', COUNT(*) FROM mulenpay_payments
UNION ALL
SELECT 'pal24_payments', COUNT(*) FROM pal24_payments
UNION ALL
SELECT 'wata_payments', COUNT(*) FROM wata_payments
UNION ALL
SELECT 'platega_payments', COUNT(*) FROM platega_payments;
```

**Expected Results:**
- If production data: Could be thousands of rows
- If staging/dev: Likely minimal or zero rows

### Data Archival Decision

**Options:**

1. **Archive to JSON:**
   - Export all gateway payment data to JSON files
   - Store in `data/archives/russian_gateways_YYYYMMDD.json`
   - Keep for compliance/historical reference

2. **Archive to Separate Table:**
   - Create `archived_payments` table
   - Move all gateway payment data
   - Keep in database but separate

3. **Delete Without Archive:**
   - Drop tables directly
   - No historical data preserved
   - Simplest approach

**Decision:** Option 3 (Delete Without Archive) ✅
- **Environment:** Dev/staging (no production data)
- **Data Status:** No data exists in gateway tables
- **Rationale:** Simplest approach, no compliance requirements
- **Approved by:** K4lantar4 on 2025-12-26

---

## Removal Strategy

### Phase 1: Data Archive (Optional)

**If archiving to JSON:**

```python
# Migration: archive_russian_gateway_data.py

def upgrade():
    import json
    from datetime import datetime
    
    # Get database connection
    conn = op.get_bind()
    
    # Archive each gateway table
    gateways = ['yookassa', 'heleket', 'mulenpay', 'pal24', 'wata', 'platega']
    
    for gateway in gateways:
        table = f"{gateway}_payments"
        
        # Query all data
        result = conn.execute(f"SELECT * FROM {table}")
        rows = [dict(row) for row in result]
        
        # Save to JSON
        filename = f"data/archives/{gateway}_payments_{datetime.now().strftime('%Y%m%d')}.json"
        with open(filename, 'w') as f:
            json.dump(rows, f, indent=2, default=str)
        
        print(f"Archived {len(rows)} rows from {table} to {filename}")

def downgrade():
    # Cannot restore from JSON automatically
    pass
```

### Phase 2: Table Drops

**Migration:** `drop_russian_gateway_tables.py`

```python
def upgrade():
    # Drop in reverse dependency order
    tables = [
        'platega_payments',
        'wata_payments',
        'pal24_payments',
        'mulenpay_payments',
        'heleket_payments',
        'yookassa_payments',
    ]
    
    for table in tables:
        # Check if table exists first
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        
        if table in inspector.get_table_names():
            op.drop_table(table)
            print(f"Dropped table: {table}")
        else:
            print(f"Table not found (skipping): {table}")

def downgrade():
    # Cannot recreate without original migrations
    # Would need to restore from backup
    raise NotImplementedError("Cannot downgrade - restore from backup if needed")
```

### Phase 3: Model Cleanup

**File:** `app/database/models.py`

**Actions:**
1. Delete 6 model classes (~320 lines)
2. Update PaymentMethod enum
3. Remove imports if any

**Before:**
```python
class PaymentMethod(Enum):
    TELEGRAM_STARS = "telegram_stars"
    TRIBUTE = "tribute"           # ❌ REMOVE
    YOOKASSA = "yookassa"         # ❌ REMOVE
    CRYPTOBOT = "cryptobot"
    HELEKET = "heleket"           # ❌ REMOVE
    MULENPAY = "mulenpay"         # ❌ REMOVE
    PAL24 = "pal24"               # ❌ REMOVE
    WATA = "wata"                 # ❌ REMOVE
    PLATEGA = "platega"           # ❌ REMOVE
    MANUAL = "manual"
```

**After:**
```python
class PaymentMethod(Enum):
    TELEGRAM_STARS = "telegram_stars"
    CRYPTOBOT = "cryptobot"
    MANUAL = "manual"
    ZARINPAL = "zarinpal"         # ✅ ADD
    CARD_TO_CARD = "card_to_card" # ✅ ADD
```

---

## Risk Assessment

### Data Loss Risk

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Accidental data loss** | LOW | HIGH | Full backup before any changes |
| **Cannot restore** | MEDIUM | MEDIUM | JSON archive + backup |
| **Foreign key violations** | LOW | MEDIUM | Verified no incoming FKs |

### Migration Risk

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Migration fails** | LOW | HIGH | Test in staging first |
| **Cannot rollback** | MEDIUM | HIGH | Full backup + manual restore procedure |
| **Orphaned data** | LOW | LOW | Transactions will have NULL transaction_id (acceptable) |

### Application Risk

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| **Code still references tables** | HIGH | HIGH | Grep all code before migration |
| **Tests fail** | MEDIUM | MEDIUM | Update tests first |
| **Runtime errors** | MEDIUM | HIGH | Staging testing + gradual rollout |

---

## Verification Checklist

### Pre-Migration

- [ ] Full database backup created
- [ ] Row counts documented for all gateway tables
- [ ] Foreign key dependencies verified
- [ ] No incoming foreign keys confirmed
- [ ] Archive strategy decided
- [ ] Staging environment prepared

### During Migration

- [ ] Archive migration runs successfully (if applicable)
- [ ] Drop migration runs successfully
- [ ] No errors in migration logs
- [ ] All tables dropped confirmed

### Post-Migration

- [ ] Tables no longer exist in database
- [ ] No foreign key violations
- [ ] Application starts successfully
- [ ] No runtime errors in logs
- [ ] Tests pass
- [ ] Manual testing completed

### Verification Commands

```sql
-- Verify tables dropped
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name LIKE '%yookassa%'
   OR table_name LIKE '%heleket%'
   OR table_name LIKE '%tribute%'
   OR table_name LIKE '%mulenpay%'
   OR table_name LIKE '%pal24%'
   OR table_name LIKE '%platega%'
   OR table_name LIKE '%wata%';
-- Should return 0 rows

-- Check for orphaned foreign keys
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE confrelid::regclass::text LIKE '%yookassa%'
   OR confrelid::regclass::text LIKE '%heleket%'
   -- ... etc
-- Should return 0 rows
```

---

## Next Steps

### Immediate Actions

1. **Database Access Required:**
   - [ ] Get production database credentials (read-only)
   - [ ] Run row count queries
   - [ ] Verify tables exist
   - [ ] Document actual table structures

2. **Decision Required:**
   - [ ] Archive data or not? (Recommendation: YES)
   - [ ] Archive format? (Recommendation: JSON)
   - [ ] Retention period? (Recommendation: 1 year)

3. **Preparation:**
   - [ ] Create backup procedure document
   - [ ] Create rollback procedure document
   - [ ] Schedule staging environment testing

### Week 2 Day 6-7 Tasks

Based on this audit:

1. Create migration: `archive_russian_gateway_data.py`
2. Create migration: `drop_russian_gateway_tables.py`
3. Test migrations in local environment
4. Test migrations in staging environment
5. Document rollback procedure
6. Get approval for production execution

---

## Appendix A: Table Structures

### YooKassa Payments

```python
class YooKassaPayment(Base):
    __tablename__ = "yookassa_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    yookassa_payment_id = Column(String(255), unique=True, nullable=False, index=True)
    amount_kopeks = Column(Integer, nullable=False)
    currency = Column(String(3), default="RUB", nullable=False)
    # ... more columns
```

### Platega Payments (from migration)

```sql
CREATE TABLE platega_payments (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    platega_transaction_id VARCHAR(255) UNIQUE,
    correlation_id VARCHAR(64) UNIQUE NOT NULL,
    amount_kopeks INTEGER NOT NULL,
    currency VARCHAR(10) DEFAULT 'RUB' NOT NULL,
    description TEXT,
    payment_method_code INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'PENDING' NOT NULL,
    is_paid BOOLEAN DEFAULT false NOT NULL,
    paid_at TIMESTAMP,
    redirect_url TEXT,
    return_url TEXT,
    failed_url TEXT,
    payload VARCHAR(255),
    metadata_json JSON,
    callback_payload JSON,
    expires_at TIMESTAMP,
    transaction_id INTEGER,
    created_at TIMESTAMP DEFAULT now() NOT NULL,
    updated_at TIMESTAMP DEFAULT now() NOT NULL,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE SET NULL
);
```

---

## Appendix B: Rollback Procedure

### Emergency Rollback

**If migration fails or causes issues:**

```bash
# 1. Stop application immediately
systemctl stop remnabot

# 2. Restore from backup
pg_restore -U postgres -d remnabot backup_pre_cleanup_YYYYMMDD.dump

# 3. Verify restoration
psql -U postgres -d remnabot -c "\dt" | grep -E "yookassa|heleket"
# Should show tables exist again

# 4. Rollback code changes
git revert <migration-commit-hash>

# 5. Restart application
systemctl start remnabot

# 6. Verify application working
curl http://localhost:8000/health
```

---

**Audit Status:** COMPLETE (pending database access for row counts)
**Next Action:** Get database credentials and run row count queries
**Approval Required:** Data archival strategy decision

---

*Database Audit Report - 2025-12-26*
*Part of Week 1 Days 1-2: Database Audit + Russian Artifacts Removal Plan*

