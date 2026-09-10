# Selective upstream patches onto `main`

**Status:** active — **Plans A and B done.** A: bot #18; cabinet frontend #7; found during it and
fixed: cabinet branding-cache crash, frontend #8. B: bot #20, plus follow-up #21 (daily charges
100x off, open question 4). Both are deployed to the dev bot as of 2026-09-10. Plans C–E not started.
**Repos:** `remnabot` (Plans A–D, all bot-first) → `frontend` (Task 3's error mapping, Plan E).
`origin` = `k4lantar4/*`; `upstream` = `BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot` /
`BEDOLAGA-DEV/bedolaga-cabinet`.
**Upstream basis (re-verified 2026-09-10):**
- `remnabot`: release **v4.8.0** (`1fe2b47a`, = `upstream/main`) **plus `upstream/dev` up to
  `dc9a7ca7`** (2026-09-10, 20 commits past the release, all triaged below). Upstream ships fixes on
  `dev` a day or more before a release, so the preflight checks `upstream/dev` too, not only
  `upstream/main`.
- `frontend`: release **v1.72.0** (`7200853`, = `upstream/main`; no upstream `dev` branch ahead of
  it). Our fork is synced to v1.71.1 (merge-base `5ade78f5`).
**Fork basis:** `remnabot` `origin/main` `aa900324` (PR #16), `frontend` `origin/main` `dc18c0fe`.
Every file/line reference below was re-checked on those commits.

**Unit of work:** one branch + one PR per sub-plan (A, B, C, D, E), each off `origin/main`, so
each is reviewable on its own. Tasks inside a sub-plan are commits.

> Before starting **any** task, run the upstream-freshness preflight in `plan-execution`, and also
> `git log --oneline dc9a7ca7..upstream/dev -- <files of the task>`. Upstream corrected its own
> expiry fix twice in two days (4.7.1 → 4.8.0 → dev `3513e1db`); a basis goes stale in days.

This plan takes only fixes that are genuinely broken *in our fork*, as small commits. It replaces
the abandoned all-at-once merge (branch `worktree-agent-a9deadb5da0928e72`). We are not catching up
with upstream (~192 commits behind `upstream/main`); the gap growing is expected.

---

## Verification notes (do not re-derive)

- **No accepted patch carries a migration.** Our Alembic head is `0112`
  (`0112_referral_earnings_reward_columns.py`, chain `… 0104 → 0111 → 0112`, no 0105–0110 files).
  Anything added later that brings a migration chains onto `0112`. Upstream dev's `76c6385c` adds
  `0119_tariff_panel_tag_and_trial_days` — rejected, and a reason never to cherry-pick upstream
  migrations by number.
- **None of the accepted upstream commits has landed** on `origin/main`: the v4.8.0-era ones are
  all `+` in `git cherry` with no subject match, and the files/symbols the dev ones add
  (`is_expire_in_past_error`, `is_stale_external_squad_error`, `addon_cart.py`) are absent.
- **`841e2bda` must NOT be cherry-picked.** It fixes a `NameError` that exists only on the abandoned
  merge branch. Our `pricing_engine.py` has `import dataclasses` (line 3) and `dataclasses.asdict`
  at 685, 740, 895 — working code.
- **Live display bug found while re-verifying (raises Task 5's priority).** `frontend` already
  carries upstream cabinet `881e557d` (2026-09-08): `src/components/subscription/purchase/dailyPrice.ts`
  `dailyPriceQuote` treats `daily_price_kopeks` as "server price, already with the *group*
  discount" and applies the active promo offer **once more**. Our bot still stacks group +
  promo-offer into `daily_price_kopeks` (`app/cabinet/routes/subscription_modules/purchase.py:232-245`,
  and `helpers.py:171-183`). A user with an active promo offer therefore sees the offer applied
  **twice** on the tariff card, the activation screen and the switch sheet, while
  `daily_subscription_service.py` charges group-only. Bot `968687ce` is the half we are missing.
- **Test baseline:** `main` is red; numbers live only in `remnabot/CLAUDE.md` → "CI baseline".
  Measure in a fresh worktree, never in the live checkout.

### Upstream `dev` past v4.8.0 (`1fe2b47a..dc9a7ca7`, triaged 2026-09-10)

| Commit | Decision | Why |
|---|---|---|
| `3513e1db` fix(panel-sync): clearing the panel date survives bot/panel clock skew | **Accepted — folded into Task 1** | Corrects the rule Task 1 ports: margin 1 → 5 min, retry at 15 min when the panel rejects the date as past, status-first split. Porting the v4.8.0 form alone would ship a bug upstream reproduced (3 min skew) |
| `9d786897` fix(remnawave): client vs OpenAPI 3.4.3 | **Partly accepted — Task 9** | We run panel 3.4.3. Our `is_user_not_found_error` (`remnawave_api.py:296-309`) returns true for *any* 404 or `A018` → callers re-create the panel user (duplicates). Bandwidth webhook (`remnawave_webhook_service.py:1846`) reads fields the panel doesn't send → user always sees "80%". Host `tags`/reachability, dead-method removal, `tz` param and the contract-fixture test are not taken (reachability was removed in our fork; the rest is cleanup) |
| `0009c30b` + `8fe30849` fix(cart): add-on cart survives to purchase | **Accepted — Plan D (Task 10)** | All three causes confirmed in our fork, see Task 10 |
| `917f3950` fix(sync): 429 no longer fails the to-panel pass | Not taken | Our client already retries 429 with `Retry-After` per request (`remnawave_api.py:516`); the shared pause targets upstream's `panel_sync/runner.py`, which we don't have |
| `0715b5c7`, `dc9a7ca7` fix(sync): don't hold a DB transaction while talking to the panel | **Deferred — verify first** | Same defect class plausibly exists in our `RemnaWaveService.sync_users_to_panel` (`remnawave_service.py:2617`, one `db` session across 500-row batches), but it is not reproduced here and upstream's fix lives in its runner. Own investigation, not a cherry-pick |
| `6144e6eb` fix(cabinet): zero = no highlighted period on tariff create | N/A | Our `TariffCreateRequest` has no `highlight_period_days` |
| `a7d023c8` fix(reachability) | N/A | No reachability module in our fork |
| `f06959ca`, `76c6385c`, `e17eb67f`, `06ae99af`, `1cb76d8c`, `cddbf296` | Rejected | Features (full-sync-to-panel with panel tags, tariff panel tag + migration `0119`, Telegram tariff editor, squad-name validation, activity trail) |
| `46a7a1b5`, `d22b0d7e`, `4784029d`, `bd88997b`, `3b5c8d48` | Rejected | Tests/docs/lockfile for the above |

### Upstream cabinet v1.71.1 → v1.72.0 (triaged 2026-09-10)

| Commit | Decision | Why |
|---|---|---|
| `db7344c0` fix(ui): subscription card no longer overflows on mobile | **Accepted — Plan E** | Buggy code present (`ConnectDeviceTile.tsx:110`, `SubscriptionCardActive.tsx:170,182,192`); long Persian tariff names make it worse for us |
| `e53803a1` fix(admin): tariff period price may be 0 | **Accepted — Plan E** | Buggy code present (`AdminTariffCreate.tsx:222`, `:612`); our backend already accepts free tariffs |
| `14832d0d`, `388b974f` best-value period preselect / outline | Not taken | Need `is_highlighted`, which our bot never sends |
| `57a3d94d` don't query disabled autopay | Not taken | Platega/Lava (RU gateways) only |

Upstream cabinet does **not** handle `email_auth_disabled` anywhere — Task 3's frontend half is
ours to write.

---

## Accept list and priority

| # | Upstream | Plan | Why |
|---|---|---|---|
| 4 | `564fec3e` | B | **Highest value.** Daily-tariff customers are throttled to their limit while paying, and LIMITED subscriptions never recover |
| 1 | `39097eb9` + `7816e1e9` + dev `3513e1db` | A | Every sync destroys the real expiry date in the panel (irreversible data loss) |
| 2 | `664ecea7` | A | Same bug, grace path |
| 5 | `968687ce` | B | Live double-discounted daily price in the cabinet (see verification notes) |
| 3 | `23a58172` + `fdebcad1` | A | Security: the admin email-login toggle leaves the API open |
| 6 | `fd9b2ccc` | B | Revenue loss + unlimited traffic via `A → B → A` switching |
| 9 | dev `9d786897` (partial) | C | Duplicate panel users on unrelated 404s; wrong % in the traffic warning |
| 10 | dev `0009c30b` + `8fe30849` | D | Customer tops up for an add-on and it is never bought; the button deletes the cart |
| 7 | `aafdb2f2` | C | Admin subscription screen breaks; currently fixed by hand in the DB |
| 8 | `118fe1be` | C | Referral-reward subscription has no working link |
| 11 | cabinet `db7344c0` + `e53803a1` | E | Mobile card overflow; admin can't price a period at 0 |

Suggested order of PRs: **A → B → C → D → E**. A and C don't touch pricing; B is the only one in
pricing code; D touches the hot file `purchase.py`; E is frontend-only and can go any time.

**Rejected from the v4.7.1/v4.8.0 review (unchanged):** `6014b92b` (our `admin_partners.py` diverged
with `is_env_locked`/`ENV_OVERRIDE_KEYS`, and "partner" there means upstream's referral program, not
our نماینده), `423bbf7d` (feature: resend verification email; route absent here), `841e2bda` (see
above). **Deferred:** `0b622ba5` (registration throttle) — decide after Plan A, see open question 1.

---

# Plan A — expiry data loss and email-login security (remnabot, then frontend)

**Goal:** The panel stops having the real end date of expired subscriptions overwritten with
"now + 1 minute" (and a bot clock running behind the panel no longer leaves a falsely active
subscription); turning email login off in the cabinet actually closes the API. Both B2C and partner.

## Vs. upstream

- **Ours that must survive:** nothing in wholesale / `PartnerStatus` / `pricing_engine.py` /
  `price_display.py` is touched. `grace_access_runtime.py` changes only at its two date points.
- **Reused as-is:** the rule from upstream `app/services/panel_sync/expiry.py` **at `dc9a7ca7`**
  (not at v4.8.0), `is_expire_in_past_error` from `app/external/remnawave_api.py` (`3513e1db`),
  `app/cabinet/auth/email_auth_gate.py`, `BotConfigurationService.deserialize_value` (already ours).
  **Do not port the `panel_sync/` package** (identity, liveness, payload, projection, runner, writer,
  expiry…): that is a second big-bang merge. Take the rule into one small module of ours.
- **Gateways:** none touched. CryptoBot stays as it is (off, undecided — don't flip it).

## Tasks

**1. `app/services/panel_expiry.py` with the dev-`3513e1db` rule, used by all panel-write points.**
- Done: `724e639d`, PR #18. Adapted: a clear still rejected after the 15-min retry is logged, not
  raised (our update paths turn any exception into "create a new panel user").
- Files: `app/services/panel_expiry.py` (new), `app/external/remnawave_api.py` (add
  `is_expire_in_past_error`), `app/services/subscription_service.py` (452, 648, 819),
  `app/services/monitoring_service.py:694`, `app/services/remnawave_service.py:320-327` (delete the
  now-dead `_safe_expire_at_for_panel`, caller at 2664), `app/cabinet/routes/admin_users.py`
  (390, 4280). Test: `tests/services/test_panel_expiry.py` (new; adapt upstream
  `tests/services/panel_sync/test_expiry.py` + the skew cases of `test_writer.py` at `dc9a7ca7`).
- Interfaces produced: `panel_expire_at(...)` and `stale_panel_expire_at(...)` (upstream names and
  semantics from `git show dc9a7ca7:app/services/panel_sync/expiry.py`), constants
  `MINIMUM_FUTURE = 5 min`, `SKEW_RETRY_MARGIN = 15 min`, already-cleared window
  `SKEW_RETRY_MARGIN + 4 min`; one async helper `update_panel_user_with_expiry(update, *, end_date, is_active, panel_current=None, now=None, **update_kwargs)` (takes the write callable, e.g. the grace-safe updater)
  that owns the skew fallback so the six call sites don't each re-implement it;
  `is_expire_in_past_error(error) -> bool` (400 with `expireAt` in an error `path` or "past" in the
  message).
- Rule (all branches — don't simplify):
  - future end date → send it, for live and blocked/disabled subscriptions alike;
  - create → send the real end date even if past (panel `POST` accepts past dates);
  - update, expired, panel holds past/unknown → omit `expireAt`;
  - update, expired, panel holds future → clamp once to `now + 5 min`; inside the already-cleared
    window, leave it;
  - panel rejects the date as past (`is_expire_in_past_error`) → if the date rode with the status
    in one PATCH, resend without `expireAt` first (status wins), then clear the date separately;
    a rejected clear retries once at `now + 15 min` with a warning log about clock skew.
- The "panel holds future" branch needs the panel's current value from the PATCH response — check
  per call site against our client that it's available; this is the part most likely to need
  adaptation.
- Test (logic, failing first): each rule branch, including a 3-minute bot-behind-panel skew.
- i18n: none (logs only).

**2. Same rule in the grace path** (`664ecea7`).
- Done: `338f92ca`, PR #18.
- Files: `app/services/grace_access_runtime.py` (**1688, 1718** — moved from 1676/1706). Test in the
  existing grace test module.
- Consumes nothing from Task 1 in the end: as upstream, a disabled grace target carries no date
  (`_PanelTarget.expire_at` optional); Task 1's guard test now covers this module.
- i18n: none.

**3. Email-auth gate with the correct parser — bot, then cabinet** (`23a58172` + `fdebcad1` as one
bot commit; plus our own frontend commit).
- Done: bot `1e8b9963` (PR #18); cabinet `40e7020e` (frontend PR #7).
- Bot files: `app/cabinet/auth/email_auth_gate.py` (new), `app/cabinet/routes/auth.py` (all 8 of
  upstream's gated handlers, 1:1 by name — upstream gates 8, not 9; today zero routes check the
  flag), `app/cabinet/routes/branding.py` (fix the `.lower() == 'true'` parse in
  `get_email_auth_enabled` at 1017, use the shared key; the admin PATCH at 1031-1037 writes the key
  and stays), `app/cabinet/routes/account_linking.py:88` (reads the config value, must read the
  gate). Test: adapt upstream's end-to-end HTTP gate test.
- Produces: HTTP 403 with `detail = {'code': 'email_auth_disabled', 'message': <English>}`.
- Frontend files: `src/utils/api-error.ts` (`getApiErrorMessage` today reads only `detail`
  string/array/`{message}` and never branches on a code — map `email_auth_disabled` to an i18n key),
  `src/locales/en.json` + `src/locales/fa.json` (new key, e.g. `auth.emailAuthDisabled`). Test:
  unit test for the mapping in `src/utils`.
- i18n: the new frontend key in **both** locales — natural Persian, not a mirrored English
  sentence; Latin digits. Quality-pass the neighbouring Persian keys on the login screen.
- Cross-repo: bot PR first (the gate only rejects requests for a feature that is switched off),
  frontend PR second, linked.

---

# Plan B — daily tariffs and tariff switching (remnabot)

**Goal:** Daily-tariff customers stop being throttled while paying; the daily price the cabinet
shows is exactly what is charged; switching tariffs on the last day is no longer free and no longer
resets traffic. B2C (partners on daily tariffs: see open question 2).

## Vs. upstream

- **Ours:** `uses_wholesale_pricing`, `apply_wholesale_discount`, `wholesale_discount_bps` in
  `pricing_engine.py` must not change. Recorded gap, not fixed here: the daily-price path in
  `helpers.py` never consults wholesale (open question 2).
- **Reused as-is:** `app/services/traffic_reset_policy.py` (`git show 1fe2b47a:…`),
  `app/services/tariff_switch_policy.py`, `PricingEngine.daily_group_price`.
- **Currency:** all three tasks stay on catalog scale (`daily_price_kopeks`, `price_kopeks`) and
  don't touch `_BALANCE_SCALE_TRANSACTION_TYPES`. Working assumption: **Phase C out of scope** —
  don't widen the dual scale, don't migrate inline. Say so before Plan B if Phase C is in.

## Tasks

**Done — merged as #20 (`74c065e6`), deployed to the dev bot 2026-09-10 18:29 UTC; follow-up #21
(`39ad24a5`, recurring daily charges now take the Toman amount) deployed 19:02 UTC.** Preflight 2026-09-10: upstream
moved to **v4.9.0** (`4e6e9224`; `upstream/dev` = `249ea848`); `dc9a7ca7` is in it and no commit in
`dc9a7ca7..v4.9.0` or `v4.9.0..upstream/dev` touches a Plan B file — basis still valid. Commit order
5 → 4 → 6 as planned.

**4. Daily charge resets the traffic counter; LIMITED subscriptions recover** (`564fec3e`).
- Done: `e07f50f2`. Applied cleanly. Not taken: the reworded `RESET_TRAFFIC_ON_PAYMENT` hint in
  `system_settings_service.py` (`SETTING_HINTS` is hard-coded Russian without en/fa keys). This
  dev `.env` has `RESET_TRAFFIC_ON_PAYMENT=true`, so daily tariffs now reset on each daily charge.
- Files: `app/services/traffic_reset_policy.py` (new), `app/services/daily_subscription_service.py`
  (`reset_traffic=False` hard-coded at 268, 276, 291; `process_auto_resume` loop 758-834 — DISABLED
  branch at 765, EXPIRED at 802, **no LIMITED branch**), `app/webapi/routes/miniapp.py` (7673, 7681,
  7698), and the cabinet daily-charge path. Test: adapt upstream's daily reset tests.
- Rules: honour `RESET_TRAFFIC_ON_PAYMENT` like every other payment path; when the panel already
  resets the counter daily by itself, don't add ours (else one day grants two quotas); run LIMITED
  recovery only when this charge actually resets the counter.
- i18n: **none.** The DISABLED→ACTIVE and EXPIRED→ACTIVE lines (780, 814) are log messages, not
  user notifications, so a LIMITED→ACTIVE branch is log-only too.

**5. `daily_group_price` as the single source of the daily price** (`968687ce`).
- Done: `9d82c6da`. The offer is taken once, at activation (`pricing_engine.py:~652` with
  `consume_promo_offer`); every later day is charged group-only. So the screens showing an
  existing subscription's recurring price — bot `show_subscription_info`, Mini App
  `get_subscription_details` and `_build_current_tariff_model` — now use `daily_group_price`
  (upstream left them stacked). The Mini App purchase list `_build_tariff_model` keeps the offer:
  that client never re-applies it, so it shows the activation price, as its periods do.
  `daily_group_price` sits beside our wholesale methods (the only conflict).
- Files: `app/services/pricing_engine.py` (add `daily_group_price`),
  `app/cabinet/routes/subscription_modules/helpers.py` (171-183, drop `_offer_pct` stacking),
  `app/cabinet/routes/subscription_modules/purchase.py` (232-245, same stacking),
  `app/services/daily_subscription_service.py` (152-159). Surface parity: grep
  `apply_stacked_discounts` / `daily_price` in `app/webapi/routes/miniapp.py` and the bot tariff
  handlers and route them through `daily_group_price` too. Test: failing test that the cabinet's
  `daily_price_kopeks` equals the amount `daily_subscription_service` charges.
- Contract with the cabinet (already shipped, `881e557d`): `daily_price_kopeks` = group-discounted
  only, `original_daily_price_kopeks` = undiscounted; the cabinet applies the promo offer once. Read
  `968687ce` for what the promo offer applies to when charging (activation vs every day) and make the
  displayed amounts match that — no frontend change expected.
- i18n: no new keys; **the displayed Toman number changes** — compare card vs activation vs charge
  in the smoke test, with and without an active promo offer.

**6. `tariff_switch_policy.py` in all three switch flows** (`fd9b2ccc`).
- Done: `5ef0bc61`. Applied cleanly, hot file included — no split needed. Checked by hand that
  `final_price` / `final_daily_price` / `upgrade_cost` exist in our functions and are the charged
  amounts; our direct readers of `RESET_TRAFFIC_ON_TARIFF_SWITCH` equal upstream's allowlist.
- Review follow-ups (gaps upstream v4.9.0 shares): `3fcac274` — the bot resume button and the
  resume after a top-up also charge the daily fee and still hard-coded "never reset"; both now
  follow the reset policy, and all five daily charges price via `daily_group_price`.
  `9f9ccc83` — bot daily → daily switch: the reset is decided from the amount actually charged
  (the first day), not from `upgrade_cost == 0`.
- Found while deploying #20/#21 (pre-existing, fixed on branch `fix/startup-dedup-and-locale-probe`):
  - **The startup dedup pass failed on every start.** The Platega/Lava "cancel recurring by
    subscription" lookups query `platega_subscriptions` / `lava_subscriptions`. Those tables were
    never created here (upstream's migrations for them are archived, not grafted). On Postgres
    the failed SELECT aborts the caller's whole transaction, and the helpers swallowed the error.
    About 24 callers run them inside a larger transaction: dedup, admin and cabinet subscription
    deletion, account merge, tariff switch, user deletion and others. The lookup now runs in a
    SAVEPOINT. Creating the tables stays a separate migration decision.
  - **The locale seeder probed write access on every start.** A populated, git-tracked
    `locales/` mounted from a root-owned directory therefore logged "Locale directory is not
    writable" each time. It now probes only when a template actually has to be copied.
- Files: `app/services/tariff_switch_policy.py` (new),
  `app/cabinet/routes/subscription_modules/tariff_switch.py` (`.days` 139, 324; reset flag 485,
  514), `app/webapi/routes/miniapp.py` (`.days` 6570, 6954, 7088; reset flag 7185, 7233),
  `app/handlers/subscription/tariff_purchase.py`.
- **Highest adaptation risk.** Hot file, far diverged: `.days` at 923, 2674, 3438, 3514, 3554, 3704,
  3810, 4111, 4567, 4696, 4987 and `RESET_TRAFFIC_ON_TARIFF_SWITCH` at 3911, 3918, 4188, 4206, 4213,
  5085, 5163, 5170. Adapt by hand; if too big, split (a) policy + cabinet/miniapp, (b) bot flow.
  Reference for how it was resolved before: `git diff origin/main...worktree-agent-a9deadb5da0928e72
  -- <file>`.
- Test: policy unit tests (last-day switch not free; `A → B → A` doesn't restore traffic).
- i18n: upstream keeps the "you will lose N days" text; any new string goes into `locales/` **and**
  `app/localization/locales/` `en.json` + `fa.json`, byte-identical pairs.

---

# Plan C — panel identity and panel-client errors (remnabot)

**Goal:** Subscriptions created by an admin tariff switch or as a referral reward get a working
panel link; an unrelated panel 404 no longer creates a duplicate panel user; the traffic warning
shows the real threshold. B2C and partner alike.

## Vs. upstream

- **Ours:** none — bot ↔ panel plumbing. The panel is fixed (3.4.3); we adapt the bot.
- **Reused as-is:** `link_subscription_panel_identity`, `SubscriptionService.sync_remnawave_user`,
  and from `9d786897` the error predicates. We already have a **private**
  `_panel_id_is_free_for` (`subscription_service.py:347`, called at 279, 404, 508, 1368) — upstream's
  public `panel_id_is_free_for` is the same predicate: promote ours, don't add a second copy.
- `118fe1be` touches upstream's **referral** path (`referred_by_id` / `ReferralEarning`) — not a
  foundation for the B2B reseller model.

## Tasks

**7. Set `subscriptions.remnawave_id` when updating the panel account** (`aafdb2f2`).
- Files: `app/services/subscription_service.py`, `app/cabinet/routes/admin_users.py`.
- Produces: public `panel_id_is_free_for`, `link_subscription_panel_identity`.
- Test: admin tariff switch on a subscription without `remnawave_id` ends with it set. i18n: none.

**8. `sync_remnawave_user` chooses create or update** (`118fe1be`).
- Files: `app/services/subscription_service.py`, `app/services/referral_reward_service.py:922`
  (currently `update_remnawave_user`), `app/webapi/routes/miniapp.py`.
- Consumes Task 7's helpers. Test: reward subscription with no panel user → created. i18n: none.

**9. Panel-client error classification per OpenAPI 3.4.3** (dev `9d786897`, partial).
- Files: `app/external/remnawave_api.py` — `is_user_not_found_error` (296-309): true only for
  `errorCode` `A025`/`A063`, or a 404 *without* an error code whose message is one of "user not
  found" / "user with specified params not found" / "users not found"; keep our
  `RemnaWaveInvalidUserIdError` early return. Add `is_stale_external_squad_error` (`A018`, `A039`,
  `A182`, or "external squad not found") and use it in the create (~640) and update (~856) retries,
  retrying on a **copy** of the payload instead of `data.pop`.
  `app/services/remnawave_webhook_service.py:1846` — take the percent from
  `data['lastTriggeredThreshold']` first.
- Check the callers that branch on it (`admin_users.py:513, 4391`, `remnawave_api.py:721, 868`) still
  do the right thing. The inline `status_code == 404 → None` lookups (666, 682, 692, 964, 1046) are
  out of scope unless one leads into re-creation.
- Order: after Task 1 (both edit the same region of `remnawave_api.py`).
- Test (failing first): A018 / A118 / A182 / plain 404 are not "user not found"; A025 is; create with
  a stale external squad retries without it and leaves the caller's dict intact; the bandwidth
  webhook formats the `lastTriggeredThreshold` value.
- i18n: `WEBHOOK_SUB_BANDWIDTH_THRESHOLD` text unchanged — quality-pass its `fa` wording while here.

---

# Plan D — add-on cart survives top-up (remnabot)

**Goal:** A customer who tries to buy extra traffic or devices without enough balance, then tops
up, gets the add-on — automatically, or via "back to checkout" — instead of "cart corrupted" /
"cart not found". B2C.

## Vs. upstream

- **Ours:** keep `purchase.py` (hot file) to one dispatch branch; the logic lives in upstream's new
  module `app/handlers/subscription/addon_cart.py`. Payment providers stay frozen: the only payment
  file touched is the shared post-top-up hook in `app/services/payment/common.py`.
- **Currency — check before coding:** add-on carts store `price_kopeks` (catalog-scale `final_price`)
  while subscription carts store `total_price`; `common.py` compares the cart total with the
  balance. Confirm both keys are on the same scale relative to `balance_kopeks` before treating them
  as interchangeable. If they're not, stop and ask — that is Phase C territory, not something to
  paper over with a conversion here.

## Tasks

**10. Add-on carts carry intent, resume from the button, and pass the top-up hook**
(dev `0009c30b` + `8fe30849`).
- Confirmed causes on `origin/main`:
  - the 8 add-on cart saves never set `return_to_cart`, so `has_topup_intent` fails and the silent
    auto-purchase skips them (`subscription_auto_purchase_service.py:~3500`) — cabinet
    `subscription_modules/devices.py:198, 473, 755`, `subscription_modules/traffic.py:303, 548`;
    bot `handlers/subscription/devices.py:409, 1600`, `handlers/subscription/traffic.py:618`;
  - the "back to checkout" handler requires `period_days` and answers "Корзина повреждена"
    (`handlers/subscription/purchase.py:1494`), deleting the add-on cart;
  - `common.py:450` requires `total_price`, which add-on carts don't have.
- Files: the 8 save sites above, `app/handlers/subscription/addon_cart.py` (new),
  `app/handlers/subscription/purchase.py` (dispatch `cart_mode in ('add_traffic', 'add_devices')`
  before the `period_days` check), `app/services/subscription_auto_purchase_service.py` (let the
  button path run the existing `add_traffic` / `add_devices` handlers at 3175-3177 without the
  silent gates — the user pressed it), `app/services/payment/common.py:450` (accept `total_price` or
  `price_kopeks`). Tests: adapt upstream `tests/handlers/test_addon_cart_resume.py` and
  `tests/services/test_addon_cart_real_purchase.py`, including upstream's guard that every add-on
  cart save sets the flag.
- i18n: 5 keys — `ADDON_CART_STILL_INSUFFICIENT`, `ADDON_CART_COMPLETED`, `ADDON_CART_FAILED`,
  `ADDON_PURCHASE_TRAFFIC_SUCCESS`, `ADDON_PURCHASE_DEVICES_SUCCESS` — in `en.json` + `fa.json`
  under **both** `locales/` and `app/localization/locales/` (byte-identical). Write the Persian
  ourselves (upstream's is literal: e.g. «محدودیت جدید» reads better as «سقف جدید»); amounts via
  `format_price`, Latin digits. Add ru/ua/zh only if a parity test would otherwise newly fail.

---

# Plan E — cabinet cherry-picks (frontend)

**Goal:** The subscription card no longer overflows on mobile; admins can set a tariff period price
to 0. B2C UI + admin.

## Vs. upstream

- Clean cherry-picks of upstream cabinet `db7344c0` and `e53803a1` (both apply to code unchanged in
  our fork). No Iran/Toman logic involved; no gateway touched.

## Tasks

**11. Cherry-pick `db7344c0` and `e53803a1`** (two commits, `git cherry-pick -x`).
- Files: `src/components/dashboard/ConnectDeviceTile.tsx`,
  `src/components/dashboard/SubscriptionCardActive.tsx`, `src/pages/AdminTariffCreate.tsx`; tests
  arrive with the commits: `src/components/dashboard/subscriptionCardLayout.test.tsx`,
  `src/pages/adminTariffFreePeriod.test.tsx`.
- Test: the two upstream tests must pass (no new failures vs. baseline); plus visual — verify live on
  panel.rookari.com at phone width with a long Persian tariff name, and create a tariff with a
  0-priced period. `npm run type-check` + biome clean on touched files.
- i18n: none.

---

## Branch disposition

- **`remnabot` / `worktree-agent-a9deadb5da0928e72`** (`c5f4dd32`, 155 ahead / 40 behind
  `origin/main`) — keep as the conflict-resolution reference for Task 6; delete (with its worktree)
  once Plan C lands. Never merge it.
- The frontend branch `worktree-agent-af3db50c4f08bf7cb` is already gone; `dc77a7d9` (BSCHEKER
  removal) is in `frontend` `origin/main`. The live `frontend` checkout is on `main`, so
  panel.rookari.com serves `main` unless someone switches it — check before smoke-testing.

## Open questions (needed before the affected work)

1. **Is email registration actually open in our cabinet?** Decides the deferred `0b622ba5` and
   Task 3's urgency.
2. **Should the wholesale discount apply to daily tariffs?** An approved partner on a daily tariff
   gets group + offer, not their wholesale discount. Needs policy numbers — its own plan once
   answered.
3. **Phase C for Plans B/D?** Default: out of scope (don't widen the dual scale, don't migrate
   inline).
4. ~~**Daily charges look 100x off.**~~ **Decided 2026-09-10: fix now, own PR** (branch
   `fix/daily-charge-toman-scale`). The first-day activation converted the catalog price with
   `catalog_price_in_toman` (÷100), but the recurring charges —
   `daily_subscription_service._process_single_charge`, the cabinet / Mini App / bot resumes and
   `try_resume_disabled_daily_after_topup` (incl. its refund) — compared `daily_price_kopeks` with
   the Toman balance and passed it to `subtract_user_balance` unconverted. Surfaced live once tariff 9
   (1,000,000 kopeks = 10,000 Toman/day) was created: its first recurring charges would have taken
   1,000,000 Toman each. Now all five use `user_can_afford` / `catalog_price_in_toman`, like the
   activation; transaction records stay on the catalog scale. Phase C would remove the distinction.

## Smoke test

After **each** sub-plan's PR, generate the checklist with `smoke-test-checklist` — not now; it must
describe the shipped code (especially Task 6's hand-adapted bot flow and Task 5's changed numbers).
