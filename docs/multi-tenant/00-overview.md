# Multi-Tenant Migration - Overview & Quick Start

**Version:** 1.0  
**Date:** 2025-12-12  
**Status:** Ready for Implementation

---

## Executive Summary

This document provides a comprehensive design for migrating the RemnaWave bot from a single-tenant to a multi-tenant SaaS architecture.

### What We're Building

- **Multiple bot instances** (tenants) running from a single codebase
- **Per-tenant feature flags** and configuration
- **Complete data isolation** between tenants
- **Tenant-specific payment methods** (card-to-card with rotation)
- **Wallet system** per tenant with traffic-based billing
- **API-based tenant management**

### Key Principles

1. **Single Codebase** - All tenants use the same code
2. **Runtime Configuration** - Features enabled/disabled via database
3. **Zero Technical Debt** - Clean, maintainable code
4. **Incremental Implementation** - Small, testable tasks
5. **Data Isolation** - `bot_id` in all tables

---

## Architecture Overview

### Current State (Single-Tenant)

```
┌─────────────────┐
│  Single Bot     │
│  Single DB      │
│  All Users      │
└─────────────────┘
```

### Target State (Multi-Tenant)

```
┌─────────────────────────────────────┐
│         Master Bot                   │
│  (Tenant Management)                 │
└─────────────────────────────────────┘
           │
           ├─── Tenant Bot 1 ─── Users 1
           ├─── Tenant Bot 2 ─── Users 2
           └─── Tenant Bot N ─── Users N
           
All share same codebase, isolated data
```

### Data Isolation Strategy

**Approach:** Row-Level Isolation with `bot_id`

- Every table has `bot_id` column
- All queries filter by `bot_id`
- Unique constraints: `(telegram_id, bot_id)` instead of just `telegram_id`
- Foreign keys cascade on delete

**Example:**
```sql
-- Before (single-tenant)
SELECT * FROM users WHERE telegram_id = 123456;

-- After (multi-tenant)
SELECT * FROM users WHERE telegram_id = 123456 AND bot_id = 1;
```

---

## Core Components

### 1. Bot Management

**Table:** `bots`
- Stores all bot instances (master + tenants)
- Each bot has unique Telegram token
- API token for management
- Wallet and billing info

### 2. Feature Flags

**Table:** `bot_feature_flags`
- Enable/disable features per tenant
- Runtime configuration
- Cached for performance

**Example Features:**
- `telegram_stars` - Telegram Stars payments
- `yookassa` - YooKassa payments
- `card_to_card` - Card-to-card payments
- `referral_program` - Referral system
- `support_tickets` - Support tickets

### 3. Tenant Configuration

**Table:** `bot_configurations`
- JSONB storage for flexible config
- Per-tenant settings
- Override defaults

### 4. Payment Cards (Card-to-Card)

**Table:** `tenant_payment_cards`
- Multiple cards per tenant
- Rotation strategies:
  - `round_robin` - Cycle through cards
  - `random` - Random selection
  - `time_based` - Rotate every N minutes
  - `weighted` - Based on success rate

---

## Quick Start Guide

### For Developers

1. **Read this overview** - Understand the architecture
2. **Review database schema** - See [Database Schema](./01-database-schema.md)
3. **Check code changes** - See [Code Changes](./02-code-changes.md)
4. **Follow workflow** - See [Workflow Guide](./07-workflow-guide.md)

### For Project Managers

1. **Review implementation tasks** - See [Implementation Tasks](./04-implementation-tasks.md)
2. **Check timeline** - 4 weeks estimated
3. **Review risks** - See [Migration Guide](./06-migration-guide.md)

### First Steps

1. ✅ Review all documentation
2. ✅ Set up development environment
3. ✅ Create feature branch
4. ✅ Start with Task 1 (Database Schema)

---

## Alternative Approaches Considered

### ❌ Separate Databases per Tenant

**Pros:**
- Complete isolation
- Easier backup/restore

**Cons:**
- Complex management
- Higher costs
- Harder to share data

**Decision:** Rejected - Too complex

### ❌ Schema per Tenant

**Pros:**
- Good isolation
- Shared infrastructure

**Cons:**
- Complex migrations
- Limited scalability

**Decision:** Rejected - Too complex

### ❌ Row-Level Security (RLS)

**Pros:**
- Database-level security

**Cons:**
- PostgreSQL-specific
- Performance overhead

**Decision:** Rejected - Overkill

### ✅ Single Codebase with bot_id (Selected)

**Pros:**
- Simple to implement
- Easy to maintain
- Good performance
- Flexible

**Cons:**
- Requires careful query design
- Need to ensure bot_id is always set

**Decision:** ✅ **Selected** - Best balance

---

## Risk Analysis

### High Risk

1. **Data Loss During Migration**
   - **Mitigation:** Full backup, test on staging
   - **Rollback:** Restore from backup

2. **Performance Degradation**
   - **Mitigation:** Add indexes, use caching
   - **Rollback:** Revert queries

3. **Breaking Changes**
   - **Mitigation:** Comprehensive testing
   - **Rollback:** Feature flag to disable

### Medium Risk

1. **Feature Flag Cache Issues**
   - **Mitigation:** Short TTL, cache invalidation
   - **Rollback:** Disable caching

2. **Bot Initialization Failures**
   - **Mitigation:** Retry logic, graceful degradation
   - **Rollback:** Disable failed bots

---

## Success Metrics

- ✅ All tenants isolated
- ✅ Feature flags working
- ✅ No performance degradation
- ✅ Zero data loss
- ✅ Clean code, no technical debt

---

## Next Steps

1. **Read [Database Schema](./01-database-schema.md)** - Understand data structure
2. **Read [Workflow Guide](./07-workflow-guide.md)** - How to proceed
3. **Start with Task 1** - Database schema creation

---

**Related Documents:**
- [Database Schema](./01-database-schema.md)
- [Code Changes](./02-code-changes.md)
- [Feature Flags](./03-feature-flags.md)
- [Implementation Tasks](./04-implementation-tasks.md)
- [Workflow Guide](./07-workflow-guide.md)
