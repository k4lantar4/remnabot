# Selective upstream patches onto `prod-cutover` (remnabot)

**Date:** 2026-09-09
**Status:** live plan — not started
**Repo:** `remnabot` (`origin` = `k4lantar4/remnabot.git`, `upstream` = `BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot`)
**Target branch:** **`main`** — not `prod-cutover`. Per `remnabot/CLAUDE.md`, `prod-cutover` was
merged into `main` on 2026-09-08 (PR #2) and `main` is the production line now. Branch every task
here off `main`. See "Branch reality" below for the two commits that have not landed there yet.
**Upstream basis:** re-verified against **v4.8.0** (`1fe2b47a`, 2026-09-09). Originally drafted
against v4.7.1; see "Upstream moved" below — Plan A tasks 1-2 were rewritten as a result.

> Before starting **any** task here, re-run the upstream-freshness preflight in the
> `plan-execution` skill. Upstream shipped 44 commits in one day between v4.7.1 and v4.8.0 and
> reversed one of its own fixes in the process. A plan basis goes stale in days, not weeks.

Replaces the abandoned all-at-once `git merge upstream/main` (branch
`worktree-agent-a9deadb5da0928e72`, 424 files, 155 commits ahead). That merge was technically
green but mixed merge + BSCHEKER removal + gateway policy + Alembic re-chaining + a bugfix into one
reviewable unit, which is not maintainable. This plan takes only the fixes that are genuinely
broken *in our fork*, as small independently-reviewable commits.

`remnabot` is ~190 commits behind `upstream/main` (v4.8.0). We are NOT catching up — per workspace
`CLAUDE.md` we do not auto-merge upstream. The gap growing is expected and is not a reason to
revisit the merge decision.

---

## Verification notes (established 2026-09-09 — do not re-derive)

Every candidate below was checked against `prod-cutover` itself, not taken on trust from the
candidate table.

- **No candidate carries a migration.** All 11 upstream commits considered touch zero files under
  `migrations/`. The known Alembic hazard (upstream's `system_error_events` migration also claiming
  `0111` with `down_revision='0110'`, while we never grafted upstream `0105`–`0110` and our `0111`
  is a deliberate graft) is therefore **moot for this plan**. Our head stays
  `migrations/alembic/versions/0111_remnawave_id_and_boot_extras.py`. Re-check this if any patch is
  added to the plan later.
- **`968687ce` IS needed on our side.** The earlier finding ("our wholesale path short-circuits in
  `calculate_user_price`, so no equivalent needed") is correct but too narrow — it only clears the
  wholesale path. The daily-price path in `app/cabinet/routes/subscription_modules/helpers.py`
  never calls `calculate_user_price` at all. Our fork carries the bug verbatim: `helpers.py`
  displays group + promo-offer stacked, while `daily_subscription_service.py` charges group only.
  Displayed price != charged price for B2C users on daily tariffs.
- **`841e2bda` must NOT be cherry-picked.** That commit fixes a `NameError`
  (`dataclasses.asdict` vs `asdict`) that exists *only on the abandoned merge branch*, introduced by
  its own conflict resolution. `prod-cutover:app/services/pricing_engine.py` still has
  `import dataclasses` (line 3) and all three call sites use `dataclasses.asdict` (lines 685, 740,
  895). Cherry-picking it would break working code.
- **`frontend` is already done.** `frontend` `prod-cutover` *is* commit `dc77a7d9` (BSCHEKER removal).
  Nothing to merge. Branch `worktree-agent-af3db50c4f08bf7cb` (`9712d786`) is 0 ahead / 24 behind
  `prod-cutover` — it contains nothing that isn't already there.
- **Test baseline on `prod-cutover`: 20 failed / 7 errors, pre-existing** (documented in
  `remnabot/CLAUDE.md`, verified identical before/after the abandoned merge). Also 23 files fail
  `ruff format --check` (pre-existing formatting debt). Compare every failure against this baseline
  before blaming your own change.

### Branch reality (measured 2026-09-09, after `git fetch origin`)

All code findings below were verified on `prod-cutover`. `origin/main` contains all of it except two
commits, so they hold for `main` too — with one caveat noted.

| Repo | `origin/main` lacks | Local `main` ref |
|---|---|---|
| `remnabot` | 2 commits: `1b594803 fix(currency): balance/combo promo codes and campaigns credited 100x`, `1da3083b chore: remove stale rehearsal/local compose files` | 98 behind `origin/main` — stale ref, just needs `git fetch && git pull --ff-only` |
| `frontend` | 1 commit: `dc77a7d9 Remove BSCHEKER/reachability feature` | 26 behind `origin/main` — same, stale ref only |

**Land those three commits before starting task work**, so every task branches off a `main` that is
actually current. `1b594803` touches `app/services/pricing_engine.py`, which Plan B task 5 also
edits — starting Plan B from a `main` without it means re-resolving that overlap later for no reason.

Both prior merges are already done and merged: `remnabot` PR #2, `frontend` PR #1.

### Upstream moved: v4.7.1 -> v4.8.0 (checked 2026-09-09)

44 commits. Impact on this plan, file by file:

| Plan item | Status against v4.8.0 |
|---|---|
| Plan A tasks 1-2 (`5b24d67a`, `664ecea7`) | **Rewritten.** `app/services/panel_expiry.py` is **deleted** in 4.8.0 and the 4.7.1 rule was found to be wrong — see below |
| Plan A task 3 (`23a58172`+`fdebcad1`) | Unchanged. `app/cabinet/auth/email_auth_gate.py` untouched in 4.8.0 — take as planned |
| Plan B task 4 (`fd9b2ccc`) | `app/services/tariff_switch_policy.py` untouched in 4.8.0 — take as planned |
| Plan B task 5 (`968687ce`) | `helpers.py` untouched. `daily_subscription_service.py` was touched by `564fec3e` — do task 5 **before** task 8 to keep the diffs readable |
| **new: `564fec3e`** | New in 4.8.0, adds `app/services/traffic_reset_policy.py`. **Accepted — added as task 8**, and it is the highest-value item found in this whole review |
| Plan C tasks 6-7 (`aafdb2f2`, `118fe1be`) | Unchanged. `panel_id_is_free_for`, `link_subscription_panel_identity` and `sync_remnawave_user` all still live in `subscription_service.py` in 4.8.0 |
| `6014b92b` (rejected) | 4.8.0 adds `0d04ae62 fix(settings): настройка из кабинета переживает перезапуск` in the same area. **Rejection stands** — same divergence and same "partner == upstream referral" reasoning |

**Why Plan A tasks 1-2 had to be rewritten.** Upstream's `39097eb9` (in 4.8.0) explicitly names the
4.7.1 rule as the cause of a new bug: omitting `expireAt` on update is correct only when the panel
already holds the real, past date. If the panel has drifted and holds a *future* date, silence
leaves a falsely-alive subscription — panel shows active, bot shows expired. The corrected rule,
verified by upstream against the panel contract (identical in 3.0.0 and 3.4.3 — and we run 3.4.3):

- panel `POST` accepts any date including past; panel `PATCH` rejects a past date
  ("Expiration date cannot be in the past");
- future date -> send it, for live *and* blocked subscriptions (access is closed by status, the date
  stays truthful);
- **create** -> send the real date, even a past one (this is what removes "expired a minute ago");
- **update of an expired subscription** -> panel already holds past/unknown: omit the field; panel
  holds future: clamp to the nearest allowed moment, once. After that the panel holds a past date
  and later runs leave it alone, so "expired a minute ago" does not come back every sync.

Implementing the 4.7.1 form would knowingly ship a bug upstream has already diagnosed and fixed.

### Bug presence confirmed in `prod-cutover`

| Patch | Evidence in our fork |
|---|---|
| `23a58172` + `fdebcad1` | `app/cabinet/auth/email_auth_gate.py` does not exist; our `auth.py` enforces the flag on **zero** routes (upstream gates 9); `branding.py:1015` has the same `== 'true'` parse bug; the admin toggle at `branding.py:1034` really does write the DB key |
| `5b24d67a` + `664ecea7` | `max(end_date, now + timedelta(minutes=1))` present at 9 sites across `subscription_service.py`, `monitoring_service.py`, `remnawave_service.py`, `admin_users.py`, `grace_access_runtime.py` |
| `fd9b2ccc` | `.days` truncation in all three switch flows + unconditional `RESET_TRAFFIC_ON_TARIFF_SWITCH` reset |
| `968687ce` | present verbatim (see above) |
| `aafdb2f2` | present |
| `118fe1be` | `referral_reward_service.py:922` still calls `update_remnawave_user`; `sync_remnawave_user` does not exist |
| `6014b92b` | real (`admin_partners.py:137-189` writes `.env`) — but **rejected**, see below |

---

## Accept / reject

**Accept — 8 upstream commits, in this order:**

| # | Patch | Why |
|---|---|---|
| 0 | `564fec3e` (v4.8.0) | **Highest value.** Paying customers get throttled to their limit while paying daily, and LIMITED subscriptions never recover. Do this first — it is the only item actively harming customers who did nothing wrong |
| 1 | `39097eb9` + `7816e1e9` (v4.8.0 rule, superseding `5b24d67a`) | Ongoing, irreversible data loss: every sync destroys the real expiry date in the panel |
| 2 | `664ecea7` | Same bug, grace path. Without it #1 is half-done |
| 3 | `23a58172` + `fdebcad1` | The only genuine security item: our admin toggle looks functional but leaves 8 routes open |
| 4 | `fd9b2ccc` | Direct revenue loss + unlimited traffic via `A -> B -> A` |
| 5 | `968687ce` | Displayed != charged; user-trust and support-load problem |
| 6 | `aafdb2f2` | Admin subscription screen breaks; currently fixed by hand in the DB |
| 7 | `118fe1be` | User left without a working link, but only on the referral-reward path |

**Reject:**

- **`6014b92b`** (partner/ticket settings to DB) — two reasons. (a) Our `admin_partners.py` has
  diverged: we carry an `is_env_locked` / `ENV_OVERRIDE_KEYS` layer upstream does not have in this
  shape, so the patch's 98 deleted lines collide with our code. (b) "partner" in that file means
  upstream's *referral program* (`REFERRAL_REWARD_SCHEME`, `REFERRAL_LEVELS_MODE`), not our B2B
  نماینده / reseller concept. High review cost, ~zero value for our market. If writing to `.env`
  ever becomes a real problem, do it as our own change, not as an upstream patch.
- **`423bbf7d`** (resend verification email) — a new feature, not a fix. The route it adds
  (`/email/register/resend`) does not exist in our fork. Taking it would inflate Task 3's scope.
- **`0b622ba5`** (registration throttle + own disposable-domain list) — genuinely useful anti-abuse,
  but a feature with new config keys, not a fix. **Deferred, not discarded.** Decide after Plan A;
  the decision depends on whether email registration is actually open in our deployment (open
  question below).
- **`841e2bda`** — see verification notes. Would break working code.

**Ordering rationale:** Plans A and C do not touch `pricing_engine.py` / `price_display.py`, so they
do not collide with uncommitted WIP or the `fix/campaign-promocode-toman` branch. Plan B is the only
one that enters pricing code and is deliberately sequenced last.

---

# Plan A — data loss and security

**Goal:** The Remnawave panel stops having the real end-date of expired subscriptions overwritten
with "now + 1 minute", and turning email login off in the cabinet actually closes the API instead of
just hiding the button.

## Vs. upstream

- **Our business logic that must survive untouched:** none of these tasks touch the wholesale /
  `PartnerStatus` path, `pricing_engine.py`, or `price_display.py`. `grace_access_runtime.py` is
  changed only at the date-computation points, not in grace policy itself.
- **Upstream infra reused as-is — do not reimplement:** the expiry rule from
  `app/services/panel_sync/expiry.py` (v4.8.0) and `app/cabinet/auth/email_auth_gate.py`, as is
  `BotConfigurationService.deserialize_value` (already present in our fork).
  **Do not port the whole `app/services/panel_sync/` package.** 4.8.0 refactors seven modules
  (`identity`, `liveness`, `payload`, `projection`, `runner`, `writer`, `expiry`) out of
  `subscription_service.py`; adopting that wholesale is a second big-bang merge, exactly what this
  plan exists to avoid. Take the *rule* from `expiry.py` into a single small module of ours and
  leave our call sites where they are.
- **Deferred features this plan must not re-enable:** no payment gateway is touched. `ParityPay` /
  `TabPay` never enter because we are not merging. `CryptoBot` stays untouched and enabled — it is
  explicitly *not* part of the Russian-gateway cleanup.

## Tasks

**1. Add our own `panel_expiry.py` carrying the v4.8.0 rule, and route all six panel-write points
through it** (rule from `39097eb9` + `7816e1e9`, shape of `5b24d67a`).
Files: `app/services/panel_expiry.py` (new — our module, holding upstream's 4.8.0 *rule*, not
upstream's `panel_sync/` package layout), `app/services/subscription_service.py` (lines 452, 648,
819), `app/services/monitoring_service.py:694`, `app/services/remnawave_service.py:327` (delete the
now-dead `_safe_expire_at_for_panel`), `app/cabinet/routes/admin_users.py` (lines 390, 4280).

Rule to implement (all four branches — do not simplify to the 4.7.1 version):
- future end date -> send it, for live and for blocked/disabled subscriptions alike;
- create -> send the real end date, even if it is in the past (panel `POST` accepts past dates);
- update, expired, panel already holds a past or unknown date -> omit `expireAt` entirely;
- update, expired, panel holds a future date -> clamp once to the nearest allowed moment.

The last branch needs the panel's current value, which arrives in the `PATCH` response — a second
request goes out only on an actual mismatch. Verify that against our `app/external/remnawave_api.py`
client before assuming the response is available at each call site; this is the part most likely to
need adaptation on our side.

**2. Same rule in the grace path** (from `664ecea7`, re-checked against 4.8.0).
Files: `app/services/grace_access_runtime.py` (lines 1676, 1706).
Kept separate from Task 1 because the grace flow has its own test path.

**3. Email-auth gate with the correct parser, as one commit** (`23a58172` + `fdebcad1` squashed —
`fdebcad1` only closes a bug in the file `23a58172` introduces, so splitting them on our fork is
meaningless).
Files: `app/cabinet/auth/email_auth_gate.py` (new), `app/cabinet/routes/auth.py` (8 of upstream's 9
routes — we lack `/email/register/resend`, which belongs to the rejected `423bbf7d`),
`app/cabinet/routes/branding.py` (fix the `== 'true'` parse in `get_email_auth_enabled`, use the
shared key), `app/cabinet/routes/account_linking.py:88`.

## Persian / i18n

- Tasks 1 and 2: no user-visible strings (admin logs only) -> no locale changes.
- **Task 3: yes.** The gate returns `403` with `{'code': 'email_auth_disabled', 'message': ...}` and
  the frontend does not handle that code at all today (`grep email_auth_disabled frontend/src` ->
  zero hits). Required: a new key in **both** `frontend/src/locales/en.json` and
  `frontend/src/locales/fa.json` for "email login is disabled", plus handling the code in the
  cabinet error layer. Write natural, everyday Persian rather than mirroring the English sentence;
  Latin digits (0-9). Per the workspace localization rule, also sanity-check the neighbouring
  existing Persian keys on the login screen that this change touches.

---

# Plan B — tariff-switch abuse and daily price

**Goal:** Daily-tariff customers stop being throttled while paying; on the last day of a
subscription, switching tariffs is no longer free and no longer
resets traffic to unlimited; and the daily price the cabinet shows is exactly the amount charged
each day.

## Vs. upstream

- **Our business logic:** the wholesale path in `pricing_engine.py` (`uses_wholesale_pricing`,
  `apply_wholesale_discount`, `wholesale_discount_bps`) must not change.
  **Note a separate gap of ours, found while verifying:** the daily-price path in `helpers.py` never
  consults wholesale at all, so an approved partner on a daily tariff currently receives the
  group+offer discount instead of their wholesale discount. This plan only **records** that; fixing
  it needs a business decision (see open questions) and is its own plan.
- **Upstream infra reused as-is:** `app/services/tariff_switch_policy.py` and
  `PricingEngine.daily_group_price` — take them verbatim.
- **Currency scale — important:** both tasks operate on **catalog scale** (`daily_price_kopeks`,
  `price_kopeks`) and do not touch `_BALANCE_SCALE_TRANSACTION_TYPES`. Per the default stated in the
  workspace `CLAUDE.md`, the working assumption is **Phase C is out of scope**: do not widen the
  dual-scale, and do not attempt the Toman unification inline. If Phase C should be in scope,
  say so before Plan B starts.

## Tasks

**4. Add `tariff_switch_policy.py` and wire it into all three flows** (from `fd9b2ccc`).
Files: `app/services/tariff_switch_policy.py` (new),
`app/cabinet/routes/subscription_modules/tariff_switch.py` (lines 139, 324, 485, 514),
`app/webapi/routes/miniapp.py` (lines 6570, 6954, 7088, 7185, 7233),
`app/handlers/subscription/tariff_purchase.py`.

> **Highest adaptation risk in this plan.** Our `tariff_purchase.py` has diverged much further than
> upstream's: against the 52 lines upstream touched, we have ~10 `.days` computation sites and 4
> `RESET_TRAFFIC_ON_TARIFF_SWITCH` sites (lines 923, 2674, 3438, 3514, 3554, 3704, 3810, 3911, 3918,
> 4111, 4188, 4206). A clean cherry-pick will not work; adapt by hand. If this outgrows one commit,
> split here: (a) policy file + cabinet/miniapp flows, (b) bot flow.

**5. `daily_group_price` as the single source of daily price** (from `968687ce`).
Files: `app/services/pricing_engine.py` (add `daily_group_price`),
`app/cabinet/routes/subscription_modules/helpers.py` (lines 171-183 — drop the `_offer_pct`
stacking), `app/cabinet/routes/subscription_modules/purchase.py`,
`app/services/daily_subscription_service.py` (lines 152-159).

**8. Daily charge actually resets the traffic counter, and LIMITED subscriptions recover**
(from `564fec3e`, new in v4.8.0).
Files: `app/services/traffic_reset_policy.py` (new), `app/services/daily_subscription_service.py`
(hard-coded `reset_traffic=False` at lines 268, 276, 291; recovery loop at lines 758-834),
`app/webapi/routes/miniapp.py` (lines 7673, 7681, 7698), plus the cabinet daily-charge path.

Two defects, both confirmed present in our fork:

- The traffic counter of a daily tariff **never** resets — three daily-charge sites hard-code
  `reset_traffic=False` instead of consulting `RESET_TRAFFIC_ON_PAYMENT`, which every other payment
  path in the project honours. A paying customer accumulates usage from their first purchase until
  the panel cuts them off by limit — *while paying every day*. The only workaround today is the
  per-tariff `traffic_reset_mode`, i.e. pushing the reset onto the panel.
  Note the special case upstream handles: when the panel already resets the counter daily by itself,
  do **not** add our own reset, or a calendar day grants two quotas.
- A subscription that fell into `LIMITED` never comes back. Our recovery loop knows `DISABLED`
  (line 765) and `EXPIRED` (line 802) but has no `LIMITED` branch. The recovery must run only when
  the charge will actually reset the counter, otherwise it revives a subscription straight back into
  the limit.

Rank this **above tasks 4 and 5** if you only have time for one Plan B item: it silently cuts off
customers who are paying correctly, which is worse than a mispriced display or a switch exploit.

## Persian / i18n

- Task 4: per upstream's own commit message the "you will lose N days" warning text does not change.
  If the hand-adaptation needs any new string (e.g. "switching on the last day is not free"), that
  same commit must add the key to **both** `remnabot/locales/en.json` and `remnabot/locales/fa.json`.
- Task 5: no new keys, but **the displayed number changes** — the Toman amount on the daily-tariff
  card must be compared against the amount actually charged during the smoke test.
- Task 8: check whether the LIMITED-recovery path sends the user a notification. Our fork already
  sends Persian notifications on `DISABLED->ACTIVE` (line 780) and `EXPIRED->ACTIVE` (line 814), so a
  `LIMITED->ACTIVE` branch needs a matching string in **both** `remnabot/locales/en.json` and
  `fa.json`, worded to match its two neighbours.

---

# Plan C — panel identity and referral reward

**Goal:** A subscription created by an admin tariff switch, and one created as a referral reward,
are both correctly created/linked in the panel so the user gets a working link.

## Vs. upstream

- **Our business logic:** none. Both are pure bot<->panel sync plumbing.
- **Upstream infra reused as-is:** `panel_id_is_free_for`, `link_subscription_panel_identity`,
  `SubscriptionService.sync_remnawave_user` — take verbatim; they replace 32 inline copies of the
  same predicate.
- **Must not be misused:** `118fe1be` touches upstream's **referral** path
  (`referred_by_id` / `ReferralEarning`). Do not treat this as a foundation for our B2B reseller
  model — per workspace `CLAUDE.md` those are different concepts. This only fixes a panel-sync bug.

## Tasks

**6. Populate `subscriptions.remnawave_id` when updating the panel account** (from `aafdb2f2`).
Files: `app/services/subscription_service.py`, `app/cabinet/routes/admin_users.py`.

**7. `sync_remnawave_user` choosing between create and update** (from `118fe1be`).
Files: `app/services/subscription_service.py`, `app/services/referral_reward_service.py` (line 922),
`app/webapi/routes/miniapp.py`.

Order matters: 6 before 7 — both edit nearby regions of `subscription_service.py`, and `aafdb2f2`
comes first in upstream history.

## Persian / i18n

Neither task has user-visible strings -> no locale changes.

---

## Branch disposition

- **`remnabot` / `worktree-agent-a9deadb5da0928e72` (`c5f4dd32`)** — **keep until Plan C is done,
  then delete.** 155 commits ahead, 0 behind: it holds the already-conflict-resolved version of
  every file here. During Task 4's hand-adaptation it is the most valuable reference available —
  `git diff prod-cutover..worktree-agent-a9deadb5da0928e72 -- <file>` shows how it was resolved
  before. Do not merge it. Delete after Task 7 so nobody picks it up by mistake; its worktree is not
  locked, so `git worktree remove` is straightforward.
- **`frontend` / `worktree-agent-af3db50c4f08bf7cb` (`9712d786`)** — **delete now.** 0 ahead / 24
  behind `prod-cutover`; contains nothing not already there. It only creates confusion.
- **`frontend` / `dc77a7d9`** — **no action needed, already done.** It *is* frontend `prod-cutover`.
  Only push and deploy remain, both explicitly out of scope. Note for smoke testing: because
  `/opt/project/frontend` sits on `fix/campaign-promocode-toman` and the `cabinet_frontend`
  container bind-mounts that source, what is live on panel.rookari.com is **not** `prod-cutover`.

---

## Open questions (need a decision before the affected work)

1. **Is email registration actually open in our cabinet?** Determines the fate of the deferred
   `0b622ba5` and how urgent Task 3 is.
2. **Should the wholesale discount apply to daily tariffs?** An approved partner on a daily tariff
   currently does not get their wholesale discount (found while verifying Plan B). Fixing it needs
   real policy numbers, which will not be invented here — it becomes its own plan once answered.

---

## Smoke test

After **each plan** finishes (not once at the end), generate the checklist fresh with the
`smoke-test-checklist` skill. It is deliberately not written here: a checklist authored before the
code exists cannot describe what to actually click — especially for Plan B, whose bot tariff-switch
flow only takes its final shape after hand-adaptation.
