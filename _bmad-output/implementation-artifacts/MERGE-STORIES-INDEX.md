# Merge Upstream Main - Stories Index (5 Stories)

**Epic:** MERGE-UPSTREAM-MAIN (Temporary)  
**Status:** 🚧 In Progress  
**Total Stories:** 5  
**Created:** 2026-01-03

---

## 📋 Overview

این فایل لیست 5 Story بزرگ برای merge کردن `upstream/main` به برنچ فعلی است. Story‌ها به صورت موقت ایجاد شده‌اند و بعد از اتمام merge باید حذف شوند.

**⚠️ توجه:** این Story‌ها خارج از برنامه اصلی هستند و فقط برای merge استفاده می‌شوند.

---

## 🗂️ Story List

| Story ID | Title | Status | Priority | Time | Dependencies |
|----------|-------|--------|----------|------|--------------|
| [MERGE-1](./MERGE-1-setup-core-infrastructure.md) | Setup, Validation & Core Infrastructure | ready-for-dev | 🔴 Critical | 17h | None |
| [MERGE-2](./MERGE-2-cabinet-module.md) | Cabinet Module - Tenant-Aware Refactoring | ready-for-dev | 🔴 Critical | 25h | MERGE-1 |
| [MERGE-3](./MERGE-3-crud-services-handlers.md) | CRUD Operations, Services & Handlers | ready-for-dev | 🟡 High | 87h | MERGE-2 |
| [MERGE-4](./MERGE-4-nalogo-bugfixes-testing.md) | Nalogo Integration, Bug Fixes & Testing | ready-for-dev | 🟡 High | 47h | MERGE-3 |
| [MERGE-5](./MERGE-5-documentation-cleanup.md) | Documentation & Cleanup | ready-for-dev | 🟢 Medium | 12h | MERGE-4 |

---

## 📊 Progress Summary

### By Status
- ✅ **Complete:** 0
- ⏳ **In Progress:** 0
- 📋 **Ready for Dev:** 5
- ⏸️ **Pending:** 0
- ❌ **Blocked:** 0

### By Priority
- 🔴 **Critical:** 2 stories (MERGE-1, MERGE-2)
- 🟡 **High:** 2 stories (MERGE-3, MERGE-4)
- 🟢 **Medium:** 1 story (MERGE-5)

### Estimated Total Time
- **MERGE-1:** 17 hours (Setup & Core)
- **MERGE-2:** 25 hours (Cabinet Module)
- **MERGE-3:** 87 hours (CRUD, Services, Handlers)
- **MERGE-4:** 47 hours (Nalogo, Bug Fixes, Testing)
- **MERGE-5:** 12 hours (Documentation & Cleanup)

**Total:** ~188 hours (~23.5 working days / ~5 weeks)

---

## 🎯 Execution Order

### Week 1: Setup & Core Infrastructure
1. **MERGE-1:** Setup, Validation & Core Infrastructure (17h)
   - Phase 0: Setup & Backup (5h)
   - Phase 1: Core Infrastructure (12h)

### Week 2: Cabinet Module
2. **MERGE-2:** Cabinet Module - Tenant-Aware Refactoring (25h)
   - Phase 2.1: Add Cabinet Module (2h)
   - Phase 2.2: Refactor Auth (7h)
   - Phase 2.3: Update Dependencies (2h)
   - Phase 2.4: Refactor Routes (12h)
   - Phase 2.5: Register Routes (2h)

### Week 3-4: CRUD, Services & Handlers
3. **MERGE-3:** CRUD Operations, Services & Handlers (87h)
   - Phase 3: CRUD Operations (27h)
   - Phase 4: Services (31h)
   - Phase 5: Handlers (29h)

### Week 5: Integration, Testing & Cleanup
4. **MERGE-4:** Nalogo Integration, Bug Fixes & Testing (47h)
   - Phase 6: Nalogo Integration (9h)
   - Phase 7: Bug Fixes (10h)
   - Phase 8: Testing & Validation (25h)
   - Manual Testing (3h)

5. **MERGE-5:** Documentation & Cleanup (12h)
   - Phase 9: Documentation (7h)
   - Phase 10: Cleanup (5h)

---

## 📝 Story Details

### MERGE-1: Setup, Validation & Core Infrastructure
**Scope:**
- Setup backup and merge branch
- Create validation scripts (3 scripts)
- Refactor config for tenant-aware Cabinet and Nalogo
- Add Cabinet columns to User model
- Add Promocode first_purchase_only field

**Key Deliverables:**
- Validation scripts working
- Tenant-aware config helpers
- Database migrations ready
- Foundation for all other stories

### MERGE-2: Cabinet Module - Tenant-Aware Refactoring
**Scope:**
- Copy Cabinet module from upstream (31 files)
- Refactor JWT handler for tenant-aware
- Refactor Telegram auth for tenant-aware
- Refactor all Cabinet routes (17 files)
- Register Cabinet router
- Create integration tests

**Key Deliverables:**
- Cabinet module working with tenant isolation
- All routes have tenant dependency
- Error handling for tenant mismatch
- Integration tests passing

### MERGE-3: CRUD Operations, Services & Handlers
**Scope:**
- Update Promocode CRUD (first_purchase_only, pagination)
- Update Subscription CRUD (traffic reset, auto-activation)
- Update User CRUD (balance filters)
- Merge remaining CRUD files (47 files in 3 batches)
- Update Subscription Service
- Refactor Cart Service (tenant-aware Redis keys)
- Merge Payment Service
- Merge remaining Services (57 files in 3 batches)
- Merge Subscription Handlers
- Merge Admin Handlers
- Merge remaining Handlers (77 files in 3 batches with checkpoints)

**Key Deliverables:**
- All CRUD operations tenant-aware
- All services tenant-aware
- All handlers tenant-aware
- Validation scripts pass
- Code review checkpoints complete

### MERGE-4: Nalogo Integration, Bug Fixes & Testing
**Scope:**
- Refactor Nalogo Service for tenant-aware config
- Migrate existing Nalogo config
- Integrate Nalogo with Payment Service
- Cherry-pick Promocode bug fixes
- Cherry-pick Subscription bug fixes
- Cherry-pick Payment bug fixes (Iranian only)
- Cherry-pick other bug fixes
- Run all unit tests
- Run integration tests
- Create Cabinet integration tests
- Create Nalogo integration tests
- Manual testing checklist
- Database schema validation
- Code quality check

**Key Deliverables:**
- Nalogo working with tenant config
- All bug fixes applied
- All tests passing (>80% coverage)
- Tenant isolation verified
- Code quality verified

### MERGE-5: Documentation & Cleanup
**Scope:**
- Update PRD with Cabinet feature
- Update Architecture document
- Update API documentation
- Create changelog
- Remove temporary story files
- Cleanup git branches
- Verify codebase state
- Create cleanup report

**Key Deliverables:**
- All documentation updated
- Temporary files removed
- Codebase ready for PRD workflow
- Cleanup report created

---

## ✅ Definition of Done

هر Story زمانی Complete است که:
1. ✅ تمام Tasks انجام شده باشند
2. ✅ تمام Acceptance Criteria برآورده شده باشند
3. ✅ تمام Tests passing باشند
4. ✅ Validation Scripts pass باشند
5. ✅ Results & Issues section تکمیل شده باشد
6. ✅ Story Status = ✅ Complete

---

## 🚨 Critical Path

**Blocking Dependencies:**
- MERGE-1 → MERGE-2 (Cabinet needs config helpers)
- MERGE-2 → MERGE-3 (CRUD/Services/Handlers need Cabinet)
- MERGE-3 → MERGE-4 (Testing needs all code merged)
- MERGE-4 → MERGE-5 (Cleanup needs testing complete)

**Parallel Work:**
- Within MERGE-3: CRUD batches can be parallelized
- Within MERGE-3: Service batches can be parallelized
- Within MERGE-3: Handler batches can be parallelized (with checkpoints)

---

## 📊 Tracking

### Story Status Updates
هر Story باید status خود را در Results section update کند:
- ⏳ In Progress
- ✅ Complete
- ❌ Blocked

### Issues & Bugs Tracking
تمام Issues و Bugs باید در Results & Issues section document شوند:
- Description
- Severity (🔴 Critical / 🟡 Medium / 🟢 Low)
- Status (Open / Fixed)
- Location (File:Line)
- Fix (Solution)

### Progress Tracking
- هر Story باید progress خود را در Results section track کند
- Batch progress برای MERGE-3 باید document شود
- Test results باید document شود

---

## 🎯 Success Criteria

**Merge موفق است اگر:**
1. ✅ تمام 5 Story complete باشند
2. ✅ تمام Tests passing باشند (>80% coverage)
3. ✅ Validation Scripts pass باشند
4. ✅ Tenant Isolation verified باشد
5. ✅ Documentation updated باشد
6. ✅ Codebase ready for PRD باشد

---

**Last Updated:** 2026-01-03  
**Next Review:** After MERGE-1 completion
