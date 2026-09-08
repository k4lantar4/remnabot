# Handoff: به‌روزرسانی پلن cutover (قبل از شروع توسعه)

> **HISTORICAL — 2026-08-31.** Plan update executed. **`docs/superpowers/plans/2026-08-28-production-cutover-mvp.md` is the sole authority.** Do not treat this handoff as the current mission. Remaining M0 is checkpointed; next gate is user «شروع M1».

Date: 2026-08-31  
Audience: دستیار/عامل جدید  
Branch: `prod-cutover` @ `/opt/remnabot1`

---

## ماموریت (فقط این)

**یک سند پلن واحد و قابل اجرا** بسازید — نه اجرای M0+، نه cutover، نه restore، نه DNS.

| انجام دهید | انجام ندهید |
|---|---|
| راستی‌آزمایی live/disk/git | `docker compose up` روی prod یا legacy volumes |
| ادغام حقایق binding در پلن MVP | Alembic graft (M4-T0) |
| حذف ارجاعات به فایل‌های حذف‌شده | شروع M1+ بدون تایید کاربر |
| علامت‌گذاری کارهای M0 انجام‌شده vs باقی‌مانده | بازنویسی spec 747 خطی Architecture A |

**خروجی مورد انتظار:** `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md` به‌روز، self-contained، بدون وابستگی به spec/errata حذف‌شده.

**Skill پیشنهادی:** `superpowers:writing-plans` — فقط برای **ویرایش پلن**، نه implementation.

---

## فایل‌های حذف‌شده (۴ فایل اضافی)

این فایل‌ها فقط برای رسیدن به پلن صحیح نوشته شده بودند. محتوای binding آن‌ها باید **داخل پلن MVP** ادغام شود.

| فایل حذف‌شده | نقش قبلی |
|---|---|
| `specs/2026-08-28-production-cutover-architecture-design.md` | Architecture A — DNS/Telegram/C2C/rollback/gates (بخش‌هایی منسوخ) |
| `specs/2026-08-28-production-cutover-architecture-errata.md` | تصحیح topology/Alembic نسبت به Architecture A |
| `specs/2026-08-29-governance-topology-audit-design.md` | governance audit + six identities |
| `plans/2026-08-28-production-cutover-mvp-errata.md` | patchهای verified drift (E1–E7) |

**نگه دارید (حذف نشده):**

| فایل | نقش |
|---|---|
| `plans/2026-08-28-production-cutover-mvp.md` | **تنها پلن** — هدف به‌روزرسانی |
| `evidence/2026-08-29-git-topology.md` | snapshot git (re-verify) |
| `evidence/2026-08-29-host-inventory-{rc,prod}.md` | snapshot host (re-verify) |
| `.cursor/rules/10-remnabot-migration.mdc` | governance machine-readable |

Architecture A خام همچنان روی remote `k4lantar4/remnabot` `origin/chore/mcp-dev-tools` @ `70476c0e` موجود است — **فقط مرجع DNS/Telegram/C2C/rollback**؛ Alembic/cabinet path از آن پیروی نکنید.

---

## راستی‌آزمایی — 2026-08-31 (VERIFIED)

### Git / branch

| Item | Value | Class |
|---|---|---|
| Branch فعال | `prod-cutover` @ `a168a817` | VERIFIED |
| Commit governance | `docs: governance topology audit and pre-M0 artifacts` | VERIFIED |
| `main` | `89fa7dc5`, **behind upstream 1** | VERIFIED |
| Working tree | `M docker-compose.yml`, `?? locales/` | VERIFIED |
| Alembic graft | **نشده** — هنوز upstream `0088–0110` روی disk | VERIFIED |

### توپولوژی (six identities — binding)

| # | Identity | Path / remote |
|---|---|---|
| 1 | Production reference | `/opt/remnabot` · `k4lantar4/remnabot` · 3.60.0 · READ-ONLY |
| 2 | Maintained bot | `/opt/remnabot1` · `k4lantar4/remnabot1` · 4.2.0 |
| 3 | Upstream bot | `BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot` |
| 4 | Upstream working tree | `/opt/bot` · READ-ONLY |
| 5 | RC runtime | `bot-v4` / `91.107.144.95` |
| 6 | Production runtime | `Bot` / `91.107.249.43` · live **`/opt/bot-remnawave`** |

**Cabinet:** `/opt/cabinet` · `k4lantar4/cabinet` — هرگز merge به remnabot1.

**رد شده:** `cabinet1`, `/opt/cabinet1`, `remnabot1 origin = remnabot`.

### Dumps (rehearsal input — NOT cutover artifacts)

| File | SHA-256 | Notes |
|---|---|---|
| `/opt/remnabot/old_3.60_remnawave_bot.sql` | `b5fc023a23e99471ab9a4a61f834989ff7ff21c7f6061af4f926e404c093cb85` | alembic `0103`; 11M |
| `/opt/remnawave/old(2.8.1)_remnawave.sql` | `11935de69fc6dc318419753916ff840f950f5b4be7a27be46e2ccf2142347377` | RW 2.8.1 |

### Artifacts هنوز موجود نیست (پلن درست است)

- `docker-compose.rehearsal.yml` — absent
- `deploy/caddy/` — absent
- `rehearsal_*` / `cutover_*` volumes — absent
- M4 Alembic graft — absent

### Production (از evidence 2026-08-29 — re-verify با `ssh bot`)

| Item | Value |
|---|---|
| Bot image | `bot-remnawave-bot` 3.60 |
| Bot PG | `postgres:15-alpine` (نه `15.18`) |
| RW | `backend:2.8.1`, PG 17.6, sub page 7.2.6 |
| C2C | enabled |
| Path | `/opt/bot-remnawave` |

### RC dev sandbox (non-promotable)

| Item | Value |
|---|---|
| RW | `backend:3` (3.3.2), PG 18.4, sub `:latest` |
| Volume | `remnawave-db-data` — **forbidden** for restore |

---

## drift پلن فعلی (باید در به‌روزرسانی اصلاح شود)

پلن MVP هنوز ادعاهای زیر را دارد که با disk **ناسازگار** یا **منسوخ** است:

| محل تقریبی در پلن | ادعای stale | واقعیت 2026-08-31 |
|---|---|---|
| «No task executed» / untracked docs | هیچ کاری انجام نشده | commit `a168a817` governance + evidence + rule |
| M0-T7 recover spec + errata | باید spec/errata کپی شود | **فایل‌ها حذف شدند** — محتوا را inline در پلن |
| ارجاع به `+ errata sibling` | errata جدا | حذف؛ یک پلن self-contained |
| ارجاع به governance audit spec | spec جدا | حذف؛ six identities در پلن |
| M0-T0 rule «does not exist» | rule نبود | **`10-remnabot-migration.mdc` committed** — M0-T0 partial PASS |
| Evidence tasks M0-T1,T4,T5 | باید ساخته شوند | **3 evidence file موجود** — re-verify و تاریخ به‌روز |
| P6 satisfied | dump موجود | **هنوز valid** (SHA بالا) |

---

## محتوای binding برای ادغام در پلن (از فایل‌های حذف‌شده)

### 1. Topology inversion (اجباری)

| منسوخ (Architecture A بدون errata) | جایگزین binding |
|---|---|
| `/opt/cabinet1` | `/opt/cabinet` |
| remnabot1 = custom 3.60 tree | remnabot1 = **4.2 fork**؛ custom از `/opt/remnabot` **graft** |
| «do not copy 0088–0110» | archive remnabot1 `0088–0110` + copy remnabot `0088–0104` |
| prod `0103` = remnabot1 `0103` file | prod `0103` = **remnabot-lineage** `subscription_user_disabled` |
| Pin Remnawave 3.3.2 | **candidate** — promote فقط digest verified بعد G3 |
| Dump name `old(3.60)_…` | `/opt/remnabot/old_3.60_remnawave_bot.sql` |
| Prod path implied `/opt/remnabot` | live prod = **`/opt/bot-remnawave`** on Bot |

### 2. Alembic (authority = پلن)

- Last shared revision: **`0087`**
- From `0088`: same IDs, **different semantics** (remnabot `0088` = C2C; remnabot1 `0088` = dedupe)
- Production DB: remnabot-lineage **`0103`**
- remnabot1 disk: upstream **`0110`** — **never** upgrade onto restored prod DB
- **Graft:** archive `0088–0110` → copy remnabot `0088–0104` → `0111+` from remnabot `0104`
- **Hazards:** `run_alembic_upgrade()` in `main.py`; leftover `0105–0110`; `0001` create_all; no app until M4-T0 PASS
- **Fallback:** graft fail → `PLAN REVISION REQUIRED: Alembic graft failed M4-T0` (re-ID from `0103`)

### 3. Remnawave two-track

| Track | Config | Promotable? |
|---|---|---|
| Rehearsal-restore | `backend:2.8.1` digest, PG **17.6**, sub **7.2.6** | Yes after G3 |
| RC dev sandbox | `backend:3`, PG 18.4, `:latest` | **No** |

PG 17→18 = track جدا (E2)؛ با 2.8→3.x در یک window ترکیب نشود.

### 4. Bot PostgreSQL

- Plan pin `15.18` = aspirational
- Production = **`postgres:15-alpine`**
- Rehearsal: همان digest prod **یا** prove 15.18 compatibility

### 5. Volume forbidden rule

**Rule:** restore/rehearsal فقط روی `rehearsal_*` / `cutover_*`.

**RC (verified):** `remnawave-db-data` forbidden.

**Bot (verified):** `bot-remnawave_postgres_data`, `bot-remnawave_*`, `remnawave-db-data`, admin/staging volumes — forbidden.

### 6. Cutover safety (از Architecture A — retain in plan)

- DNS-only Cloudflare A → `91.107.144.95`, TTL 300, no AAAA, no Floating IP
- Writer freeze before dump
- Pre-DNS verify before flip
- Single production bot after old bot stopped
- Rollback = DNS back + frozen 3.60/2.8.1 — never downgrade 3.x DB in place
- Gates G1–G13; G8 C2C hard = NO-GO if INCOMPLETE

### 7. Plan errata E1–E7 (inline کنید)

- **E1:** volume lists host-specific
- **E2:** prod path `/opt/bot-remnawave`; RC lacks it
- **E3:** postgres 15-alpine vs 15.18
- **E4:** two-track Remnawave
- **E5:** prod Caddy already has some `staging-host-*` — M1-T4 must not duplicate if DNS points Bot
- **E6:** governance artifacts partially committed (rule + evidence)
- **E7:** Alembic fallback trigger

---

## چک‌لیست re-verify قبل از ویرایش پلن

دستیار جدید **باید** این‌ها را دوباره روی disk/runtime ببیند و در پلن تاریخ + SHA ثبت کند:

```bash
# Git topology (هر tree)
git -C /opt/remnabot1 branch -v && git -C /opt/remnabot1 status --short
git -C /opt/cabinet log -1 --oneline && git -C /opt/remnabot log -1 --oneline
git -C /opt/bot log -1 --oneline

# Dump checksums
sha256sum /opt/remnabot/old_3.60_remnawave_bot.sql
sha256sum /opt/remnawave/old\(2.8.1\)_remnawave.sql

# Alembic collision sanity
ls /opt/remnabot1/migrations/alembic/versions/010*.py
# انتظار: 0104_remnawave_numeric_id.py (upstream) — graft نشده

# RC volumes / compose absence
docker volume ls | grep -E 'rehearsal|cutover|remnawave-db-data'
test -f /opt/remnabot1/docker-compose.rehearsal.yml && echo exists || echo absent

# Production (read-only)
ssh bot 'docker ps --format "{{.Names}} {{.Image}}" | head -20'
ssh bot 'test -d /opt/bot-remnawave && echo prod path ok'
```

اگر نتیجه با جدول «راستی‌آزمایی» بالا **متناقض** بود → `PLAN REVISION REQUIRED: <reason>` در پلن بنویسید؛ حدس نزنید.

---

## workflow پیشنهادی به‌روزرسانی پلن

### Phase A — Discovery (read-only)

1. بخوانید: این handoff → پلن MVP → evidence → `.cursor/rules/10-remnabot-migration.mdc`
2. چک‌لیست re-verify را اجرا کنید
3. لیست drift (جدول بالا + هر مورد جدید) را تکمیل کنید

### Phase B — Plan edit (یک فایل)

1. **یک پلن self-contained** — بخش «Locked errata» و «Six identities» را نگه دارید ولی ارجاع به فایل حذف‌شده را حذف کنید
2. **M0 را بازنویسی کنید:**
   - M0-T0 rule: **DONE** (committed) — re-verify only
   - M0-T1/T4 evidence: **DONE** (committed) — append re-verify date
   - M0-T7 recover spec: **CANCEL** — جایگزین: «Architecture A facts inlined §Cutover safety»
   - M0-T2,T3,T5,T6: وضعیت واقعی را علامت بزنید
3. **Prerequisites:** P6 PASS؛ P1/P2/P3 still UNKNOWN until human confirms
4. **Header:** «Plan updated YYYY-MM-DD; no M1+ execution until user approves»
5. حذف «Do not execute M0» اگر M0 partial complete — جایگزین: «Do not execute M1+ until user approves updated plan»

### Phase C — Self-review (قبل از تحویل)

- [ ] هیچ path به `specs/2026-08-*` یا `*-errata.md` حذف‌شده نیست
- [ ] Alembic graft + forbidden actions + two-track RW در یک جا هست
- [ ] M0 task status با git/disk match می‌کند
- [ ] «No task executed» حذف یا اصلاح شده
- [ ] User gate صریح: تایید پلن → سپس M1

---

## معیار «پلن آماده توسعه»

پلن آماده است وقتی:

1. **Self-contained** — فقط MVP plan + evidence + rule کافی است
2. **Verified** — SHA/HEAD/date در evidence یا پلن به‌روز است
3. **M0 status honest** — done / partial / pending per task
4. **M1+ blocked** تا کاربر صریحاً «شروع M1» بگوید
5. **No internal contradiction** — cabinet path, Alembic, prod path, postgres pin

---

## پیش‌نیازهای انسانی (پلن نباید حدس بزند)

| ID | Item | Status |
|---|---|---|
| P1 | Isolated C2C test admin chat | UNKNOWN — از کاربر بپرسید |
| P2 | Cloudflare DNS write access | UNKNOWN |
| P3 | Cloudflare token DNS-01 (optional) | UNKNOWN |
| P6 | Bot rehearsal dump | **SATISFIED** (SHA verified 2026-08-31) |

---

## یادداشت برای کاربر نهایی

بعد از به‌روزرسانی پلن توسط دستیار جدید:

1. پلن MVP را بخوانید
2. اگر درست است: «M1 را شروع کن»
3. اگر نه: بخش مشخص + دلیل

**این handoff خودش پلن نیست** — نقشه راه برای **یک** دستیار که پلن را اصلاح کند.
