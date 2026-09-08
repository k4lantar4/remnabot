# M3-T0 — Choose Remnawave 3.x candidate (tracking, not pin)

Date: 2026-09-01  
Host: RC (`bot-v4` / `91.107.144.95`)  
Task: M3-T0 · weight 3 · dependencies: M0-T5  
Authority: `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`  
Source: `https://github.com/remnawave/panel/releases` via `gh api` (not Hub `:latest`, not RC `backend:3`)

## Verdict: CANDIDATE_TAG = `3.4.3`

| Field | Value |
|---|---|
| `CANDIDATE_TAG` | **`3.4.3`** |
| Panel release | [v3.4.3](https://github.com/remnawave/panel/releases/tag/3.4.3) published **2026-08-31T20:14:25Z** · draft **false** · prerelease **false** |
| Panel git | tag `3.4.3` → commit `6af9a271413b1aa445269d2133adf7f4c4d59fb1` (“Release v3.4.3”) |
| Recommended docker tag | **`remnawave/backend:3.4.3`** (also `ghcr.io/remnawave/backend:3.4.3`) |
| Do **not** use | `remnawave/backend:latest`, `remnawave/backend:3`, RC sandbox image |
| Digest pull | **deferred to M3-T1** (this task records tag + Hub/index observation only) |

Plan rule: if a newer 3.x exists at execution than the 2026-08-29 seed **v3.3.2**, **that** is the candidate unless notes say otherwise. Notes do not say otherwise.

## Why not 3.3.2 / 3.4.2

| Tag | Published | Role |
|---|---|---|
| v3.3.2 | 2026-08-20T03:09:56Z | M0 plan seed / RC sandbox age (~2026-08-20); **superseded** |
| v3.4.2 | 2026-08-30T23:06:50Z | M0-T5 live observation (not a pin) |
| **v3.4.3** | 2026-08-31T20:14:25Z | **latest stable 3.x at M3-T0** |

Backend 3.4.3 changelog (`3.4.2...3.4.3`): security **fix** “Backend-tools auth bypass via mixed-case path” (`1581086b`). No “stay on 3.3.2”, no “do not upgrade from 2.8.1”, no prerelease flag.

Backend annotated tag peels to commit `f8ad8ad3410252215ca7b2e429d157bd275ec564`.

## Docker Hub / index (observation — not a rehearsal pin)

Inspected with Docker Hub API + `docker buildx imagetools inspect remnawave/backend:3.4.3` (manifests only; **image layers not pulled**). Host arch: **x86_64**.

| Item | Digest |
|---|---|
| OCI index `docker.io/remnawave/backend:3.4.3` | `sha256:4ea85b2fc16bd3e5d367b61afc07ec219133eaa12dd7b5e898adc33c84515422` |
| linux/amd64 manifest | `sha256:f471279e06fd02c48b18b6be49233f66a99c48e82ad512d1c99eb6e5d120e333` |
| linux/arm64 manifest | `sha256:498a26f610d02969caf8d0bb3a8cb1c31a88ca03d5f218f34d3e1487ce2cce1b` |

M3-T1 must `docker pull remnawave/backend:3.4.3` on this host and record the **actual pulled digest**, then compare to the index/amd64 values above. Do not treat Hub observation as G3-passed.

## Not in this batch

| Item | Status |
|---|---|
| Pull `3.4.3` into rehearsal | **not done** (`docker image inspect remnawave/backend:3.4.3` → absent) |
| Swap `rehearsal_rw` off 2.8.1 | **not done** |
| Prisma / G3 upgrade on `rehearsal_rw_pg17` | M3-T1 |
| `remnawave/subscription-page:3.4.3` | Hub **404** — do not assume a matching sub-page tag; M3-T1 decides the sub-page image |
| RC sandbox `backend:3` as candidate | **forbidden** (E4 / two-track) |

## Isolation (unchanged)

| Name | After M3-T0 |
|---|---|
| `rehearsal_rw` | still `remnawave/backend:2.8.1@sha256:361f9bb0b183d4fcefea2f1f7163db490e2aa1ec3b4bdde016a9ab9229ce956b` healthy |
| `rehearsal_rw_pg17` | G2 restore; not upgraded |
| `rehearsal_bot` | **absent** |
| `rehearsal_bot_db` / `rehearsal_bot_pg15` | G1 left running; no alembic |
| sandbox `remnawave` | still `remnawave/backend:3` (image created 2026-08-20T03:07:32Z — **not** 3.4.3) |
| `remnawave-db-data` | sandbox only |

## Next

M3-T1: snapshot `rehearsal_rw_pg17` with `pg_dump -Fc`, pull `remnawave/backend:3.4.3`, record digest, Prisma on the **copy**, G3 GO/NO-GO. Do not start `rehearsal_bot`. Do not alembic-upgrade bot restore until M4-T0.
