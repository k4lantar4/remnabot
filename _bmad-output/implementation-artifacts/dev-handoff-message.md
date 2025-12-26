# پیام برای Developer

سلام! 👋

یک Story برات آماده کردم که باید 27 فایل مربوط به درگاه‌های پرداخت روسی رو حذف کنی.

---

## 📦 فایل‌هایی که باید بخونی (به ترتیب اولویت):

### 1️⃣ Story اصلی (شروع از اینجا):
```
_bmad-output/implementation-artifacts/story-001-cleanup-russian-gateways-phase1.md
```

این فایل شامل:
- ✅ Acceptance Criteria واضح
- ✅ مراحل Step-by-step
- ✅ دستورات دقیق bash
- ✅ راهنمای troubleshooting
- ✅ تخمین زمان: 50 دقیقه

### 2️⃣ راهنمای اجرای تکمیلی:
```
_bmad-output/project-planning-artifacts/cleanup-execution-guide.md
```

این فایل شامل:
- ✅ Checklist کامل 27 فایل
- ✅ دستورات verification
- ✅ نمونه‌های کد

### 3️⃣ Context کامل (اختیاری):
```
_bmad-output/project-planning-artifacts/russian-artifacts-removal-plan.md
```

برای فهمیدن چرا این کار رو می‌کنیم و برنامه کلی.

---

## 🚀 Quick Start (اگر عجله داری):

```bash
# 1. Create branch
cd /path/to/remnabot
git checkout -b cleanup/russian-gateways-phase1

# 2. باز کن این فایل و دنبال کن:
_bmad-output/implementation-artifacts/story-001-cleanup-russian-gateways-phase1.md
# → بخش "Step 2: Delete Files" رو copy-paste کن

# 3. Verify
git status  # باید 27 deleted file نشون بده

# 4. Commit & Push
git add -A
git commit -m "cleanup: Remove Russian payment gateway files (27 files)"
git push origin cleanup/russian-gateways-phase1

# 5. Create PR
# (جزئیات در Story)
```

---

## ⏱️ زمان تخمینی:

- **خواندن Story + راهنما:** 15 دقیقه
- **حذف فایل‌ها + Test:** 25 دقیقه
- **Commit + PR:** 10 دقیقه
- **جمع:** حدود 1 ساعت

---

## 🎯 هدف:

حذف 27 فایل از 4 layer:
- 7 external files
- 13 service files
- 7 handler files

این فایل‌ها مربوط به درگاه‌های پرداخت روسی هستند که دیگر نیازی نیست:
YooKassa, Heleket, Tribute, MulenPay, Pal24, Platega, WATA

---

## ⚠️ مهم:

1. **محیط:** dev/staging (داده production نیست، نگران نباش)
2. **ریسک:** پایین (فایل‌های isolated هستند)
3. **اگر error دیدی:** در PR mention کن، فاز 2 fix می‌کنیم

---

## 📞 سوال داری؟

- Story رو کامل بخون: `story-001-cleanup-russian-gateways-phase1.md`
- یا به من پیام بده: @K4lantar4

---

موفق باشی! 🚀

این فقط فاز 1 از یک برنامه 3-فاز است. بعد از این، فاز 2 و 3 هم خواهیم داشت.

