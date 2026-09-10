# Grace access for subscription renewal

Grace access temporarily leaves the client on a special Remnawave squad that Telegram should still work through. It is intended for two cases:

- `expired` — the subscription time has ended;
- `limited` — the current period’s traffic has been exhausted.

The bot database remains the source of truth for billing. Grace does not extend the paid period in the database, does not change the tariff, and never reduces already used traffic. After payment, the panel receives the usual current values from the database.

## Modes

- `GRACE_ACCESS_MODE=false` — the feature is off: new grace sessions are not created and background processing does not start. Do not use this mode to stop grace that has already been granted: apply `drain` first.
- `GRACE_ACCESS_MODE=observe` — the bot only detects matching cases and writes them to the log. Grace sessions are not created; access and Remnawave are not changed.
- `GRACE_ACCESS_MODE=true` — new grace sessions are issued and already open sessions are processed.
- `GRACE_ACCESS_MODE=drain` — new grace sessions are not issued. Already active sessions finish correctly on payment or their original deadline; unfinished `pending` is not activated.

There is no allowlist.

## Settings

The intended place is the web cabinet, **Admin → Grace access**. The same screen validates configuration (an empty or invalid squad UUID will not allow enabling the mode), shows the running mode next to the saved one, and shows session state.

Keys can also be set in `.env`, but there is a cost: a key that is physically present in the file is added to `ENV_OVERRIDE_KEYS`, the file overrides the database, and the setting can no longer be changed from the admin UI — the section opens with a lock on every field, and saving returns 409. That is why these keys are commented out in `.env.example`. Put them in the file only where the value must be immutable:

```env
GRACE_ACCESS_MODE=observe
GRACE_ACCESS_DURATION_HOURS=72

GRACE_ACCESS_EXPIRED_SQUAD_UUID=UUID_OF_THE_EXPIRED_SQUAD
GRACE_ACCESS_LIMITED_SQUAD_UUID=UUID_OF_THE_LIMITED_SQUAD

GRACE_ACCESS_TRAFFIC_GB=1

GRACE_ACCESS_TRIAL_ENABLED=false
GRACE_ACCESS_DAILY_ENABLED=false
GRACE_ACCESS_FREE_ENABLED=false

GRACE_ACCESS_RECONCILE_INTERVAL_SECONDS=60
GRACE_ACCESS_RECONCILE_BATCH_SIZE=200
GRACE_ACCESS_CANDIDATE_LOOKBACK_MINUTES=30
```

Both UUIDs must be real UUIDs of internal Remnawave squads. You may use the same Telegram-only squad for both cases. Its nodes must not have a route to the regular internet: the “Telegram only” restriction is enforced by the squad/node network configuration, not by the bot itself.

In `true` mode, `GRACE_ACCESS_TRAFFIC_GB` must be at least 1 GiB. That is the exact quota the client can spend during grace. Remnawave stores a cumulative usage counter, so the panel’s technical limit is “current usage + grace quota”. The counter is not reset: the old remainder and the old unlimited flag are not carried into temporary access.

With `GRACE_ACCESS_MODE=true`, grace is available by default to ordinary paid non-daily subscriptions. Additional flags enable the other mutually exclusive kinds. A subscription is classified by priority: trial → daily → free → ordinary paid. For example, a free daily subscription is controlled only by `GRACE_ACCESS_DAILY_ENABLED`.

Both reasons share the same duration and quota, but keep different squads. To create the overlay, Remnawave must return current traffic usage; if usage is unknown, issuance is safely deferred until the next reconciler attempt.

The old variables `GRACE_ACCESS_EXPIRED_TRAFFIC_GB` and `GRACE_ACCESS_LIMITED_TRAFFIC_GB` are no longer supported.

## Repeat issuance

- `expired` is issued once for a specific subscription end date. Renewal changes the date and creates a new incident.
- `limited` uses the combination of end date, total limit, and `lastTrafficResetAt`. Changing any of these values creates a new incident. If Remnawave did not return a reset date, the stable marker `unknown` is used.

A repeated webhook, restart, or repeated background check of the same incident does not create a new grace session. Subscription-kind flags are checked only on new issuance: an already open session is not cut off after the corresponding flag is disabled.

## First production enablement

1. Back up the database and the current `.env`.
2. First set mode `observe` (cabinet: **Admin → Grace access**, or `GRACE_ACCESS_MODE=observe` in `.env`) and restart the bot: the mode is read once at startup, so a saved value does nothing without a restart. The migration creates a separate `grace_access_sessions` table and three service fields on `subscriptions`.
3. Check status:

   ```bash
   python -m app.tools.grace_access status
   ```

4. Confirm from `Grace candidate observed` logs that only the expected `expired` and `limited` clients are detected.
5. Fill in the Telegram-only squad UUIDs, switch the mode to `true`, and restart the bot. UUIDs apply immediately; the mode applies only after restart.
6. Check the first issued client in Remnawave: status is temporarily `ACTIVE`, only the grace squad is assigned, the external squad is removed, expiry equals the grace end time, and the limit equals current usage plus `GRACE_ACCESS_TRAFFIC_GB`. Used traffic must not decrease.

If `true` mode configuration is invalid, grace stays off and the main bot continues to start with a critical log entry.

## What happens on payment

1. The bot payment logic updates the ordinary subscription in the database.
2. The grace handler sees the new period/traffic.
3. Remnawave is restored to the canonical status, period, limit, squads, and external squad of the paid tariff.
4. The grace session finishes with reason `paid`.

Ordinary sync during grace continues to fetch traffic usage and links, but does not overwrite the temporary period, status, and squads.

## Emergency stop and rollback

For a normal stop, first set `GRACE_ACCESS_MODE=drain`. Do not switch straight to `false`: open sessions need the new code to restore clients safely.

Inspect state and run a dry check without changes:

```bash
python -m app.tools.grace_access status
python -m app.tools.grace_access restore-all
```

Immediately restore all open sessions:

```bash
python -m app.tools.grace_access restore-all --apply
```

The command refuses to run if configuration is still `true`. It checks the **saved** configuration, while the running process may have started with a different mode: a cabinet switch takes effect only after restart. Therefore restart the bot before `restore-all --apply` — otherwise the live worker will keep issuing grace while the command is closing sessions. After restore, the `open` field must be zero.

If there are terminal conflicts, `status` shows up to 20 recent errors. First inspect those clients manually in Remnawave. When the state is safe and there are no open sessions, confirm the check:

```bash
python -m app.tools.grace_access restore-all --apply --accept-conflicts
```

Only after all sessions have been closed successfully can you remove the migration and return to the old code:

```bash
alembic downgrade 0096
```

Rollback order: `drain` → `restore-all --apply` → verify `open=0` and conflicts → `alembic downgrade 0096` → deploy the old bot version.

## Safeguards

- Before changing Remnawave, a durable snapshot of the original state is saved.
- A repeated event for the same incident does not issue grace a second time.
- An API error leaves `pending`, which can be safely retried or restored.
- Retrying `pending` does not enable the user if the panel was changed or disabled manually.
- Manual disable and canonical billing changes take priority over grace.
- The external squad is temporarily removed until access is enabled and restored after completion.
- Deleting a subscription/user is blocked while open grace is unfinished, so the panel and database do not diverge.
- The database forbids cascading deletion of the only recovery snapshot of an open session.
- Ordinary, admin, and nightly Remnawave updates cannot overwrite grace status, period, traffic, or squads.
- After waiting for a lock, sync re-reads the subscription from the database, so an old task cannot cancel a fresh payment.
- Bulk add/remove of all clients from a squad is blocked if at least one open grace session exists.
- `drain` does not apply a new overlay and does not activate `pending`.

## Updating the bot from upstream

Migration `0097_add_grace_access` continues the sequential numbering (`down_revision = '0096'`).
