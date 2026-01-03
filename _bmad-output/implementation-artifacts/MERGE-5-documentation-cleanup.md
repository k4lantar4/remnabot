# Story MERGE-5: Documentation & Cleanup

**Status:** ready-for-dev  
**Epic:** MERGE-UPSTREAM-MAIN (Temporary)  
**Priority:** 🟢 MEDIUM  
**Estimated Time:** 12 hours  
**Dependencies:** MERGE-4

---

## Story

As a **developer**,  
I want to **update documentation, create changelog, and cleanup temporary merge artifacts**,  
so that **codebase is ready for PRD workflow with clean state and complete documentation**.

---

## Acceptance Criteria

1. ✅ **AC 5.1:** Given PRD document, when checking, then Cabinet feature is documented
2. ✅ **AC 5.2:** Given Architecture document, when checking, then Cabinet and Nalogo are documented
3. ✅ **AC 5.3:** Given API documentation, when checking, then all Cabinet endpoints are documented
4. ✅ **AC 5.4:** Given merge is complete, when cleanup is done, then all temporary MERGE-*.md files are removed
5. ✅ **AC 5.5:** Given codebase, when cleanup is done, then codebase is ready for PRD workflow

---

## Tasks / Subtasks

### Phase 9: Documentation (7 hours)

#### Task 9.1: Update PRD with Cabinet Feature
- [ ] **Action:** Document Cabinet feature in PRD
  - **Files:**
    - `_bmad-output/prd.md` (MODIFY, add section)
  - **Content to Add:**
    ```markdown
    ## Cabinet Feature
    
    ### FR-X: Cabinet Web Interface
    - Users can access web-based cabinet
    - Tenant-aware authentication
    - Per-tenant JWT secrets
    - Full user management via web interface
    ```
  - **Lines Affected:** Add new section (~50-100 lines)
  - **Verification:** PRD updated, requirements clear

#### Task 9.2: Update Architecture Document
- [ ] **Action:** Document Cabinet and Nalogo in architecture
  - **Files:**
    - `_bmad-output/architecture.md` (MODIFY, add sections)
  - **Content to Add:**
    ```markdown
    ## Cabinet Architecture
    - Tenant-aware JWT authentication
    - Per-tenant config for JWT secrets
    - Route structure and dependencies
    
    ## Nalogo Integration
    - Tenant-aware config
    - Receipt generation per tenant
    - Config migration strategy
    ```
  - **Lines Affected:** Add new sections (~100-200 lines)
  - **Verification:** Architecture updated, patterns documented

#### Task 9.3: Update API Documentation
- [ ] **Action:** Document Cabinet API endpoints
  - **Files:**
    - API documentation files (NEW or UPDATE)
  - **Content:**
    - All Cabinet endpoints
    - Tenant parameters
    - Request/response examples
    - Error codes
  - **Verification:** API docs complete, examples work

#### Task 9.4: Create Changelog
- [ ] **Action:** Generate changelog for merge
  - **Files:**
    - `CHANGELOG.md` (NEW or UPDATE)
  - **Content:**
    ```markdown
    ## [Unreleased] - YYYY-MM-DD
    
    ### Added
    - Cabinet module with tenant-aware authentication
    - Nalogo integration with tenant config
    - Validation scripts for tenant isolation
    - Promocode first_purchase_only feature
    - Subscription traffic reset on renewal
    
    ### Changed
    - Config system: Global env → Tenant config (Cabinet, Nalogo)
    - Cart service: Redis keys now include tenant prefix
    - All CRUD operations: Added bot_id filtering
    
    ### Fixed
    - [List bug fixes from cherry-picks]
    ```
  - **Verification:** Changelog complete, version bumped

### Phase 10: Cleanup (5 hours)

#### Task 10.1: Remove Temporary Story Files
- [ ] **Action:** Delete all MERGE-*.md story files
  - **Files to Delete:**
    - `_bmad-output/implementation-artifacts/MERGE-1-*.md`
    - `_bmad-output/implementation-artifacts/MERGE-2-*.md`
    - `_bmad-output/implementation-artifacts/MERGE-3-*.md`
    - `_bmad-output/implementation-artifacts/MERGE-4-*.md`
    - `_bmad-output/implementation-artifacts/MERGE-5-*.md`
  - **Command:**
    ```bash
    cd _bmad-output/implementation-artifacts/
    rm -f MERGE-*.md
    ```
  - **Verification:** No MERGE-*.md files remain

#### Task 10.2: Archive Merge Documentation (Optional)
- [ ] **Action:** Archive essential merge documentation
  - **Files to Keep:**
    - `_bmad-output/merge-implementation-guide.md` (KEEP - reference)
    - `_bmad-output/implementation-artifacts/tech-spec-merge-upstream-main-implementation.md` (KEEP - reference)
  - **Files to Archive/Delete:**
    - `_bmad-output/implementation-artifacts/MERGE-STORIES-INDEX.md` (ARCHIVE or DELETE)
  - **Verification:** Only essential docs remain

#### Task 10.3: Cleanup Git Branches
- [ ] **Action:** Merge merge branch to main and cleanup
  - **Commands:**
    ```bash
    git checkout main
    git merge merge/upstream-main-YYYYMMDD --no-ff -m "Merge upstream/main - Complete"
    git branch -d merge/upstream-main-YYYYMMDD
    git push origin --delete merge/upstream-main-YYYYMMDD  # if pushed
    # Keep backup branch for safety
    ```
  - **Verification:** Merge branch merged, main updated

#### Task 10.4: Verify Codebase State
- [ ] **Action:** Verify codebase is clean and ready
  - **Checks:**
    ```bash
    # Check for temporary files
    find . -name "MERGE-*.md" -type f
    
    # Check git status
    git status
    
    # Run all tests
    pytest tests/ -v
    
    # Run validation scripts
    python scripts/validate_bot_id_queries.py
    python scripts/validate_tenant_context.py
    python scripts/validate_redis_keys.py
    ```
  - **Verification:** All checks pass

#### Task 10.5: Create Cleanup Report
- [ ] **Action:** Document cleanup actions
  - **Files:**
    - `docs/merge-cleanup-report-YYYYMMDD.md` (NEW)
  - **Content:**
    ```markdown
    # Merge Cleanup Report
    
    **Date:** YYYY-MM-DD
    **Status:** ✅ Complete
    
    ## Actions Taken
    - Removed X temporary story files
    - Merged merge branch to main
    - Updated documentation
    - Verified codebase state
    
    ## Files Removed
    - [List]
    
    ## Files Kept
    - [List with reasons]
    
    ## Verification Results
    - All tests passing: ✅
    - Validation scripts passing: ✅
    - Git status clean: ✅
    
    ## Ready for PRD
    - ✅ Codebase clean
    - ✅ All merge work complete
    - ✅ Documentation updated
    - ✅ Ready to start PRD workflow
    ```
  - **Verification:** Report created, all items documented

---

## Dev Notes

### Critical Requirements
- ✅ **MUST** update all documentation before cleanup
- ✅ **MUST** verify codebase state before declaring ready
- ✅ **MUST** keep essential merge documentation (reference)
- ✅ **MUST** document all cleanup actions

### Files Affected

**Modified Files:**
- `_bmad-output/prd.md` (add Cabinet section)
- `_bmad-output/architecture.md` (add Cabinet and Nalogo sections)
- API documentation files (add Cabinet endpoints)
- `CHANGELOG.md` (add merge changes)

**New Files:**
- `docs/merge-cleanup-report-YYYYMMDD.md` (cleanup documentation)

**Files to Delete:**
- All `MERGE-*.md` story files (5 files)
- `MERGE-STORIES-INDEX.md` (optional)

### Documentation Strategy

**PRD Updates:**
- Add Cabinet feature requirements
- Update user stories
- Add acceptance criteria

**Architecture Updates:**
- Document Cabinet architecture
- Document Nalogo integration pattern
- Update diagrams if needed

**API Documentation:**
- Document all Cabinet endpoints
- Add tenant parameters
- Add examples

### Cleanup Strategy

**Phase 1: Documentation**
- Update all docs first
- Create changelog
- Verify completeness

**Phase 2: File Cleanup**
- Remove temporary story files
- Archive/delete index
- Keep essential references

**Phase 3: Git Cleanup**
- Merge to main
- Delete temporary branches
- Keep backup branch (optional)

**Phase 4: Verification**
- Run all checks
- Verify state
- Create cleanup report

---

## Results & Issues

### Completion Status
- [ ] Phase 9 complete (Documentation)
- [ ] Phase 10 complete (Cleanup)
- [ ] All documentation updated
- [ ] All temporary files removed
- [ ] Codebase verified
- [ ] All ACs verified

### Issues Found
- **Issue 1:** [Description]
  - **Severity:** 🔴 Critical / 🟡 Medium / 🟢 Low
  - **Status:** Open / Fixed
  - **Location:** [File:Line]
  - **Fix:** [Solution]

### Documentation Status
- **PRD Updated:** ✅ Yes / ❌ No
- **Architecture Updated:** ✅ Yes / ❌ No
- **API Docs Updated:** ✅ Yes / ❌ No
- **Changelog Created:** ✅ Yes / ❌ No

### Cleanup Status
- **Story Files Removed:** [X] files
- **Git Branches Cleaned:** ✅ Yes / ❌ No
- **Codebase Verified:** ✅ Yes / ❌ No
- **Cleanup Report Created:** ✅ Yes / ❌ No

### Verification Results
- **Tests:** [X/Y] passing
- **Validation Scripts:** [X/Y] passing
- **Git Status:** Clean / Issues found
- **Codebase State:** ✅ Ready for PRD / ❌ Not Ready

### Next Steps
- [ ] ✅ **READY FOR PRD WORKFLOW**
- [ ] Start PRD creation workflow
- [ ] Begin epic and story creation for main product

---

**Story Status:** ⏳ In Progress / ✅ Complete / ❌ Blocked  
**Completed At:** [Date/Time]  
**Completed By:** [Developer Name]  
**Codebase Status:** ✅ Ready for PRD / ❌ Not Ready
