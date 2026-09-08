# WIP inventory (2026-08-31)

Authority: M0-T2 · MVP plan `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`

## 2026-08-31 snapshot facts (M0-T2 brief)

### remnabot1 (`prod-cutover` @ a168a817)

- `M docker-compose.yml`: joins external `remnawave-network`; comments out `bot_network` ipam subnet. This is RC-sandbox wiring, **not** rehearsal compose. Do not promote as cutover compose. Do not restore onto `remnabot1_postgres_data`.
- `M .cursor/rules/10-remnabot-migration.mdc`: authority-hierarchy retarget after spec deletion (keep).
- `D` four spec/errata files: intentional; stay deleted.
- `?? locales/`: bind-mounted into running `remnabot1-bot` (`/opt/remnabot1/locales:/app/locales`). Untracked. Do not commit unless M4-T7 FA work requires it.
- `app/custom` **missing**. Previous T2.1 wholesale seam is **not** on this fork.
- Wholesale port source: `/opt/remnabot/app/utils/price_display.py` (M4-T7).

### remnabot / cabinet

- remnabot clean @ `f36ec4ca`. cabinet clean @ `35e5aa9e`.
- No `app/` commit in M0.

---

## Execution state (after 0c5fa2d1)

Live re-verify: 2026-08-31 · host RC (`bot-v4`)

### remnabot1 HEAD

| Field | Value |
|---|---|
| Branch | `prod-cutover` |
| HEAD | `0c5fa2d174b5cad5dec5798b171239ff9de02229` |
| Subject | `docs(M0): make MVP plan the single authority after spec/errata deletion` |
| Prior tip (brief baseline) | `a168a817cbfdbab020ed3b328c596d866dfbc2a6` |

### Committed in 0c5fa2d1 (not current dirty)

These items appeared as WIP at brief baseline (`a168a817`) and are now committed:

- `.cursor/rules/10-remnabot-migration.mdc` — authority-hierarchy retarget after spec deletion (keep).
- Deleted four spec/errata files (intentional; stay deleted):
  - `docs/superpowers/plans/2026-08-28-production-cutover-mvp-errata.md`
  - `docs/superpowers/specs/2026-08-28-production-cutover-architecture-design.md`
  - `docs/superpowers/specs/2026-08-28-production-cutover-architecture-errata.md`
  - `docs/superpowers/specs/2026-08-29-governance-topology-audit-design.md`

Also in 0c5fa2d1 (not WIP): MVP plan update, evidence re-verifies, handoff doc update.

### Leftover WIP (uncommitted after 0c5fa2d1)

| Status | Path | Classification |
|---|---|---|
| `M` | `docker-compose.yml` | RC-sandbox wiring (external `remnawave-network`; `bot_network` ipam commented). **Not** rehearsal compose. Do not promote as cutover compose. Do not restore onto `remnabot1_postgres_data`. |
| `??` | `locales/` | Bind-mount copy (`en.json`, `fa.json`, `ru.json`, `ua.json`, `zh.json`). Untracked. Do not commit unless M4-T7 FA work requires it. |
| `M` | `docs/contests-api.md` | Leftover Russian→English doc translation from tree replace |
| `M` | `docs/grace-access.md` | Leftover Russian→English doc translation from tree replace |
| `M` | `docs/menu_stats_api_usage.md` | Leftover Russian→English doc translation from tree replace |
| `M` | `docs/miniapp-setup.md` | Leftover Russian→English doc translation from tree replace |
| `M` | `docs/persistent_cart_system.md` | Leftover Russian→English doc translation from tree replace |
| `M` | `docs/project_structure_reference.md` | Leftover Russian→English doc translation from tree replace |
| `M` | `docs/referral_program_setting.md` | Leftover Russian→English doc translation from tree replace |
| `M` | `docs/web-admin-integration-guide.md` | Leftover Russian→English doc translation from tree replace |
| `M` | `docs/web-admin-integration.md` | Leftover Russian→English doc translation from tree replace |
| `M` | `docs/websocket-and-webhooks.md` | Leftover Russian→English doc translation from tree replace |

### Unchanged snapshot facts (still true at execution)

- `app/custom` **missing** — previous T2.1 wholesale seam is **not** on this fork. Do not invent T2.1.
- Wholesale port source: `/opt/remnabot/app/utils/price_display.py` (M4-T7).

### remnabot / cabinet (live re-verify)

| Tree | HEAD | Dirty | Notes |
|---|---|---|---|
| `/opt/remnabot` | `f36ec4ca078eea3f2647f01887ccf987823fbfd0` | clean | Matches brief seed |
| `/opt/cabinet` | `35e5aa9e78123fdf18506a7a8a46875d268689ed` | `M docker-compose.yml` | SHA matches brief seed; local compose WIP only |

- No `app/` commit in M0.
- `git diff --cached --name-only \| grep '^app/'` empty at M0-T2 execution.
