# Story #001: حذف فایل‌های درگاه‌های پرداخت روسی - فاز 1

**Epic:** Pre-MVP Cleanup
**Sprint:** Week 1
**Story Points:** 2
**Priority:** P0 (Critical - Blocking)
**Assignee:** [Dev Name]
**Created:** 2025-12-26
**Status:** Ready for Development

---

## 📋 Story Description

به عنوان یک developer، باید تمام فایل‌های مربوط به درگاه‌های پرداخت روسی را از codebase حذف کنم تا:
1. Codebase تمیز شود
2. Confusion برای AI agents کاهش یابد
3. پایه برای multi-tenant SaaS آماده شود

**Context:** ما داریم از یک ربات VPN تک‌نفره روسی به پلتفرم SaaS multi-tenant ایرانی migrate می‌کنیم. درگاه‌های پرداخت روسی دیگر نیاز نیستند.

---

## 🎯 Acceptance Criteria

### Must Have (باید انجام شود):

- [ ] **27 فایل درگاه‌های روسی حذف شوند:**
  - [ ] 7 فایل External layer
  - [ ] 6 فایل Service layer (individual)
  - [ ] 7 فایل Service/payment module
  - [ ] 7 فایل Handler/balance

- [ ] **Git commit با message مناسب ایجاد شود**
  - Format: "cleanup: Remove Russian payment gateway files (27 files)"
  - شامل توضیحات کامل

- [ ] **No import errors:**
  - Application باید بدون خطا start شود
  - Verification command ها pass شوند

- [ ] **Tests pass:**
  - همه unit tests موجود pass شوند
  - اگر test fail شد، fix یا skip کنید (با توضیح)

### Nice to Have (اختیاری):

- [ ] Update any related documentation
- [ ] Add comment در PR توضیح میده چرا این فایل‌ها حذف شدند

---

## 📁 فایل‌های مرجع (باید بخوانید)

### 1. راهنمای اجرا (اصلی):
**File:** `_bmad-output/project-planning-artifacts/cleanup-execution-guide.md`

این فایل شامل:
- ✅ Checklist کامل 27 فایل
- ✅ دستورات bash دقیق (ready to copy-paste)
- ✅ دستورات verification
- ✅ نمونه commit message

**⚠️ مهم:** تمام این فایل را بخوانید قبل از شروع!

### 2. برنامه کامل پاکسازی:
**File:** `_bmad-output/project-planning-artifacts/russian-artifacts-removal-plan.md`

Context کامل برای:
- چرا این کار را می‌کنیم
- برنامه 3 هفته‌ای
- فاز 2 و 3 چه خواهند بود

### 3. Database Audit:
**File:** `_bmad-output/project-planning-artifacts/database-audit-report.md`

اطلاعات database (برای فاز‌های بعدی)

---

## 🚀 مراحل اجرا (Step by Step)

### Step 1: Setup (5 دقیقه)

```bash
# 1. Clone یا pull latest
cd /path/to/remnabot
git checkout dev5-from-upstream  # یا هر branch اصلی شما
git pull origin dev5-from-upstream

# 2. Create feature branch
git checkout -b cleanup/russian-gateways-phase1

# 3. باز کردن فایل راهنما
# باز کنید: _bmad-output/project-planning-artifacts/cleanup-execution-guide.md
```

### Step 2: Delete Files (10 دقیقه)

**از فایل `cleanup-execution-guide.md` صفحه "Week 1, Days 3-5" را دنبال کنید.**

```bash
# External Layer (7 files)
rm app/external/yookassa_webhook.py
rm app/external/wata_webhook.py
rm app/external/pal24_client.py
rm app/external/pal24_webhook.py
rm app/external/heleket.py
rm app/external/heleket_webhook.py
rm app/external/tribute.py

# Service Layer - Individual (6 files)
rm app/services/wata_service.py
rm app/services/yookassa_service.py
rm app/services/tribute_service.py
rm app/services/mulenpay_service.py
rm app/services/pal24_service.py
rm app/services/platega_service.py

# Service Layer - Payment Module (7 files)
rm app/services/payment/heleket.py
rm app/services/payment/mulenpay.py
rm app/services/payment/pal24.py
rm app/services/payment/tribute.py
rm app/services/payment/wata.py
rm app/services/payment/platega.py
rm app/services/payment/yookassa.py

# Handler Layer - Balance (7 files)
rm app/handlers/balance/wata.py
rm app/handlers/balance/yookassa.py
rm app/handlers/balance/heleket.py
rm app/handlers/balance/mulenpay.py
rm app/handlers/balance/pal24.py
rm app/handlers/balance/platega.py
rm app/handlers/balance/tribute.py
```

### Step 3: Verify Deletions (5 دقیقه)

```bash
# Check git status
git status
# باید 27 deleted file نشان دهد

# Verify no imports remain (should return NOTHING)
rg "from app.external.yookassa_webhook" app/
rg "from app.services.wata_service" app/
rg "from app.services.payment.heleket" app/
rg "from app.handlers.balance.yookassa" app/

# If any results found:
# - این فایل‌ها contaminated هستند (فاز 2)
# - برای الان فقط note کنید، حذف نکنید
```

### Step 4: Test Application (10 دقیقه)

```bash
# Try to start application
python main.py

# Expected:
# - اگر import errors نداشت: ✅ عالی
# - اگر import error داشت: فایل contaminated پیدا شد
#   → در PR mention کنید
#   → ما در فاز 2 fix می‌کنیم

# Run tests (if exist)
pytest tests/ -v

# Expected:
# - Tests pass: ✅ عالی
# - Some tests fail: اگر مربوط به Russian gateways است، skip کنید:
#   → Add @pytest.mark.skip(reason="Russian gateway removed")
```

### Step 5: Commit & Push (5 دقیقه)

```bash
# Stage changes
git add -A

# Commit با message مناسب
git commit -m "cleanup: Remove Russian payment gateway files (27 files)

- Delete 7 external gateway webhook files
- Delete 6 individual gateway service files
- Delete 7 payment module gateway files
- Delete 7 balance handler gateway files

Total: 27 files, ~3,000 lines removed

Details:
- External: yookassa, wata, pal24, heleket, tribute
- Services: Individual service files for each gateway
- Services/payment: Module files for each gateway
- Handlers/balance: Balance handlers for each gateway

Related: Story #001 - Russian Gateway Cleanup Phase 1
Environment: dev/staging (no production data impact)
Part of: Multi-tenant SaaS migration

Technical Notes:
- No data loss risk (dev/staging environment)
- These gateways serve Russian market only
- Replacing with Iranian gateways (ZarinPal, Card-to-Card)
- Phase 2 will clean contaminated core files
- Phase 3 will drop database tables
"

# Push to remote
git push origin cleanup/russian-gateways-phase1
```

### Step 6: Create Pull Request (5 دقیقه)

**PR Title:**
```
[Cleanup] Remove Russian payment gateway files - Phase 1 (27 files)
```

**PR Description:**
```markdown
## Summary
حذف 27 فایل مربوط به درگاه‌های پرداخت روسی که دیگر نیاز نیستند.

## Changes
- ❌ Deleted 7 external gateway files (webhooks)
- ❌ Deleted 6 individual gateway services
- ❌ Deleted 7 payment module gateway files
- ❌ Deleted 7 balance handler gateway files

**Total:** 27 files, ~3,000 lines removed

## Context
بخشی از migration به multi-tenant SaaS ایرانی. این درگاه‌ها فقط برای بازار روسیه بودند:
- YooKassa
- Heleket
- Tribute
- MulenPay
- Pal24
- Platega
- WATA

جایگزین‌ها:
- ✅ ZarinPal (Iranian)
- ✅ کارت به کارت (Iranian)
- ✅ Wallet

## Testing
- [ ] Application starts without errors
- [ ] No import errors found
- [ ] Existing tests pass (or skipped if gateway-specific)

## Next Steps
- Phase 2: Clean contaminated core files (23 files)
- Phase 3: Drop database tables (7 tables)

## Related
- Story: #001
- Plan: `_bmad-output/project-planning-artifacts/russian-artifacts-removal-plan.md`
```

---

## 🐛 مشکلات احتمالی و راه حل

### Problem 1: Import Errors After Deletion

**Error:**
```
ImportError: cannot import name 'YooKassaService' from 'app.services.yookassa_service'
```

**Solution:**
این فایل contaminated است (فاز 2). برای الان:
1. فایلی که error می‌دهد را پیدا کنید
2. خط import را comment کنید یا حذف کنید
3. در PR mention کنید: "Found contaminated file: X"

### Problem 2: Tests Failing

**Error:**
```
test_yookassa_payment_flow ... FAILED
```

**Solution:**
اگر test مربوط به Russian gateway است:
```python
@pytest.mark.skip(reason="Russian gateway removed - Story #001")
def test_yookassa_payment_flow():
    # ...
```

### Problem 3: Git Conflicts

**Solution:**
```bash
git fetch origin
git rebase origin/dev5-from-upstream
# Resolve conflicts (فایل‌هایی که حذف کردید، delete را accept کنید)
```

---

## ⏱️ تخمین زمان

| مرحله | زمان تخمینی |
|-------|-------------|
| Setup + Read docs | 15 دقیقه |
| Delete files | 10 دقیقه |
| Verify + Test | 15 دقیقه |
| Commit + Push | 5 دقیقه |
| Create PR | 5 دقیقه |
| **Total** | **50 دقیقه** |

**Story Points: 2** (نیم روز کاری با احتساب مستندسازی)

---

## 📚 منابع اضافی

### Documentation
- Implementation Readiness Report: `_bmad-output/project-planning-artifacts/implementation-readiness-report-2025-12-26.md`
- Russian Artifacts Removal Plan: `_bmad-output/project-planning-artifacts/russian-artifacts-removal-plan.md`

### Commands Cheat Sheet

```bash
# Verify deletions
git status | grep deleted | wc -l  # Should show 27

# Check no imports remain
rg -i "yookassa|heleket|tribute|mulenpay|pal24|platega|wata" app/ \
  --type py | grep -v ".pyc" | grep import

# Test application
python main.py  # Should start without errors

# Run specific test
pytest tests/test_payments.py -v
```

---

## ✅ Definition of Done

این Story زمانی Done است که:

1. ✅ 27 فایل حذف شده باشند
2. ✅ Git commit ایجاد شده باشد
3. ✅ Application بدون import error start شود
4. ✅ Tests pass یا به درستی skip شوند
5. ✅ Pull Request ایجاد شده باشد
6. ✅ PR حداقل 1 review داشته باشد
7. ✅ Merge شده باشد به branch اصلی

---

## 🔄 Next Story (Preview)

**Story #002:** Surgical Removal from Contaminated Core Files
- Modify 11 service files
- Modify 16 handler files
- Remove Russian gateway references
- Update payment method selection UI

**Estimated:** 5 Story Points (2-3 روز)

---

## 💬 سوالات؟

اگر هر سوالی داشتید:
1. فایل `cleanup-execution-guide.md` را دوباره بخوانید
2. به PM مراجعه کنید (@K4lantar4)
3. در PR سوال بپرسید

---

**Story Created:** 2025-12-26
**Created By:** Product Manager (K4lantar4)
**Part of:** remnabot Multi-Tenant SaaS Transformation
**Epic:** Russian Gateway Cleanup (3 weeks, 3 phases)

---

*این Story بخشی از یک برنامه 4-هفته‌ای برای آماده‌سازی codebase قبل از Epic creation است.*

