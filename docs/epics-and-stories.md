# Epics and Stories - Multi-Tenancy Transformation

**Author:** Product & Development Team  
**Date:** 2025-11-21  
**Version:** 1.0

---

## Overview

This document breaks down the PRD into implementable Epics and Stories. Each Epic represents a major feature area, and Stories are concrete, testable units of work that developers can implement.

**Total Functional Requirements:** 70 FRs  
**Epic Count:** 9 Epics  
**Story Count:** ~45-50 Stories (estimated)

---

## Epic 1: Multi-Tenancy Database Foundation

**Epic Goal:** Establish database schema and migration strategy for multi-tenancy with complete data isolation.

**Related FRs:** FR19-FR29

**Dependencies:** None (Foundation Epic)

### Stories

#### Story 1.1: Create Tenant Table and Model
**As a** system administrator  
**I want** a Tenant table in the database  
**So that** I can manage tenant records

**Acceptance Criteria:**
- [ ] Tenant table created with all required fields (id, name, status, bot_token, bot_username, settings, created_by_user_id, timestamps)
- [ ] Tenant SQLAlchemy model created in `app/database/models.py`
- [ ] Indexes created on status, bot_token, created_by_user_id
- [ ] Constraints added (status enum check)
- [ ] Migration script created and tested
- [ ] Model relationships defined (created_by_user_id → users)

**Technical Notes:**
- Follow existing model patterns
- Use JSONB for settings field
- Status: pending_approval, active, suspended, rejected

**Estimated Effort:** 3-4 hours

---

#### Story 1.2: Create Main Tenant (tenant_id=1)
**As a** system  
**I want** a default main tenant  
**So that** existing data can be migrated to it

**Acceptance Criteria:**
- [ ] Migration script creates tenant with id=1, name="Main Bot", status="active"
- [ ] Main tenant's bot_token set from settings.BOT_TOKEN
- [ ] Main tenant's bot_username set from settings.BOT_USERNAME (if available)
- [ ] Sequence set to start from 2
- [ ] Existing data can reference tenant_id=1

**Technical Notes:**
- Main tenant represents the original bot instance
- Bot token comes from environment/config, not user input

**Estimated Effort:** 1-2 hours

---

#### Story 1.3: Add tenant_id to Users Table
**As a** system  
**I want** users table to have tenant_id  
**So that** users are isolated by tenant

**Acceptance Criteria:**
- [ ] Migration adds tenant_id column to users table
- [ ] Foreign key constraint to tenants table
- [ ] Default value = 1 for existing data
- [ ] NOT NULL constraint after migration
- [ ] Index created on tenant_id
- [ ] Composite unique index on (telegram_id, tenant_id) - same Telegram user can exist in multiple tenants
- [ ] All existing users get tenant_id=1
- [ ] Model updated with tenant_id field and relationship

**Estimated Effort:** 2-3 hours

---

#### Story 1.4: Add tenant_id to Subscriptions Table
**As a** system  
**I want** subscriptions table to have tenant_id  
**So that** subscriptions are isolated by tenant

**Acceptance Criteria:**
- [ ] Migration adds tenant_id to subscriptions
- [ ] Existing subscriptions get tenant_id from their user
- [ ] NOT NULL constraint
- [ ] Index created
- [ ] Model updated

**Estimated Effort:** 2 hours

---

#### Story 1.5: Add tenant_id to Transactions Table
**As a** system  
**I want** transactions table to have tenant_id  
**So that** transactions are isolated by tenant

**Acceptance Criteria:**
- [ ] Migration adds tenant_id to transactions
- [ ] Existing transactions get tenant_id from their user
- [ ] NOT NULL constraint
- [ ] Index created
- [ ] Model updated

**Estimated Effort:** 2 hours

---

#### Story 1.6: Add tenant_id to Tickets and TicketMessages
**As a** system  
**I want** tickets and ticket_messages to have tenant_id  
**So that** support tickets are isolated by tenant

**Acceptance Criteria:**
- [ ] Migration adds tenant_id to tickets (from user)
- [ ] Migration adds tenant_id to ticket_messages (from ticket)
- [ ] Indexes created
- [ ] Models updated

**Estimated Effort:** 2 hours

---

#### Story 1.7: Add tenant_id to Promo System Tables
**As a** system  
**I want** promo tables to have tenant_id  
**So that** promotional features are isolated by tenant

**Acceptance Criteria:**
- [ ] Migration adds tenant_id to: promo_groups, promocodes, promo_code_uses, promo_offer_templates, promo_offer_logs, discount_offers
- [ ] Existing data gets tenant_id=1
- [ ] Composite unique index on promocodes (code, tenant_id)
- [ ] All models updated

**Estimated Effort:** 3-4 hours

---

#### Story 1.8: Add tenant_id to Remaining Tenant-Scoped Tables
**As a** system  
**I want** all tenant-scoped tables to have tenant_id  
**So that** complete data isolation is achieved

**Acceptance Criteria:**
- [ ] Migration adds tenant_id to: referral_earnings, subscription_conversions, subscription_temporary_access, user_promo_groups, broadcast_history, polls, poll_questions, poll_options, poll_responses, poll_answers, advertising_campaigns, advertising_campaign_registrations, user_messages, sent_notifications, web_api_tokens
- [ ] All relationships properly resolved (via user, subscription, poll, etc.)
- [ ] Indexes created
- [ ] Models updated

**Estimated Effort:** 4-5 hours

---

#### Story 1.9: Add tenant_id to Payment Provider Tables
**As a** system  
**I want** payment tables to have tenant_id  
**So that** payments are isolated by tenant

**Acceptance Criteria:**
- [ ] Migration adds tenant_id to: yookassa_payments, cryptobot_payments, heleket_payments, mulenpay_payments, pal24_payments, wata_payments, platega_payments
- [ ] Existing payments get tenant_id from their user
- [ ] Indexes created
- [ ] Models updated

**Estimated Effort:** 3-4 hours

---

#### Story 1.10: Create Composite Indexes for Performance
**As a** system  
**I want** optimized indexes for common queries  
**So that** tenant-filtered queries are fast

**Acceptance Criteria:**
- [ ] Composite index on users (tenant_id, status) WHERE status='active'
- [ ] Composite index on subscriptions (tenant_id, status) WHERE status='active'
- [ ] Composite index on transactions (tenant_id, created_at)
- [ ] Composite index on tickets (tenant_id, status) WHERE status='open'
- [ ] All indexes tested with EXPLAIN ANALYZE

**Estimated Effort:** 2 hours

---

**Epic 1 Total Estimated Effort:** 24-30 hours

---

## Epic 2: Tenant Management

**Epic Goal:** Enable system administrators to create, view, update, and manage tenant records.

**Related FRs:** FR1-FR7

**Dependencies:** Epic 1 (Tenant table must exist)

### Stories

#### Story 2.1: Create Tenant CRUD Operations
**As a** developer  
**I want** CRUD functions for tenants  
**So that** services can manage tenant records

**Acceptance Criteria:**
- [ ] `app/database/crud/tenant.py` created
- [ ] Functions: create_tenant(), get_tenant_by_id(), get_tenant_by_bot_token(), list_tenants(), update_tenant(), delete_tenant()
- [ ] All functions include proper error handling
- [ ] Unit tests written

**Estimated Effort:** 3-4 hours

---

#### Story 2.2: Create TenantService
**As a** developer  
**I want** a TenantService class  
**So that** business logic for tenant management is centralized

**Acceptance Criteria:**
- [ ] `app/services/tenant_service.py` created
- [ ] Methods: create_tenant(), get_tenant(), update_tenant_settings(), suspend_tenant(), activate_tenant()
- [ ] Settings validation
- [ ] Default settings generation
- [ ] Unit tests written

**Estimated Effort:** 4-5 hours

---

#### Story 2.3: Create Tenant API Endpoints
**As a** system administrator  
**I want** REST API endpoints for tenant management  
**So that** I can manage tenants via API

**Acceptance Criteria:**
- [ ] `app/webapi/routes/tenants.py` created
- [ ] Endpoints: GET /api/tenants, GET /api/tenants/{id}, POST /api/tenants, PUT /api/tenants/{id}, POST /api/tenants/{id}/suspend, POST /api/tenants/{id}/activate
- [ ] Pydantic schemas created
- [ ] Authentication and authorization (system admin only)
- [ ] API documentation updated
- [ ] Integration tests written

**Estimated Effort:** 6-8 hours

---

#### Story 2.4: Add Tenant Statistics to API
**As a** system administrator  
**I want** tenant statistics in API responses  
**So that** I can see tenant activity at a glance

**Acceptance Criteria:**
- [ ] Statistics calculated: total_users, active_subscriptions, total_revenue
- [ ] Statistics included in GET /api/tenants/{id} response
- [ ] Efficient queries (no N+1 problems)
- [ ] Cached if needed

**Estimated Effort:** 3-4 hours

---

**Epic 2 Total Estimated Effort:** 16-21 hours

---

## Epic 3: Representative Bot Provisioning

**Epic Goal:** Enable users to request representative bot instances through the main bot interface with automated provisioning.

**Related FRs:** FR8-FR18

**Dependencies:** Epic 1, Epic 2

### Stories

#### Story 3.1: Create Bot Request Model and CRUD
**As a** developer  
**I want** a bot request model  
**So that** I can track bot requests

**Acceptance Criteria:**
- [ ] BotRequest model created (or use Tenant with status=pending_approval)
- [ ] CRUD operations for bot requests
- [ ] Status tracking: pending, approved, rejected, completed
- [ ] Tracking code generation

**Estimated Effort:** 2-3 hours

---

#### Story 3.2: Add Bot Request Menu Item to Main Bot
**As a** user  
**I want** a menu option to request a representative bot  
**So that** I can start the request process

**Acceptance Criteria:**
- [ ] Menu item added to main bot (tenant_id=1 only)
- [ ] Button/keyboard created
- [ ] Handler created to start request flow
- [ ] Localized text (Persian)

**Estimated Effort:** 2-3 hours

---

#### Story 3.3: Implement Bot Request Form Flow
**As a** user  
**I want** to fill out a form to request a bot  
**So that** I can provide required information

**Acceptance Criteria:**
- [ ] FSM states created for request flow
- [ ] Multi-step form: name, contact, business details (optional)
- [ ] Form validation
- [ ] User can cancel at any step
- [ ] Confirmation screen with tracking code

**Estimated Effort:** 4-5 hours

---

#### Story 3.4: Create Bot Request Approval Workflow
**As a** system administrator  
**I want** to review and approve bot requests  
**So that** I can control tenant creation

**Acceptance Criteria:**
- [ ] Admin notification when new request created
- [ ] Admin can view pending requests
- [ ] Admin can approve/reject requests
- [ ] Rejection reason can be provided
- [ ] User notified of decision

**Estimated Effort:** 4-5 hours

---

#### Story 3.5: Implement Automated Bot Provisioning
**As a** system  
**I want** to automatically provision bot when approved  
**So that** representatives get their bot quickly

**Acceptance Criteria:**
- [ ] When approved, create tenant record
- [ ] Guide user to create bot via @BotFather (provide instructions)
- [ ] User provides bot token through bot interface
- [ ] Validate bot token (verify with Telegram API)
- [ ] Store validated bot token in tenant record
- [ ] Configure default tenant settings
- [ ] Send bot credentials and setup instructions to user
- [ ] Update request status to completed

**Technical Notes:**
- **Bot Token Strategy:** User creates bot via @BotFather, provides token
- **Validation:** Use Telegram Bot API to verify token validity
- **Alternative (Future):** Automatic bot creation via BotFather API (post-MVP)

**Estimated Effort:** 6-8 hours

---

#### Story 3.6: Add Bot Request Status Check
**As a** user  
**I want** to check my bot request status  
**So that** I know if it's been approved

**Acceptance Criteria:**
- [ ] User can check status by tracking code
- [ ] Status displayed: pending, approved, rejected
- [ ] If approved, bot credentials shown
- [ ] If rejected, reason shown

**Estimated Effort:** 2-3 hours

---

**Epic 3 Total Estimated Effort:** 19-25 hours

---

## Epic 4: Tenant Context Management

**Epic Goal:** Implement tenant context extraction and injection throughout the application.

**Related FRs:** FR30-FR35

**Dependencies:** Epic 1

### Stories

#### Story 4.1: Create Tenant Context Middleware
**As a** developer  
**I want** middleware to extract tenant context  
**So that** all handlers have tenant_id available

**Acceptance Criteria:**
- [ ] Middleware created in `app/middlewares/tenant_context.py`
- [ ] Extracts tenant_id from bot token (for bot handlers)
- [ ] Extracts tenant_id from API token (for REST API)
- [ ] Injects tenant_id into request context
- [ ] Handles missing tenant gracefully

**Estimated Effort:** 4-5 hours

---

#### Story 4.2: Update Service Layer for Tenant Filtering
**As a** developer  
**I want** services to automatically filter by tenant_id  
**So that** data isolation is enforced

**Acceptance Criteria:**
- [ ] Tenant context injected into all service methods
- [ ] All database queries include tenant_id filter
- [ ] Services updated: UserService, SubscriptionService, TransactionService, TicketService, PromoService, etc.
- [ ] Tenant limits enforced (check before operations that would exceed limits)
- [ ] Error messages when limits reached
- [ ] No data leakage between tenants
- [ ] Unit tests verify isolation
- [ ] Integration tests verify limit enforcement

**Technical Notes:**
- Limits checked before: user creation, subscription creation, transaction processing
- Limits stored in tenant.settings.limits
- Error: "Tenant limit reached: max_users" with actionable message

**Estimated Effort:** 10-12 hours

---

#### Story 4.3: Update CRUD Operations for Tenant Filtering
**As a** developer  
**I want** CRUD functions to filter by tenant_id  
**So that** data access is tenant-aware

**Acceptance Criteria:**
- [ ] All CRUD functions accept tenant_id parameter
- [ ] All queries include WHERE tenant_id = ?
- [ ] Relationships respect tenant boundaries
- [ ] Existing CRUD modules updated (33 modules)
- [ ] Backward compatibility maintained (tenant_id=1 default)

**Estimated Effort:** 10-12 hours

---

#### Story 4.4: Update Bot Handlers for Tenant Context
**As a** developer  
**I want** bot handlers to use tenant context  
**So that** each bot instance operates independently

**Acceptance Criteria:**
- [ ] Bot token identifies tenant
- [ ] All handlers get tenant_id from context
- [ ] Handlers pass tenant_id to services
- [ ] Main bot (tenant_id=1) continues to work
- [ ] Representative bots work independently

**Estimated Effort:** 6-8 hours

---

#### Story 4.5: Update API Authentication for Tenant Scoping
**As a** developer  
**I want** API tokens to be tenant-scoped  
**So that** API access is isolated by tenant

**Acceptance Criteria:**
- [ ] WebApiToken model updated with tenant_id
- [ ] Token creation includes tenant_id
- [ ] Token validation extracts tenant_id
- [ ] API endpoints filter by token's tenant_id
- [ ] System admin tokens can access all tenants

**Estimated Effort:** 4-5 hours

---

**Epic 4 Total Estimated Effort:** 32-40 hours

---

## Epic 5: Localization - Remove Hardcoded Russian

**Epic Goal:** Eliminate all hardcoded Russian strings and move them to translation files.

**Related FRs:** FR36-FR41

**Dependencies:** None

### Stories

#### Story 5.1: Audit Hardcoded Russian Strings
**As a** developer  
**I want** to identify all hardcoded Russian strings  
**So that** I know what needs to be moved

**Acceptance Criteria:**
- [ ] Codebase scanned for Russian text
- [ ] List created of all hardcoded strings
- [ ] Files identified: handlers, services, keyboards, etc.
- [ ] Report generated with locations

**Estimated Effort:** 2-3 hours

---

#### Story 5.2: Create Persian Translation File
**As a** developer  
**I want** a complete Persian translation file  
**So that** all text can be localized

**Acceptance Criteria:**
- [ ] `app/localization/locales/fa.json` created/updated
- [ ] All Russian strings translated to Persian
- [ ] All existing keys from ru.json included
- [ ] Translation quality checked

**Estimated Effort:** 4-6 hours

---

#### Story 5.3: Replace Hardcoded Strings in Handlers
**As a** developer  
**I want** handlers to use translation system  
**So that** no Russian is hardcoded

**Acceptance Criteria:**
- [ ] All handlers updated to use `get_texts()`
- [ ] Hardcoded strings replaced with translation keys
- [ ] All handler files reviewed and updated
- [ ] No Russian strings remain in handlers

**Estimated Effort:** 8-10 hours

---

#### Story 5.4: Replace Hardcoded Strings in Services
**As a** developer  
**I want** services to use translation system  
**So that** no Russian is hardcoded

**Acceptance Criteria:**
- [ ] All services updated to use translation system
- [ ] Hardcoded strings replaced
- [ ] Services accept language parameter
- [ ] No Russian strings remain in services

**Estimated Effort:** 6-8 hours

---

#### Story 5.5: Replace Hardcoded Strings in Keyboards
**As a** developer  
**I want** keyboards to use translation system  
**So that** no Russian is hardcoded

**Acceptance Criteria:**
- [ ] All keyboard functions accept language parameter
- [ ] Hardcoded button texts replaced with translation keys
- [ ] All keyboard files updated
- [ ] No Russian strings remain in keyboards

**Estimated Effort:** 4-5 hours

---

#### Story 5.6: Replace Hardcoded Strings in Other Modules
**As a** developer  
**I want** all modules to use translation system  
**So that** no Russian is hardcoded anywhere

**Acceptance Criteria:**
- [ ] All remaining modules reviewed
- [ ] Hardcoded strings in utils, middlewares, etc. replaced
- [ ] Complete codebase scan confirms zero hardcoded Russian
- [ ] Tests verify no regressions

**Estimated Effort:** 4-6 hours

---

**Epic 5 Total Estimated Effort:** 28-38 hours

---

## Epic 6: Localization - Persian as Default

**Epic Goal:** Change default language from Russian to Persian for all new users and system messages.

**Related FRs:** FR42-FR48

**Dependencies:** Epic 5 (Translation file must exist)

### Stories

#### Story 6.1: Update DEFAULT_LANGUAGE Configuration
**As a** system administrator  
**I want** default language to be Persian  
**So that** new users see Persian interface

**Acceptance Criteria:**
- [ ] `app/config.py` updated: DEFAULT_LANGUAGE = "fa"
- [ ] `app/localization/loader.py` uses "fa" as fallback
- [ ] Configuration tested
- [ ] Existing users keep their selected language

**Estimated Effort:** 2 hours

---

#### Story 6.2: Update New User Default Language
**As a** system  
**I want** new users to get Persian by default  
**So that** they see Persian interface

**Acceptance Criteria:**
- [ ] User creation sets language="fa" by default
- [ ] `app/database/crud/user.py` updated
- [ ] Existing users unchanged
- [ ] Tests verify default language

**Estimated Effort:** 1-2 hours

---

#### Story 6.3: Update System Messages Default Language
**As a** system  
**I want** system messages to use Persian  
**So that** all system communication is in Persian

**Acceptance Criteria:**
- [ ] System notifications use Persian
- [ ] Error messages use Persian
- [ ] Admin notifications use Persian (or configurable)
- [ ] Fallback to English if Persian missing (not Russian)

**Estimated Effort:** 3-4 hours

---

#### Story 6.4: Update Fallback Language Logic
**As a** developer  
**I want** fallback to English instead of Russian  
**So that** missing translations don't show Russian

**Acceptance Criteria:**
- [ ] Translation loader falls back to English, not Russian
- [ ] All fallback logic updated
- [ ] Tests verify fallback behavior
- [ ] No Russian shown when Persian missing

**Estimated Effort:** 2-3 hours

---

#### Story 6.5: Verify Language Selection Still Works
**As a** user  
**I want** to select my preferred language  
**So that** I can use the interface in my language

**Acceptance Criteria:**
- [ ] Language selection feature still works
- [ ] Users can choose ru, en, fa
- [ ] Selection persists across sessions
- [ ] All languages properly supported

**Estimated Effort:** 2 hours

---

**Epic 6 Total Estimated Effort:** 10-13 hours

---

## Epic 7: API Tenant Awareness

**Epic Goal:** Update all existing API endpoints to be tenant-aware and add new tenant management endpoints.

**Related FRs:** FR49-FR55

**Dependencies:** Epic 1, Epic 4

### Stories

#### Story 7.1: Update Existing API Endpoints for Tenant Filtering
**As a** developer  
**I want** all API endpoints to filter by tenant_id  
**So that** API responses are tenant-scoped

**Acceptance Criteria:**
- [ ] All GET endpoints filter results by tenant_id
- [ ] All POST/PUT/DELETE endpoints validate tenant_id
- [ ] Tenant context extracted from API token
- [ ] All route modules updated (22 modules)
- [ ] Integration tests verify tenant isolation

**Estimated Effort:** 10-12 hours

---

#### Story 7.2: Update API Token System for Tenant Scoping
**As a** developer  
**I want** API tokens to include tenant context  
**So that** tokens are tenant-scoped

**Acceptance Criteria:**
- [ ] WebApiToken model has tenant_id
- [ ] Token creation requires tenant_id
- [ ] Token validation extracts tenant_id
- [ ] Token endpoints updated
- [ ] System admin tokens can access all tenants

**Estimated Effort:** 4-5 hours

---

#### Story 7.3: Add Tenant Management API Endpoints
**As a** system administrator  
**I want** API endpoints for tenant management  
**So that** I can manage tenants programmatically

**Acceptance Criteria:**
- [ ] Endpoints implemented: GET /api/tenants, GET /api/tenants/{id}, POST /api/tenants, PUT /api/tenants/{id}, POST /api/tenants/{id}/suspend, POST /api/tenants/{id}/activate
- [ ] Pydantic schemas created
- [ ] Authentication and authorization
- [ ] API documentation updated
- [ ] Integration tests written

**Estimated Effort:** 6-8 hours

---

#### Story 7.4: Add Tenant Statistics API Endpoints
**As a** system administrator  
**I want** API endpoints for tenant statistics  
**So that** I can get analytics data

**Acceptance Criteria:**
- [ ] GET /api/tenants/{id}/statistics endpoint
- [ ] GET /api/tenants/{id}/analytics endpoint
- [ ] Statistics calculated efficiently
- [ ] Period filtering supported
- [ ] Integration tests written

**Estimated Effort:** 4-5 hours

---

#### Story 7.5: Add Bot Request API Endpoint
**As a** user  
**I want** to request a bot via API  
**So that** I can integrate with external systems

**Acceptance Criteria:**
- [ ] POST /api/bot-requests endpoint
- [ ] Request validation
- [ ] Tracking code generation
- [ ] Status check endpoint
- [ ] Integration tests written

**Estimated Effort:** 3-4 hours

---

**Epic 7 Total Estimated Effort:** 27-34 hours

---

## Epic 8: Bot Functionality Tenant Isolation

**Epic Goal:** Ensure each tenant's bot instance operates independently with proper data isolation.

**Related FRs:** FR56-FR62

**Dependencies:** Epic 1, Epic 4

### Stories

#### Story 8.1: Update Bot Initialization for Multi-Tenant
**As a** developer  
**I want** bot initialization to support multiple bot tokens  
**So that** each tenant has their own bot instance

**Acceptance Criteria:**
- [ ] Bot factory supports multiple tokens
- [ ] Each tenant's bot token creates separate bot instance
- [ ] Bot instances share codebase but have separate handlers
- [ ] Main bot (tenant_id=1) continues to work
- [ ] Representative bots work independently

**Estimated Effort:** 6-8 hours

---

#### Story 8.2: Update Webhook Routing for Tenant Identification
**As a** developer  
**I want** webhooks to identify tenant from bot token  
**So that** messages route to correct tenant

**Acceptance Criteria:**
- [ ] Webhook handler extracts bot token from update (or webhook secret)
- [ ] Bot token mapped to tenant_id via database lookup
- [ ] Tenant context injected into request
- [ ] Messages routed to correct tenant's bot instance and dispatcher
- [ ] Error handling for unknown/invalid tokens
- [ ] Webhook path strategy: Single path with token detection (not per-tenant paths)
- [ ] Tests verify routing for all tenant scenarios

**Technical Notes:**
- **Webhook Strategy:** Single webhook path (e.g., `/webhook/telegram`)
- **Token Detection:** Extract from update metadata or use webhook secret token mapping
- **Routing:** Lookup tenant by bot_token, get bot instance from registry, route to dispatcher
- **Fallback:** If token not found, log error and return 404

**Estimated Effort:** 6-8 hours

---

#### Story 8.3: Verify User Data Isolation
**As a** system  
**I want** users from different tenants to be isolated  
**So that** Tenant A users cannot see Tenant B data

**Acceptance Criteria:**
- [ ] Users filtered by tenant_id in all queries
- [ ] User cannot access other tenant's data
- [ ] Subscription data isolated
- [ ] Transaction data isolated
- [ ] Integration tests verify isolation

**Estimated Effort:** 4-5 hours

---

#### Story 8.4: Verify Subscription Data Isolation
**As a** system  
**I want** subscriptions to be tenant-isolated  
**So that** each tenant manages their own subscriptions

**Acceptance Criteria:**
- [ ] Subscriptions filtered by tenant_id
- [ ] Subscription operations respect tenant boundaries
- [ ] Payment processing uses tenant context
- [ ] Integration tests verify isolation

**Estimated Effort:** 3-4 hours

---

#### Story 8.5: Verify Tenant-Specific Settings
**As a** tenant admin  
**I want** to configure my tenant's settings  
**So that** my bot operates with my preferences

**Acceptance Criteria:**
- [ ] Tenant settings loaded from tenant.settings JSONB
- [ ] Settings applied to bot behavior
- [ ] Settings can be updated via API
- [ ] Default settings provided
- [ ] Tests verify settings application

**Estimated Effort:** 4-5 hours

---

**Epic 8 Total Estimated Effort:** 21-27 hours

---

## Epic 9: Backward Compatibility

**Epic Goal:** Ensure existing functionality continues to work without disruption during and after migration.

**Related FRs:** FR63-FR70

**Dependencies:** All previous Epics

### Stories

#### Story 9.1: Verify Existing Users Continue to Work
**As an** existing user  
**I want** my account to continue working  
**So that** I experience no disruption

**Acceptance Criteria:**
- [ ] All existing users have tenant_id=1
- [ ] Users can log in and use bot
- [ ] All features work as before
- [ ] No data loss
- [ ] Integration tests verify functionality

**Estimated Effort:** 4-5 hours

---

#### Story 9.2: Verify Existing Subscriptions Continue to Work
**As an** existing user  
**I want** my subscription to continue working  
**So that** I don't lose service

**Acceptance Criteria:**
- [ ] All existing subscriptions have tenant_id=1
- [ ] Subscriptions remain active
- [ ] Payment processing works
- [ ] Renewal works
- [ ] Integration tests verify functionality

**Estimated Effort:** 3-4 hours

---

#### Story 9.3: Verify Existing Transactions Remain Accessible
**As an** existing user  
**I want** my transaction history to remain accessible  
**So that** I can view past payments

**Acceptance Criteria:**
- [ ] All existing transactions have tenant_id=1
- [ ] Transaction history displays correctly
- [ ] No transaction data lost
- [ ] Reports work correctly
- [ ] Integration tests verify functionality

**Estimated Effort:** 2-3 hours

---

#### Story 9.4: Verify Admin Functionality Remains Operational
**As an** administrator  
**I want** admin features to continue working  
**So that** I can manage the system

**Acceptance Criteria:**
- [ ] Admin panel works
- [ ] User management works
- [ ] Subscription management works
- [ ] Analytics work
- [ ] All admin features tested

**Estimated Effort:** 4-5 hours

---

#### Story 9.5: Verify Payment Integrations Continue to Work
**As a** system  
**I want** payment providers to continue working  
**So that** users can make payments

**Acceptance Criteria:**
- [ ] All 9 payment providers work
- [ ] Webhooks include tenant context
- [ ] Payment processing uses tenant_id
- [ ] No payment failures
- [ ] Integration tests verify all providers

**Estimated Effort:** 5-6 hours

---

#### Story 9.6: Verify RemnaWave Integration Continues to Work
**As a** system  
**I want** RemnaWave integration to continue working  
**So that** VPN subscriptions function

**Acceptance Criteria:**
- [ ] RemnaWave API calls work
- [ ] Server sync works
- [ ] Subscription sync works
- [ ] All RemnaWave features tested
- [ ] Integration tests verify functionality

**Estimated Effort:** 3-4 hours

---

#### Story 9.7: Verify Database Migrations Are Non-Destructive
**As a** system administrator  
**I want** migrations to preserve all data  
**So that** no information is lost

**Acceptance Criteria:**
- [ ] All migrations tested on copy of production data
- [ ] No data loss during migration
- [ ] Rollback plan documented
- [ ] Migration scripts verified
- [ ] Backup strategy in place

**Estimated Effort:** 4-5 hours

---

#### Story 9.8: Verify API Compatibility Maintained
**As an** API user  
**I want** existing API endpoints to continue working  
**So that** my integrations don't break

**Acceptance Criteria:**
- [ ] All existing API endpoints work
- [ ] Response formats unchanged (except tenant filtering)
- [ ] Authentication works
- [ ] No breaking changes
- [ ] API documentation updated

**Estimated Effort:** 3-4 hours

---

**Epic 9 Total Estimated Effort:** 28-36 hours

---

## Summary

### Epic Breakdown

| Epic | Stories | Estimated Hours |
|------|---------|----------------|
| Epic 1: Multi-Tenancy Database Foundation | 10 | 24-30 |
| Epic 2: Tenant Management | 4 | 16-21 |
| Epic 3: Representative Bot Provisioning | 6 | 19-25 |
| Epic 4: Tenant Context Management | 5 | 32-40 |
| Epic 5: Localization - Remove Hardcoded Russian | 6 | 28-38 |
| Epic 6: Localization - Persian as Default | 5 | 10-13 |
| Epic 7: API Tenant Awareness | 5 | 27-34 |
| Epic 8: Bot Functionality Tenant Isolation | 5 | 21-27 |
| Epic 9: Backward Compatibility | 8 | 28-36 |
| **Total** | **54** | **205-264 hours** |

### Recommended Implementation Order

1. **Epic 1** (Foundation) - Must be first
2. **Epic 5** (Localization cleanup) - Can be parallel with Epic 1
3. **Epic 6** (Persian default) - After Epic 5
4. **Epic 2** (Tenant Management) - After Epic 1
5. **Epic 4** (Tenant Context) - After Epic 1
6. **Epic 3** (Bot Provisioning) - After Epic 2
7. **Epic 7** (API Updates) - After Epic 4
8. **Epic 8** (Bot Isolation) - After Epic 4
9. **Epic 9** (Backward Compatibility) - Continuous throughout, final verification

### Critical Path

Epic 1 → Epic 2 → Epic 4 → Epic 7 → Epic 8 → Epic 9

### Parallel Work Opportunities

- Epic 5 & Epic 6 can be done in parallel with Epic 1-4
- Epic 3 can start after Epic 2 is complete
- Epic 9 testing can be done continuously

---

**Document Status:** Ready for Sprint Planning  
**Review Required:** Yes - Product & Development Team  
**Approval Required:** Yes - Technical Lead

