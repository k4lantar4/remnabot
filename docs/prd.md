# remnabot - Product Requirements Document

**Author:** BMad
**Date:** 2025-11-21
**Version:** 1.0

---

## Executive Summary

RemnaWave Bedolaga Bot is transforming from a single-tenant Telegram bot for VPN subscription management into a multi-tenant SaaS platform that enables representatives/dealers to operate their own branded bot instances. This evolution maintains the existing robust subscription management, payment processing, and user administration capabilities while adding tenant isolation, representative bot provisioning, and comprehensive localization improvements.

The platform will support multiple tenants (representatives) who can request and receive their own bot instances, each operating independently with tenant-specific configurations, user bases, and branding while sharing the same underlying infrastructure and RemnaWave API integration.

### What Makes This Special

The key differentiator is the **automated representative bot provisioning system** - representatives can request their own bot instance directly from the main bot interface, and the system automatically provisions a fully functional, isolated bot instance with tenant-specific configuration. This enables rapid scaling of the dealer network without manual setup overhead.

Additionally, the comprehensive localization refactoring (removing all hardcoded Russian strings and setting Persian as default) makes the platform truly international-ready while maintaining backward compatibility with existing users.

---

## Project Classification

**Technical Type:** saas_b2b
**Domain:** general
**Complexity:** low

This is a SaaS B2B platform transformation project. The existing monolith architecture will be enhanced with multi-tenancy capabilities. The domain is general business software (VPN subscription management) with no specialized regulatory requirements. The complexity is low because we're building on a solid existing foundation rather than creating from scratch.

{{#if domain_context_summary}}

### Domain Context

{{domain_context_summary}}
{{/if}}

---

## Success Criteria

**Primary Success Metrics:**
- Representatives can successfully request and receive their own bot instances through the main bot interface
- All tenant data is properly isolated (users, subscriptions, transactions, settings)
- Zero hardcoded Russian strings remain in the codebase - all text comes from translation files
- Persian (Farsi) is the default language for all new users and system messages
- Existing functionality remains fully operational with no regressions
- Representative bot provisioning process completes automatically without manual intervention

**Technical Success Criteria:**
- Multi-tenant database schema supports tenant isolation at all levels
- API endpoints properly handle tenant context
- Localization system supports Persian as default with fallback mechanisms
- All existing features work correctly in multi-tenant context

**User Experience Success:**
- Representatives can easily request bot instances through intuitive bot interface
- Users experience no disruption during migration
- Persian-speaking users see Persian interface by default
- All text is properly localized (no mixed languages or hardcoded strings)

---

## Product Scope

### MVP - Minimum Viable Product

**Multi-Tenancy Core:**
- Tenant model in database (Tenant table with tenant_id, name, settings, status)
- Tenant isolation for all core entities (User, Subscription, Transaction, etc.)
- Tenant context middleware/filtering for all database queries
- Tenant-specific configuration management

**Representative Bot Provisioning:**
- Automated bot request flow in main bot (button/menu item)
- Request approval/processing workflow
- Bot instance provisioning (creates tenant, generates bot token, configures settings)
- Representative receives bot credentials and setup instructions

**Localization Refactoring:**
- Audit and identify all hardcoded Russian strings
- Move all hardcoded strings to translation files (app/localization/locales/fa.json)
- Change DEFAULT_LANGUAGE from "ru" to "fa" in config
- Update all code references to use translation system instead of hardcoded strings
- Ensure Persian translation file is complete

**API Enhancements:**
- Tenant-aware API endpoints
- Tenant context in request headers or authentication
- Tenant filtering for all data retrieval endpoints

### Growth Features (Post-MVP)

- Tenant-specific branding (custom bot name, logo, welcome messages)
- Tenant analytics and reporting dashboard
- Tenant billing and revenue sharing
- Advanced tenant management (suspension, limits, quotas)
- Multi-level representative hierarchy (sub-representatives)
- Tenant-specific payment provider configurations
- Tenant white-label customization options

### Vision (Future)

- Self-service tenant onboarding with automated approval
- Tenant marketplace (representatives can discover and join)
- Advanced multi-tenancy features (cross-tenant analytics, federation)
- Tenant-specific feature flags and A/B testing
- Automated tenant scaling and resource management

---

{{#if domain_considerations}}

## Domain-Specific Requirements

{{domain_considerations}}

This section shapes all functional and non-functional requirements below.
{{/if}}

---

{{#if innovation_patterns}}

## Innovation & Novel Patterns

{{innovation_patterns}}

### Validation Approach

{{validation_approach}}
{{/if}}

---

## saas_b2b Specific Requirements

### Multi-Tenancy Architecture

**Tenant Model:**
- Each tenant represents a representative/dealer who operates their own bot instance
- Tenant isolation at database level: all core tables include `tenant_id` foreign key
- Default tenant (tenant_id=1 or NULL) represents the main/original bot instance
- Tenant table fields:
  - `id` (PK)
  - `name` (representative/dealer name)
  - `status` (active, suspended, pending_approval)
  - `bot_token` (Telegram bot token for this tenant)
  - `bot_username` (bot username)
  - `settings` (JSON field for tenant-specific configuration)
  - `created_at`, `updated_at`
  - `created_by_user_id` (FK to users - who requested this tenant)

**Data Isolation Strategy:**
- Row-level security: all queries filter by tenant_id
- Service layer enforces tenant context
- Database migrations add tenant_id to: User, Subscription, Transaction, Ticket, PromoGroup, and all other tenant-scoped entities
- Backward compatibility: existing data gets tenant_id=1 (main tenant)

**Tenant Context Management:**
- Tenant context determined from:
  - Bot token (for bot handlers) - identifies which tenant's bot received the message
  - API authentication token (for REST API) - tokens are tenant-scoped
  - Admin operations - explicit tenant selection
- Middleware/service layer injects tenant_id into all database operations

### Permissions & Roles

**Role Hierarchy:**
1. **System Admin** (main tenant, tenant_id=1)
   - Full access to all tenants
   - Can create, suspend, manage tenants
   - Access to cross-tenant analytics

2. **Tenant Admin** (representative who owns a tenant)
   - Full access to their tenant's data only
   - Can manage their tenant's users, subscriptions, settings
   - Cannot access other tenants' data

3. **Tenant User** (end user of a tenant's bot)
   - Standard user permissions within their tenant
   - Cannot see or access other tenants

**Permission Matrix:**

| Action | System Admin | Tenant Admin | Tenant User |
|--------|-------------|--------------|-------------|
| View own tenant data | ✅ | ✅ | ✅ (own data only) |
| View other tenants | ✅ | ❌ | ❌ |
| Create tenant | ✅ | ❌ | ❌ |
| Request bot instance | ❌ | ❌ | ✅ (via main bot) |
| Manage tenant settings | ✅ | ✅ (own tenant) | ❌ |
| Suspend tenant | ✅ | ❌ | ❌ |
| View cross-tenant analytics | ✅ | ❌ | ❌ |

### API Specification

**Tenant-Aware Endpoints:**
- All existing endpoints remain functional but now filter by tenant_id
- New endpoints for tenant management:
  - `POST /api/bot-requests` - Request new bot instance (from main bot)
  - `GET /api/bot-requests/{request_id}` - Get bot request status
  - `GET /api/tenants` - List tenants (admin only)
  - `GET /api/tenants/{id}` - Get tenant details
  - `PUT /api/tenants/{id}` - Update tenant settings
  - `POST /api/tenants/{id}/suspend` - Suspend tenant
  - `POST /api/tenants/{id}/activate` - Activate tenant
  - `GET /api/tenants/{id}/statistics` - Get tenant statistics
  - `GET /api/tenants/{id}/analytics` - Get tenant analytics dashboard

**Authentication Model:**
- Bot handlers: Tenant identified by bot token (each tenant has unique bot token)
- REST API: Bearer tokens are tenant-scoped (token contains tenant_id)
- Admin API: System admin tokens can access all tenants, tenant admin tokens restricted to their tenant

### Integration Requirements

**RemnaWave API Integration:**
- Maintains existing integration
- Tenant-specific RemnaWave configurations (if needed in future)
- All tenants share same RemnaWave panel access (or tenant-specific credentials in settings JSON)

**Payment Provider Integration:**
- Existing 9 payment providers continue to work
- Tenant-specific payment provider configurations (optional, in tenant.settings JSON)
- Payment webhooks include tenant context

**Telegram Integration:**
- Each tenant has their own bot token
- Bot instances are separate but share same codebase
- Webhook routing identifies tenant from bot token

---

{{#if ux_principles}}

## User Experience Principles

{{ux_principles}}

### Key Interactions

{{key_interactions}}
{{/if}}

---

## Functional Requirements

### Tenant Management

**FR1:** System administrators can create new tenant records with name, status, and configuration
**FR2:** System administrators can view list of all tenants with status, creation date, and basic statistics
**FR3:** System administrators can suspend or activate tenant accounts
**FR4:** System administrators can update tenant settings and configuration
**FR5:** System administrators can view tenant-specific analytics and statistics
**FR6:** Tenants are automatically assigned a unique tenant_id upon creation
**FR7:** Tenant status can be: pending_approval, active, suspended

### Representative Bot Provisioning

**FR8:** Users can access a "Request Representative Bot" option from the main bot's menu
**FR9:** Users can initiate bot request flow through bot interface (button/menu item)
**FR10:** System can collect required information for bot request (representative name, contact info, business details)
**FR11:** System can validate bot request information before processing
**FR12:** System can automatically create tenant record when bot request is approved
**FR13:** System can generate unique Telegram bot token for new tenant (or guide user to create one)
**FR14:** System can configure tenant settings with default values upon creation
**FR15:** System can send bot credentials and setup instructions to requesting user
**FR16:** System can track bot request status (pending, approved, rejected, completed)
**FR17:** System can notify administrators of new bot requests requiring approval
**FR18:** Approved bot instances are immediately functional with tenant isolation

### Multi-Tenancy Data Isolation

**FR19:** All User records are associated with a tenant_id
**FR20:** All Subscription records are associated with a tenant_id
**FR21:** All Transaction records are associated with a tenant_id
**FR22:** All Ticket records are associated with a tenant_id
**FR23:** All PromoGroup records are associated with a tenant_id
**FR24:** All other tenant-scoped entities include tenant_id foreign key
**FR25:** Database queries automatically filter by tenant_id based on context
**FR26:** Users can only access data within their tenant scope
**FR27:** System administrators can access data across all tenants
**FR28:** Existing data (created before multi-tenancy) is assigned to main tenant (tenant_id=1)
**FR29:** Tenant isolation is enforced at service layer, not just database layer

### Tenant Context Management

**FR30:** Bot handlers can identify tenant from incoming bot token
**FR31:** REST API can identify tenant from authentication token
**FR32:** Service layer can inject tenant_id into all database operations
**FR33:** System can maintain tenant context throughout request lifecycle
**FR34:** Admin operations can explicitly specify tenant context
**FR35:** Cross-tenant operations require system admin privileges

### Localization - Hardcoded String Removal

**FR36:** System can identify all hardcoded Russian strings in codebase
**FR37:** All hardcoded Russian strings are moved to translation files
**FR38:** Code uses translation system (Texts class) instead of hardcoded strings
**FR39:** No Russian text remains hardcoded in Python code, handlers, or services
**FR40:** All user-facing text comes from translation files
**FR41:** System maintains backward compatibility during localization refactoring

### Localization - Persian as Default

**FR42:** DEFAULT_LANGUAGE configuration setting is changed from "ru" to "fa"
**FR43:** New users receive Persian interface by default
**FR44:** System messages and notifications use Persian by default
**FR45:** Persian translation file (fa.json) contains all required strings
**FR46:** System falls back to English if Persian translation is missing (not Russian)
**FR47:** Existing users can continue using their selected language (ru/en)
**FR48:** Language selection feature continues to work for all supported languages

### API - Tenant Awareness

**FR49:** All existing API endpoints filter results by tenant_id
**FR50:** API authentication tokens include tenant context
**FR51:** API responses only include data from authenticated user's tenant
**FR52:** System admin API tokens can access data from any tenant
**FR53:** Tenant admin API tokens are restricted to their tenant's data
**FR54:** New tenant management endpoints are available for system administrators
**FR55:** Bot request endpoint is accessible from main bot context

### Bot Functionality - Tenant Isolation

**FR56:** Each tenant's bot instance operates independently
**FR57:** Users interacting with Tenant A's bot cannot see Tenant B's data
**FR58:** Each tenant's bot has separate user base
**FR59:** Each tenant's bot has separate subscriptions and transactions
**FR60:** Each tenant's bot can have tenant-specific settings and configuration
**FR61:** Main bot (tenant_id=1) continues to function as before
**FR62:** Representative bots have same feature set as main bot

### Backward Compatibility

**FR63:** Existing users continue to function without disruption
**FR64:** Existing subscriptions continue to work
**FR65:** Existing transactions remain accessible
**FR66:** Existing admin functionality remains operational
**FR67:** Existing payment integrations continue to work
**FR68:** Existing RemnaWave integration continues to work
**FR69:** Database migrations are non-destructive and preserve existing data
**FR70:** Code changes maintain API compatibility where possible

---

## Non-Functional Requirements

### Performance

- Tenant filtering adds minimal overhead to database queries (indexed tenant_id columns)
- Multi-tenant queries perform within acceptable latency (<100ms for standard operations)
- Bot request provisioning completes within reasonable time (<30 seconds)
- System handles multiple concurrent tenant operations without degradation
- Existing single-tenant performance characteristics are maintained

### Security

- Tenant data isolation is enforced at multiple layers (database, service, API)
- Tenant context cannot be bypassed or manipulated by users
- Bot tokens are securely stored and cannot be accessed by unauthorized users
- API authentication tokens are tenant-scoped and cannot access other tenants
- System admin operations require explicit authentication and authorization
- All tenant-scoped data access is logged for audit purposes
- SQL injection and other security vulnerabilities are prevented through ORM usage

### Scalability

- Database schema supports thousands of tenants without performance issues
- Tenant_id columns are properly indexed for efficient querying
- System can handle growth from single tenant to hundreds of tenants
- Bot provisioning process scales to handle multiple concurrent requests
- Translation file loading is efficient (cached) and doesn't impact performance

### Integration

- RemnaWave API integration continues to work with multi-tenant architecture
- Payment provider webhooks correctly identify tenant context
- Telegram bot API integration works for multiple bot instances (multiple tokens)
- Existing external integrations remain functional
- New tenant-specific integrations can be configured via tenant settings JSON

### Maintainability

- Code changes follow existing architecture patterns (layered architecture)
- Multi-tenancy implementation is clean and doesn't add unnecessary complexity
- Translation system is centralized and easy to maintain
- Hardcoded strings are eliminated, making future localization easier
- Database migrations are well-documented and reversible

---

## Summary

This PRD documents the transformation of RemnaWave Bedolaga Bot from a single-tenant application to a multi-tenant SaaS platform. The core value proposition is enabling representatives/dealers to operate their own branded bot instances through an automated provisioning system, while maintaining all existing functionality and improving internationalization through comprehensive localization refactoring.

**Key Deliverables:**
- Multi-tenant database architecture with proper data isolation
- Automated representative bot provisioning workflow
- Complete localization refactoring (remove hardcoded Russian, set Persian as default)
- Tenant-aware API and service layer
- Backward compatibility with existing users and data

**Total Functional Requirements:** 70 FRs covering tenant management, bot provisioning, data isolation, localization, API enhancements, and backward compatibility.

**Critical Success Factors:**
1. Zero data leakage between tenants
2. Seamless user experience during migration
3. Complete elimination of hardcoded Russian strings
4. Persian as default language for new users
5. Automated bot provisioning without manual intervention

---

_This PRD captures the essence of remnabot - transforming a single-tenant VPN subscription bot into a scalable multi-tenant SaaS platform that enables representatives to operate their own bot instances while maintaining robust functionality and improving internationalization._

_Created through collaborative discovery between BMad and AI facilitator._

