# Sprint Planning - Multi-Tenancy Transformation

**Author:** Product & Development Team  
**Date:** 2025-11-21  
**Version:** 1.0

---

## Overview

This document organizes Epics and Stories into executable Sprints. Each Sprint is 2 weeks (80 hours) with a focused goal.

**Sprint Duration:** 2 weeks (80 hours)  
**Team Size:** 1-2 developers  
**Total Estimated Effort:** 212-272 hours (updated after review fixes)  
**Total Sprints:** 4-5 Sprints

---

## Sprint 1: Foundation & Localization (Week 1-2)

**Sprint Goal:** Establish database foundation and complete localization refactoring

**Duration:** 2 weeks (80 hours)  
**Focus:** Database schema + Localization cleanup

### Stories

#### Epic 1: Multi-Tenancy Database Foundation
- **Story 1.1:** Create Tenant Table and Model (3-4h)
- **Story 1.2:** Create Main Tenant (tenant_id=1) (1-2h) - *Updated: includes bot_token initialization*
- **Story 1.3:** Add tenant_id to Users Table (2-3h)
- **Story 1.4:** Add tenant_id to Subscriptions Table (2h)
- **Story 1.5:** Add tenant_id to Transactions Table (2h)
- **Story 1.6:** Add tenant_id to Tickets and TicketMessages (2h)
- **Story 1.7:** Add tenant_id to Promo System Tables (3-4h)
- **Story 1.8:** Add tenant_id to Remaining Tenant-Scoped Tables (4-5h)
- **Story 1.9:** Add tenant_id to Payment Provider Tables (3-4h)
- **Story 1.10:** Create Composite Indexes for Performance (2h)

**Epic 1 Subtotal:** 24-30 hours

#### Epic 5: Localization - Remove Hardcoded Russian (Parallel Work)
- **Story 5.1:** Audit Hardcoded Russian Strings (2-3h)
- **Story 5.2:** Create Persian Translation File (4-6h)
- **Story 5.3:** Replace Hardcoded Strings in Handlers (8-10h)
- **Story 5.4:** Replace Hardcoded Strings in Services (6-8h)
- **Story 5.5:** Replace Hardcoded Strings in Keyboards (4-5h)
- **Story 5.6:** Replace Hardcoded Strings in Other Modules (4-6h)

**Epic 5 Subtotal:** 28-38 hours

#### Epic 6: Localization - Persian as Default (After Epic 5)
- **Story 6.1:** Update DEFAULT_LANGUAGE Configuration (2h)
- **Story 6.2:** Update New User Default Language (1-2h)
- **Story 6.3:** Update System Messages Default Language (3-4h)
- **Story 6.4:** Update Fallback Language Logic (2-3h)
- **Story 6.5:** Verify Language Selection Still Works (2h)

**Epic 6 Subtotal:** 10-13 hours

**Sprint 1 Total:** 62-81 hours  
**Buffer:** 0-18 hours (for testing, code review, unexpected issues)

**Sprint 1 Deliverables:**
- ✅ Complete database schema with tenant_id in all tables
- ✅ All migrations tested and ready
- ✅ Zero hardcoded Russian strings
- ✅ Persian translation file complete
- ✅ Persian as default language

---

## Sprint 2: Tenant Management & Context (Week 3-4)

**Sprint Goal:** Implement tenant management and tenant context system

**Duration:** 2 weeks (80 hours)  
**Focus:** Tenant CRUD + Context Management

### Stories

#### Epic 2: Tenant Management
- **Story 2.1:** Create Tenant CRUD Operations (3-4h)
- **Story 2.2:** Create TenantService (4-5h)
- **Story 2.3:** Create Tenant API Endpoints (6-8h)
- **Story 2.4:** Add Tenant Statistics to API (3-4h)

**Epic 2 Subtotal:** 16-21 hours

#### Epic 4: Tenant Context Management
- **Story 4.1:** Create Tenant Context Middleware (4-5h)
- **Story 4.2:** Update Service Layer for Tenant Filtering (10-12h) - *Updated: includes limits enforcement*
- **Story 4.3:** Update CRUD Operations for Tenant Filtering (10-12h)
- **Story 4.4:** Update Bot Handlers for Tenant Context (6-8h)
- **Story 4.5:** Update API Authentication for Tenant Scoping (4-5h)

**Epic 4 Subtotal:** 34-42 hours

**Sprint 2 Total:** 50-63 hours  
**Buffer:** 17-30 hours (for testing, integration, bug fixes)

**Sprint 2 Deliverables:**
- ✅ Tenant CRUD operations working
- ✅ Tenant API endpoints functional
- ✅ Tenant context middleware active
- ✅ All services filter by tenant_id
- ✅ All CRUD operations tenant-aware

---

## Sprint 3: Bot Provisioning & API Updates (Week 5-6)

**Sprint Goal:** Enable bot provisioning and update all API endpoints

**Duration:** 2 weeks (80 hours)  
**Focus:** Bot Provisioning + API Tenant Awareness

### Stories

#### Epic 3: Representative Bot Provisioning
- **Story 3.1:** Create Bot Request Model and CRUD (2-3h)
- **Story 3.2:** Add Bot Request Menu Item to Main Bot (2-3h)
- **Story 3.3:** Implement Bot Request Form Flow (4-5h)
- **Story 3.4:** Create Bot Request Approval Workflow (4-5h)
- **Story 3.5:** Implement Automated Bot Provisioning (6-8h) - *Updated: includes bot token validation*
- **Story 3.6:** Add Bot Request Status Check (2-3h)

**Epic 3 Subtotal:** 20-27 hours

#### Epic 7: API Tenant Awareness
- **Story 7.1:** Update Existing API Endpoints for Tenant Filtering (10-12h)
- **Story 7.2:** Update API Token System for Tenant Scoping (4-5h)
- **Story 7.3:** Add Tenant Management API Endpoints (6-8h) - *May overlap with Epic 2*
- **Story 7.4:** Add Tenant Statistics API Endpoints (4-5h)
- **Story 7.5:** Add Bot Request API Endpoint (3-4h)

**Epic 7 Subtotal:** 27-34 hours

**Sprint 3 Total:** 47-61 hours  
**Buffer:** 19-33 hours (for testing, integration, edge cases)

**Sprint 3 Deliverables:**
- ✅ Bot request flow complete
- ✅ Automated bot provisioning working
- ✅ All API endpoints tenant-aware
- ✅ API tokens tenant-scoped
- ✅ Tenant statistics API functional

---

## Sprint 4: Bot Isolation & Backward Compatibility (Week 7-8)

**Sprint Goal:** Ensure bot isolation and verify backward compatibility

**Duration:** 2 weeks (80 hours)  
**Focus:** Bot Isolation + Compatibility Testing

### Stories

#### Epic 8: Bot Functionality Tenant Isolation
- **Story 8.1:** Update Bot Initialization for Multi-Tenant (8-10h) - *Updated: includes bot registry and factory*
- **Story 8.2:** Update Webhook Routing for Tenant Identification (6-8h) - *Updated: includes routing strategy*
- **Story 8.3:** Verify User Data Isolation (4-5h)
- **Story 8.4:** Verify Subscription Data Isolation (3-4h)
- **Story 8.5:** Verify Tenant-Specific Settings (4-5h)

**Epic 8 Subtotal:** 25-31 hours

#### Epic 9: Backward Compatibility
- **Story 9.1:** Verify Existing Users Continue to Work (4-5h)
- **Story 9.2:** Verify Existing Subscriptions Continue to Work (3-4h)
- **Story 9.3:** Verify Existing Transactions Remain Accessible (2-3h)
- **Story 9.4:** Verify Admin Functionality Remains Operational (4-5h)
- **Story 9.5:** Verify Payment Integrations Continue to Work (5-6h)
- **Story 9.6:** Verify RemnaWave Integration Continues to Work (3-4h)
- **Story 9.7:** Verify Database Migrations Are Non-Destructive (4-5h)
- **Story 9.8:** Verify API Compatibility Maintained (3-4h)

**Epic 9 Subtotal:** 28-36 hours

**Sprint 4 Total:** 53-67 hours  
**Buffer:** 13-27 hours (for bug fixes, edge cases, final testing)

**Sprint 4 Deliverables:**
- ✅ Each tenant's bot operates independently
- ✅ Complete data isolation verified
- ✅ All existing functionality works
- ✅ All integrations tested
- ✅ Production-ready system

---

## Sprint 5: Polish & Production Readiness (Week 9-10) - Optional

**Sprint Goal:** Final polish, performance optimization, and production deployment

**Duration:** 2 weeks (80 hours) - **May not be needed if Sprints 1-4 complete everything**

**Focus:** Optimization, Documentation, Deployment

### Potential Stories

- Performance optimization and query tuning
- Comprehensive integration testing
- Security audit
- Documentation completion
- Deployment scripts and procedures
- Monitoring and alerting setup
- Load testing
- Bug fixes from previous sprints

**Sprint 5 Total:** Flexible (0-80 hours)

---

## Sprint Summary

| Sprint | Focus | Stories | Hours | Buffer |
|--------|-------|---------|-------|--------|
| **Sprint 1** | Foundation & Localization | 21 | 62-81 | 0-18 |
| **Sprint 2** | Tenant Management & Context | 9 | 50-63 | 17-30 |
| **Sprint 3** | Bot Provisioning & API | 11 | 47-61 | 19-33 |
| **Sprint 4** | Bot Isolation & Compatibility | 13 | 53-67 | 13-27 |
| **Sprint 5** | Polish & Production | TBD | 0-80 | TBD |
| **Total** | | **54+** | **205-264** | **57-115** |

---

## Critical Path

```
Sprint 1 (Epic 1) 
    ↓
Sprint 2 (Epic 2 + Epic 4)
    ↓
Sprint 3 (Epic 3 + Epic 7)
    ↓
Sprint 4 (Epic 8 + Epic 9)
```

**Parallel Work:**
- Epic 5 & Epic 6 can run in parallel with Epic 1 in Sprint 1
- Some Epic 7 stories can start in Sprint 2 if Epic 4 completes early

---

## Dependencies Map

```
Epic 1 (Database) 
    → Epic 2 (Tenant Management)
    → Epic 4 (Context Management)
        → Epic 3 (Bot Provisioning)
        → Epic 7 (API Updates)
            → Epic 8 (Bot Isolation)
                → Epic 9 (Compatibility)

Epic 5 (Localization Cleanup)
    → Epic 6 (Persian Default)
    (Can run in parallel with Epic 1)
```

---

## Risk Mitigation

### High-Risk Areas

1. **Database Migrations (Sprint 1)**
   - Risk: Data loss or migration failures
   - Mitigation: Test on production copy, backup strategy, rollback plan

2. **Service Layer Updates (Sprint 2)**
   - Risk: Missing tenant filtering, data leakage
   - Mitigation: Comprehensive unit tests, code review, integration tests

3. **Bot Provisioning (Sprint 3)**
   - Risk: Complex automation, edge cases
   - Mitigation: Phased rollout, manual approval option, extensive testing

4. **Backward Compatibility (Sprint 4)**
   - Risk: Breaking existing functionality
   - Mitigation: Continuous testing throughout, feature flags, gradual rollout

### Buffer Allocation

- **Sprint 1:** 0-18 hours buffer (tight, but foundation is critical)
- **Sprint 2:** 19-32 hours buffer (complex context management)
- **Sprint 3:** 21-34 hours buffer (API updates are extensive)
- **Sprint 4:** 17-31 hours buffer (testing and verification)

---

## Definition of Done

For each Sprint, all Stories must meet:

- [ ] Code written and reviewed
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] Documentation updated
- [ ] No hardcoded Russian strings (after Sprint 1)
- [ ] All database queries include tenant_id filter (after Sprint 2)
- [ ] All features work in multi-tenant context
- [ ] Backward compatibility verified
- [ ] Performance acceptable (<100ms for standard queries)

---

## Sprint Planning Recommendations

### Team Composition

**Option 1: Single Developer**
- Focus on one Epic at a time
- Sequential Sprint execution
- Total time: 4-5 Sprints (8-10 weeks)

**Option 2: Two Developers**
- Developer 1: Database + Context (Epic 1, 4)
- Developer 2: Localization + Management (Epic 5, 6, 2)
- Then combine for Epic 3, 7, 8, 9
- Total time: 3-4 Sprints (6-8 weeks)

### Daily Standup Focus

- **Sprint 1:** Migration progress, localization completion
- **Sprint 2:** Tenant context implementation, service updates
- **Sprint 3:** Bot provisioning flow, API endpoint updates
- **Sprint 4:** Isolation testing, compatibility verification

### Sprint Review Checklist

- [ ] All Sprint Stories completed
- [ ] Demo of new functionality
- [ ] Test results reviewed
- [ ] Blockers identified and resolved
- [ ] Next Sprint planned

---

## Success Metrics

### Sprint 1 Success
- ✅ All migrations run successfully
- ✅ Zero hardcoded Russian strings
- ✅ Persian translation complete

### Sprint 2 Success
- ✅ Tenant CRUD working
- ✅ All services filter by tenant_id
- ✅ No data leakage in tests

### Sprint 3 Success
- ✅ Bot request flow complete
- ✅ Automated provisioning works
- ✅ All API endpoints tenant-aware

### Sprint 4 Success
- ✅ Complete data isolation verified
- ✅ All existing features work
- ✅ Production deployment ready

---

**Document Status:** Ready for Team Review  
**Next Steps:** Team review, Story point estimation refinement, Sprint kickoff

