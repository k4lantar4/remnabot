# 📚 فهرست مستندات Multi-Tenant

**آخرین به‌روزرسانی:** 2025-12-15

---

## 🎯 شروع از اینجا

### ⭐ Master Document
**[MASTER-IMPLEMENTATION-GUIDE.md](./MASTER-IMPLEMENTATION-GUIDE.md)**  
**این اولین فایلی است که باید بخوانید!**

این فایل شامل:
- ✅ وضعیت فعلی پیاده‌سازی
- ✅ برنامه کامل مرحله‌به‌مرحله
- ✅ چک‌لیست پیشرفت
- ✅ قوانین طلایی

---

## 📖 مستندات اصلی

### 1. راهنمای پیاده‌سازی
- **[MASTER-IMPLEMENTATION-GUIDE.md](./MASTER-IMPLEMENTATION-GUIDE.md)** ⭐⭐⭐
  - راهنمای اصلی - شروع از اینجا

- **[implementation-guide-step-by-step.md](./implementation-guide-step-by-step.md)** ⭐⭐
  - راهنمای جزئی مرحله‌به‌مرحله

### 2. تحلیل و طراحی
- **[analysis/redundancy-analysis-and-refactoring-plan.md](./analysis/redundancy-analysis-and-refactoring-plan.md)** ⭐⭐
  - تحلیل مشکل redundancy
  - برنامه refactoring

- **[analysis/comprehensive-code-review.md](./analysis/comprehensive-code-review.md)** ⭐
  - بررسی جامع کد
  - مشکلات و راهکارها

### 3. مرجع طراحی
- **[tenant-configs-categorization.md](./tenant-configs-categorization.md)** ⭐
  - دسته‌بندی کامل configs
  - MASTER_ONLY vs TENANT_CONFIGURABLE

- **[tenant-bots-callback-handler-mapping.md](./tenant-bots-callback-handler-mapping.md)** ⭐
  - Mapping کامل callbacks → handlers → database

- **[tenant-bots-admin-ux-design.md](./tenant-bots-admin-ux-design.md)** ⭐
  - طراحی UX برای Admin Panel

- **[analysis/billing-model-design.md](./analysis/billing-model-design.md)** ⭐
  - طراحی مدل Billing

---

## 📋 راهنمای مطالعه

### برای شروع پیاده‌سازی:
1. **[MASTER-IMPLEMENTATION-GUIDE.md](./MASTER-IMPLEMENTATION-GUIDE.md)** ⭐
2. **[analysis/redundancy-analysis-and-refactoring-plan.md](./analysis/redundancy-analysis-and-refactoring-plan.md)**
3. **[implementation-guide-step-by-step.md](./implementation-guide-step-by-step.md)**

### برای درک طراحی:
1. **[tenant-configs-categorization.md](./tenant-configs-categorization.md)**
2. **[tenant-bots-admin-ux-design.md](./tenant-bots-admin-ux-design.md)**
3. **[tenant-bots-callback-handler-mapping.md](./tenant-bots-callback-handler-mapping.md)**

### برای بررسی مشکلات:
1. **[analysis/comprehensive-code-review.md](./analysis/comprehensive-code-review.md)**
2. **[analysis/redundancy-analysis-and-refactoring-plan.md](./analysis/redundancy-analysis-and-refactoring-plan.md)**

---

## 🗑️ مستندات قدیمی (نادیده بگیرید)

این مستندات قدیمی هستند و نباید استفاده شوند:
- ❌ `multi-tenant-design-document.md`
- ❌ `multi-tenant-migration-plan.md`
- ❌ `multi-tenant/` folder (بسیاری از فایل‌ها)

برای لیست کامل، به **[DOCUMENTATION-CLEANUP-GUIDE.md](./DOCUMENTATION-CLEANUP-GUIDE.md)** مراجعه کنید.

---

## 🔗 لینک‌های سریع

### شروع کار:
- [MASTER-IMPLEMENTATION-GUIDE.md](./MASTER-IMPLEMENTATION-GUIDE.md) ⭐

### مشکلات:
- [comprehensive-code-review.md](./analysis/comprehensive-code-review.md)
- [redundancy-analysis-and-refactoring-plan.md](./analysis/redundancy-analysis-and-refactoring-plan.md)

### مرجع:
- [tenant-configs-categorization.md](./tenant-configs-categorization.md)
- [tenant-bots-callback-handler-mapping.md](./tenant-bots-callback-handler-mapping.md)

---

**نکته:** اگر گیج شدید، فقط **[MASTER-IMPLEMENTATION-GUIDE.md](./MASTER-IMPLEMENTATION-GUIDE.md)** را بخوانید!

