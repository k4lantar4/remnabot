# Upstream tracking baseline evidence

Date: 2026-08-31  
Host: RC (`bot-v4` / `91.107.144.95`)  
Task: M0-T5 · Authority: MVP plan `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`

## Goal

Record immutable upstream-tracking SHAs and classify fork-only drift on `origin/main` without integrating or merging. Read-only fetch permitted; no application code changes.

## Step 1: Seed snapshot (2026-08-31 brief)

Values from task brief at planning time — preserved as historical snapshot.

| Ref | SHA / tag | Notes |
|---|---|---|
| remnabot1 `main` | `89fa7dc584b9fb7f017c385d604614fb29692d66` | upstream release-please merge |
| remnabot1 `origin/main` | `31a3e93042e528ac13f1b8aa9f4acb02001bac99` | 1 ahead of local `main` |
| remnabot1 `prod-cutover` | `a168a817cbfdbab020ed3b328c596d866dfbc2a6` | local M0 docs branch |
| `/opt/bot` HEAD | `89fa7dc584b9fb7f017c385d604614fb29692d66` | upstream reference |
| cabinet `main` / `origin` / `upstream` | `35e5aa9e78123fdf18506a7a8a46875d268689ed` | release-please merge |
| remnabot reference (`/opt/remnabot`) | `f36ec4ca078eea3f2647f01887ccf987823fbfd0` | production reference 3.60.0 |
| remnawave/panel latest (seed) | **v3.3.2** (2026-08-29) | re-check at execution |
| RC compose promotion policy | `:3` / `:latest` | **violation** for production promotion |

## Step 2: Execution-time live values (2026-08-31 M0-T5)

Fetched read-only: `git fetch origin upstream remnabot` (remnabot1), `git fetch origin upstream` (cabinet). GitHub API for remnawave/panel release.

| Ref | Live SHA / tag | vs seed | Match |
|---|---|---|---|
| remnabot1 `main` | `89fa7dc584b9fb7f017c385d604614fb29692d66` | unchanged | yes |
| remnabot1 `origin/main` | `31a3e93042e528ac13f1b8aa9f4acb02001bac99` | unchanged | yes |
| remnabot1 `upstream/main` | `89fa7dc584b9fb7f017c385d604614fb29692d66` | fetched | 0/0 vs `main` |
| remnabot1 `prod-cutover` HEAD | `3f798500acf0971e4400661c146b8a50d2c229d2` | +4 M0 doc commits since seed | **differs** (expected) |
| remnabot1 `remnabot/main` | `f36ec4ca078eea3f2647f01887ccf987823fbfd0` | unchanged | yes |
| `/opt/bot` HEAD | `89fa7dc584b9fb7f017c385d604614fb29692d66` | unchanged | yes |
| cabinet `main` | `35e5aa9e78123fdf18506a7a8a46875d268689ed` | unchanged | yes |
| cabinet `origin/main` | `f52c7ec6d98c63078937d25a6db695cbd0b5a4dd` | 1 ahead (CI) | SHA differs from seed table row* |
| cabinet `upstream/main` | `35e5aa9e78123fdf18506a7a8a46875d268689ed` | unchanged | yes |
| remnabot reference HEAD | `f36ec4ca078eea3f2647f01887ccf987823fbfd0` | unchanged | yes |
| remnawave/panel latest release | **v3.4.2** published **2026-08-30T23:06:50Z** | seed v3.3.2 | **newer** — observation only |

\*Seed row grouped cabinet `main`/`origin`/`upstream` at one SHA; live `origin/main` is 1 commit ahead (CI only). `main` and `upstream/main` still match seed.

### prod-cutover lineage (local only)

`prod-cutover` is **5 commits ahead** of `main`, **1 commit behind** `origin/main`:

```
3f798500 docs(M0-T4): record baseline tag 89fa7dc5
8b70bd75 docs(M0-T3): cabinet git reconciliation
f10ebd75 docs(M0-T2): WIP inventory after remnabot1 re-fork
0c5fa2d1 docs(M0): make MVP plan the single authority after spec/errata deletion
a168a817 docs: governance topology audit and pre-M0 artifacts
```

Not pushed to `origin` at execution time.

### Application versions (CHANGELOG / pyproject / package.json)

| Tree | Version | Source |
|---|---|---|
| remnabot1 | 4.2.0 | `pyproject.toml` |
| `/opt/bot` (upstream ref) | 4.2.0 | `pyproject.toml` @ `89fa7dc5` |
| `/opt/remnabot` (production ref) | 3.60.0 | `CHANGELOG.md` |
| `/opt/cabinet` | 1.67.0 | `package.json` |

## Step 3: Git topology verification (six-identity table)

| Check | Expected | Live | Verdict |
|---|---|---|---|
| remnabot1 `origin` | `k4lantar4/remnabot1` | `https://github.com/k4lantar4/remnabot1.git` | PASS |
| remnabot1 `upstream` | official bot upstream | `BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot` | PASS |
| remnabot1 `remnabot` remote | reference only (`k4lantar4/remnabot`) | present, not `origin` | PASS |
| cabinet `origin` | `k4lantar4/cabinet` | `https://github.com/k4lantar4/cabinet.git` | PASS |
| cabinet `upstream` | `bedolaga-cabinet` | `BEDOLAGA-DEV/bedolaga-cabinet` | PASS |
| `/opt/cabinet1` | absent | ABSENT | PASS |
| remnabot `origin` | `k4lantar4/remnabot` | `https://github.com/k4lantar4/remnabot.git` | PASS |

**No `PLAN REVISION REQUIRED: Git topology ambiguity`.**

## Step 4: origin/main drift classification

### remnabot1 — `main..origin/main` (count: 1)

| SHA | Subject | Files | Classification |
|---|---|---|---|
| `31a3e930` | Create python-app.yml | `.github/workflows/python-app.yml` (+39 lines) | **defer** |

Rationale: GitHub Actions CI workflow on the fork; not a bot release, not MVP behavior. Do **not** merge into `prod-cutover` during M0.

### cabinet — `main..origin/main` (count: 1)

| SHA | Subject | Files | Classification |
|---|---|---|---|
| `f52c7ec6` | Create webpack.yml | `.github/workflows/webpack.yml` (+28 lines) | **defer** |

Rationale: GitHub Actions CI workflow on the fork; not a cabinet release. Consistent with M0-T3 cabinet reconciliation (fork-only CI drift).

## Step 5: remnawave/panel release observation

| Field | Seed (2026-08-29) | Live (M0-T5 execution) |
|---|---|---|
| Latest tag | v3.3.2 | **v3.4.2** |
| Published | 2026-08-29 (brief) | **2026-08-30T23:06:50Z** |

Recent tags (GitHub): v3.4.2, v3.4.1, v3.4.0.

**Not a production pin.** MVP promotion requires rehearsed pinned digest on PG 17.6 (plan §7). Observing upstream movement does not authorize deploy.

## Step 6: RC Remnawave compose promotion policy

From `/opt/remnawave/docker-compose.yml` (runtime on RC):

| Service | Image tag | Promotion status |
|---|---|---|
| `remnawave` | `remnawave/backend:3` | **violation** — moving `:3` tag, non-promotable |
| `remnawave-subscription-page` | `remnawave/subscription-page:latest` | **violation** — implicit `latest` |

RC dev stack (`backend:3`, PG 18.4, `:latest`) remains **non-promotable** until rehearsed with pinned digests per MVP plan.

Production target remains verified 2.8.1 → candidate 3.x **digest** on PG **17.6** via rehearsal track — not this RC configuration.

## Working tree notes (not committed)

| Tree | Dirty paths | Action |
|---|---|---|
| remnabot1 | `M docker-compose.yml`, docs under `docs/`, `?? locales/` | excluded from M0-T5 commit |
| cabinet | `M docker-compose.yml` | excluded |
| `/opt/bot` | `M docker-compose.yml` | read-only reference |

## Summary

| Item | Result |
|---|---|
| Live SHAs recorded | yes |
| Seed snapshot preserved | yes |
| Git topology | PASS |
| remnabot1 `origin/main` +1 | **defer** (CI) |
| cabinet `origin/main` +1 | **defer** (CI) |
| remnawave/panel latest | v3.4.2 (observation; not pin) |
| RC `:3` / `:latest` | promotion **violation** (unchanged policy) |
