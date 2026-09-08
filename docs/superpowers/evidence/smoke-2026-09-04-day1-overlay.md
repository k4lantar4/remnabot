# Day-1 overlay — operator smoke checklist

**Date:** 2026-09-04  
**Scope:** Part A Telegram overlay + Part B cabinet Layer A (no M7, no Buy-button redesign)  
**STOP:** do not start M7 from this smoke.

## Runtime readiness (agent-verified)

| Component | Identity | Status |
|---|---|---|
| Bot image HEAD | remnabot1 `e716cb83` | — |
| Cabinet HEAD | cabinet `0173edae` | — |
| Telegram RC | `@mrj7_bot` (test token; polling) | `rehearsal_bot` **healthy** |
| Cabinet RC | `https://panel.rookari.com` | `cabinet_frontend` **healthy**, HTTP **200** |
| Multi-tariff env (live container) | `SALES_MODE=tariffs`, `MULTI_TARIFF_ENABLED=true`, `MAX_ACTIVE=5000` | ON |
| Rich menu | `MAIN_MENU_RICH_ENABLED=true`, `MENU_LAYOUT_ENABLED=true` | ON |

Note: background Lava/Platega cancel warnings on boot are deferred-provider noise — out of day-1 scope. Do not use production bot token or production C2C admin chat.

---

## A — Telegram (`@mrj7_bot`)

### A1 — `/start` shell (4.2 chrome)

| Step | Path | Expect |
|---|---|---|
| 1 | Send `/start` | Rich 4.2 shell: Connect / Subscription / Balance — **not** the 3.60 grid |
| 2 | Read chrome | Persian labels; balance in تومان |
| 3 | Subscription preview date (if shown) | Jalali for fa (e.g. `18.04.1405` style), Latin digits |

**Known (observe only — no fix this round):** while an active subscription exists, **Buy is hidden on `/start`** (upstream rule). Second purchase entry is under My Subscriptions (A3).

### A2 — My Subscriptions list

| Step | Path | Expect |
|---|---|---|
| 1 | Tap Subscription → open list | Title Persian with page/total if paginated |
| 2 | Read a line | ترافیک / تعداد کاربر / Jalali until-date — no Cyrillic list chrome |
| 3 | Gift row | Gift button still present |
| 4 | Partner identity (if account has brand+serial) | e.g. `Moonvpn_67258` style |

### A3 — Search

| Step | Path | Expect |
|---|---|---|
| 1 | Tap search | Prompt for name / serial / note |
| 2 | Send a query that matches one sub | Confirmation + **filtered list re-rendered** |
| 3 | Reset search | Full list again |

### A4 — Pause

| Step | Path | Expect |
|---|---|---|
| 1 | Open an **active non-critical** test sub detail | Pause button visible if `user_disabled` mapped |
| 2 | Confirm → pause | Confirm screen then detail with «متوقف» + enable; no crash |
| 3 | Back to list | Paused sub stays in **active-tier order** (not last pages); searchable without needing search to find it |

### A5 — Second purchase / multi-tariff (observe)

| Step | Path | Expect |
|---|---|---|
| 1 | From My Subscriptions tap **➕ Buy** (or buy-another) | Tariff list opens |
| 2 | Tap a tariff you **already** have active | Alert: `TARIFF_PURCHASE_ALREADY_ACTIVE` — renew via My Subscriptions (this means multi is ON) |
| 3 | Tap a **different** tariff (if available) | Period/confirm flow continues (do not need to complete paid purchase for PASS) |

Do not require completing a paid charge for smoke PASS.

### A6 — Partner confirm (optional)

Isolated partner test account only. Confirm shows note/brand extras. Skip if none. Never use production C2C admin chat.

---

## B — Cabinet (`https://panel.rookari.com`)

Use a private/incognito window so `cabinet_language` is unset.

| Step | Path | Expect |
|---|---|---|
| B1 | Open panel (no prior localStorage lang) | First paint fa + RTL (not Russian) |
| B2 | Login with test Telegram → اشتراک من | End date Jalali + Latin digits |
| B3 | Traffic amount | LTR isolate (e.g. `0 MB / 10.0 GB` readable left-to-right) |
| B4 | Config URL field (if shown) | Starts with `https://` (url-ltr) |
| B5 | Connect / دریافت کانفیگ | QR + copy sheet; no user-path «دستگاه» (تعداد کاربر / اتصال OK) |

---

## Out of scope this smoke

- Adding Buy to `/start` when a sub is already active  
- Allowing a second purchase of the **same** tariff_id  
- M7-T1 / DNS / production token / Layer C (`/sales`)  
- Fixing deferred Lava/Platega cancel warnings  

---

## Operator results (2026-09-04)

| ID | Result | Notes |
|---|---|---|
| A1.1–A1.3 | PASS | |
| A2.1–A2.4 | PASS | |
| A3.1–A3.3 | PASS | |
| A4.1 | PASS | Pause button visible |
| A4.2 | PASS | After `57b44073` + `53a9a39f`: confirm → pause → detail/`sm:` OK |
| A4.3 | PASS | After `e716cb83`: paused sub stays with active-tier list order (operator `تایید` 2026-09-04) |
| A5.1–A5.2 | PASS | |
| A5.3 | PASS | Different tariff flow |
| A6 | SKIP | |
| B1–B5 | PASS | |

**Day-1 overlay smoke:** **PASS** (operator `تایید` 2026-09-04 after A4.2 + list-order fixes).  
**Do not start M7** from this result. Next cutover pointer remains MVP plan **M7-T1** (named-start only).

## Sign-off

Operator: (reported in chat 2026-09-04)  
Result: **PASS**  
Date: 2026-09-04  
Bot HEAD at sign-off: `e716cb83`  
Cabinet HEAD: `0173edae`
