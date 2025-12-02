# Multi-Tenant SaaS Migration: Architecture Audit Report

**Date:** 2025-01-27  
**Auditor:** Senior Backend Architect  
**Project:** remnabot  
**Purpose:** Pre-migration assessment for Multi-Tenant SaaS refactoring

---

## Executive Summary

This report analyzes three critical areas of the codebase to assess migration complexity to a multi-tenant SaaS architecture. The project shows a **mixed maturity level**: well-structured database models, but inconsistent localization and payment provider coupling that will require significant refactoring.

---

## 1. Localization Analysis

### Current State

**Infrastructure:**
- ✅ Localization system exists: `app/localization/texts.py` with `Texts` class and `get_texts()` function
- ✅ Locale files: `locales/en.json`, `locales/fa.json`, plus YAML defaults
- ✅ 4,931 matches for localization function calls (`get_text`, `t()`, `_()`) across 65 handler files

**Hardcoded Strings:**
- ❌ **65 files** in `app/handlers/` contain Cyrillic (Russian) characters
- ❌ **3 files** in `app/keyboards/` contain Cyrillic characters
- ❌ Examples of hardcoded strings found:
  - `"📊 История операций пуста"` (balance/main.py:161)
  - `"📊 <b>История операций</b>\n\n"` (balance/main.py:167)
  - `"💰 Мой баланс"` (payment/common.py:119)
  - `"🏠 Главное меню"` (payment/common.py:125)
  - `"✅ <b>Платеж успешно завершен!</b>\n\n"` (payment/common.py:157)

### Effort Assessment: **MIXED** ⚠️

**Breakdown:**
- **~40% Clean**: Core infrastructure in place, many handlers use `get_texts()`
- **~60% Mixed/Hardcoded**: Significant hardcoded Russian strings in:
  - Payment success messages
  - Keyboard button labels
  - Error messages
  - Admin interface text
  - Status display strings

**Migration Impact:**
- **Medium-High Effort**: Requires systematic audit of all 65 handler files
- **Estimated Work**: 2-3 weeks for full localization extraction
- **Risk**: Some strings may be context-dependent (user-specific formatting)

**Recommendations:**
1. Create a script to scan and extract all Cyrillic strings
2. Migrate hardcoded strings to locale files (prioritize user-facing messages)
3. Add linting rule to prevent future hardcoded Cyrillic strings
4. Consider using translation keys instead of direct Russian text

---

## 2. Payment System Architecture

### Current Architecture

**Pattern: Mixin-Based (No Abstract Base Class)**

```python
# PaymentService inherits from multiple mixins
class PaymentService(
    PaymentCommonMixin,      # Shared utilities
    YooKassaPaymentMixin,    # Provider-specific
    CryptoBotPaymentMixin,    # Provider-specific
    TelegramStarsMixin,       # Provider-specific
    # ... 6 more mixins
):
```

**Payment Providers:**
- YooKassa (Russian payment gateway)
- CryptoBot (Crypto payments)
- Telegram Stars
- Tribute
- Heleket
- MulenPay
- Pal24
- Platega
- Wata

### Coupling Analysis

**✅ Strengths:**
- Mixin pattern provides some separation
- `PaymentCommonMixin` contains shared logic (keyboards, notifications)
- Each provider has dedicated mixin class
- Provider-specific models (YooKassaPayment, CryptoBotPayment, etc.)

**❌ Weaknesses:**
- **No common interface/ABC**: Each mixin implements different method signatures
- **Handler coupling**: Handlers directly import and call provider-specific methods:
  - `app/handlers/balance/yookassa.py`
  - `app/handlers/balance/cryptobot.py`
  - `app/handlers/balance/heleket.py`
  - etc. (9 separate handler files)
- **Service initialization**: `PaymentService` directly instantiates provider services:
  ```python
  self.yookassa_service = YooKassaService(...)
  self.cryptobot_service = CryptoBotService(...)
  # etc.
  ```

### Adding New Provider (e.g., ZarinPal)

**Current Process Would Require:**
1. ✅ Create new mixin: `ZarinPalPaymentMixin`
2. ✅ Add to `PaymentService` inheritance
3. ✅ Create handler file: `app/handlers/balance/zarinpal.py`
4. ❌ **Modify core logic**: Update `PaymentService.__init__()` to instantiate service
5. ❌ **Modify handlers**: Update payment method selection logic
6. ❌ **Modify keyboards**: Add ZarinPal to payment method selection

**Coupling Level: MODERATE-HIGH** ⚠️

### Recommendations for Multi-Tenant

**Required Refactoring:**
1. **Create Abstract Payment Provider Interface:**
   ```python
   class PaymentProvider(ABC):
       @abstractmethod
       async def create_payment(...) -> PaymentResult
       @abstractmethod
       async def verify_payment(...) -> PaymentStatus
       @abstractmethod
       def get_provider_name() -> str
   ```

2. **Implement Provider Registry Pattern:**
   ```python
   class PaymentProviderRegistry:
       def register_provider(self, name: str, provider: PaymentProvider)
       def get_provider(self, name: str) -> PaymentProvider
       def list_available_providers(self) -> List[str]
   ```

3. **Decouple Handlers:**
   - Single handler: `app/handlers/balance/payment.py`
   - Route to provider via registry
   - Tenant-specific provider configuration

4. **Tenant-Aware Provider Selection:**
   - Store enabled providers per tenant
   - Filter available methods by tenant config

**Estimated Effort:** 3-4 weeks

---

## 3. Database Schema Overview

### Core Entities

**User Management:**
- `User` (id, telegram_id, username, balance_kopeks, language, status)
- `UserPromoGroup` (Many-to-Many: User ↔ PromoGroup)

**Subscription:**
- `Subscription` (id, user_id [UNIQUE], status, start_date, end_date, traffic_limit_gb, device_limit)
- `SubscriptionServer` (Many-to-Many: Subscription ↔ ServerSquad)
- `SubscriptionTemporaryAccess` (trial access tracking)
- `SubscriptionEvent` (audit log)

**Payment:**
- `Transaction` (id, user_id, type, amount_kopeks, payment_method, external_id)
- Provider-specific models:
  - `YooKassaPayment`
  - `CryptoBotPayment`
  - `HeleketPayment`
  - `MulenPayPayment`
  - `Pal24Payment`
  - `WataPayment`
  - `PlategaPayment`

**Pricing & Promotions:**
- `PromoGroup` (discount groups with priority)
- `PromoCode` (codes for balance/subscription bonuses)
- `PromoCodeUse` (usage tracking)
- `DiscountOffer` (time-limited offers)
- `PromoOfferTemplate` (offer templates)

**Support:**
- `Ticket` (id, user_id, status, priority)
- `TicketMessage` (ticket conversation)
- `SupportAuditLog` (moderator actions)

**Content:**
- `ServerSquad` (VPN servers, country_code, price_kopeks)
- `Squad` (legacy server model)
- `Poll`, `PollQuestion`, `PollOption`, `PollResponse`
- `BroadcastHistory`
- `UserMessage`, `WelcomeText`

**System:**
- `SystemSetting` (key-value config)
- `MonitoringLog`
- `WebApiToken`
- `MainMenuButton`

### Key Relationships

```
User (1) ──< (1) Subscription [UNIQUE constraint]
User (1) ──< (*) Transaction
User (1) ──< (*) YooKassaPayment
User (1) ──< (*) CryptoBotPayment
User (1) ──< (*) [Other Payment Models]
User (*) ──<─> (*) PromoGroup [via UserPromoGroup]
User (1) ──< (*) Ticket
User (1) ──< (*) ReferralEarning

Subscription (1) ──<─> (*) ServerSquad [via SubscriptionServer]
Subscription (1) ──< (*) DiscountOffer
Subscription (1) ──< (*) SubscriptionTemporaryAccess

Transaction (1) ──< (0..1) YooKassaPayment
Transaction (1) ──< (0..1) CryptoBotPayment
Transaction (1) ──< (0..1) [Other Payment Models]

PromoGroup (*) ──<─> (*) ServerSquad [via server_squad_promo_groups]
```

### Multi-Tenant Migration Impact

**❌ Current Issues:**
- **No tenant_id column** in any table
- **No tenant isolation** - all data is global
- **Hard-coded currency** (kopeks/rubles) throughout
- **Single language default** (Russian)

**Required Schema Changes:**

1. **Add Tenant Entity:**
   ```python
   class Tenant(Base):
       id = Column(Integer, primary_key=True)
       name = Column(String(255))
       subdomain = Column(String(100), unique=True)
       default_language = Column(String(5))
       default_currency = Column(String(3))
       settings_json = Column(JSON)
   ```

2. **Add tenant_id Foreign Key to ALL tables:**
   - User → tenant_id (NOT NULL)
   - Subscription → tenant_id (via user)
   - Transaction → tenant_id (via user)
   - All payment models → tenant_id (via user)
   - ServerSquad → tenant_id
   - PromoGroup → tenant_id
   - Ticket → tenant_id
   - etc.

3. **Migration Strategy:**
   - **Option A: Row-Level Security (PostgreSQL)**
     - Add tenant_id to all tables
     - Use RLS policies for isolation
   - **Option B: Schema-per-Tenant**
     - Separate database schema per tenant
     - Higher isolation, more complex migrations
   - **Option C: Database-per-Tenant**
     - Separate database per tenant
     - Maximum isolation, highest operational complexity

**Estimated Effort:** 4-6 weeks (depending on data migration complexity)

---

## Summary & Recommendations

### Migration Complexity Matrix

| Area | Current State | Migration Effort | Risk Level |
|------|--------------|------------------|------------|
| **Localization** | Mixed (40% clean, 60% hardcoded) | Medium-High (2-3 weeks) | Medium |
| **Payment System** | Mixin-based, moderate coupling | High (3-4 weeks) | High |
| **Database Schema** | Single-tenant, no isolation | Very High (4-6 weeks) | Very High |

### Critical Path Items

1. **Database Schema Migration** (Highest Priority)
   - Design tenant model and relationships
   - Plan data migration strategy
   - Implement tenant_id across all tables
   - Add tenant context middleware

2. **Payment Provider Abstraction** (High Priority)
   - Create PaymentProvider interface
   - Refactor to provider registry
   - Decouple handlers from specific providers
   - Add tenant-aware provider selection

3. **Localization Cleanup** (Medium Priority)
   - Extract hardcoded strings
   - Migrate to locale files
   - Add linting rules
   - Support tenant-specific locales

### Recommended Migration Phases

**Phase 1: Foundation (Weeks 1-4)**
- Add Tenant model and tenant_id columns
- Implement tenant context middleware
- Create tenant-aware database queries

**Phase 2: Payment Refactoring (Weeks 5-8)**
- Abstract payment provider interface
- Refactor handlers to use registry
- Add tenant-specific provider config

**Phase 3: Localization & Polish (Weeks 9-11)**
- Extract hardcoded strings
- Add tenant-specific locale support
- Testing and validation

**Phase 4: Data Migration & Go-Live (Weeks 12-14)**
- Migrate existing data to tenant model
- Performance testing
- Staged rollout

### Total Estimated Timeline: **12-14 weeks**

---

## Appendix: File Counts

- **Handlers with Cyrillic:** 65 files
- **Keyboards with Cyrillic:** 3 files
- **Payment Providers:** 9 providers
- **Payment Handler Files:** 9 files (one per provider)
- **Database Models:** 40+ models
- **Core Entities:** 8 major entity groups

---

**Report Generated:** 2025-01-27  
**Next Steps:** Review with team, prioritize migration phases, allocate resources

