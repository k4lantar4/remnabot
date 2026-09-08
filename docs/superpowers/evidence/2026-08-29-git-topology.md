# Git topology evidence

Date: 2026-08-29  
Host: RC (`bot-v4` / `91.107.144.95`)  
Re-verify: 2026-08-31 (appended below). Authority: MVP plan.

## Six-identity table

| # | Tree | Git? | Branch | HEAD (full SHA) | Remotes | @{u} | Ahead/Behind | Dirty |
|---|---|---|---|---|---|---|---|---|
| 1 | `/opt/remnabot` | yes | `main` | `f36ec4ca078eea3f2647f01887ccf987823fbfd0` | origin=`k4lantar4/remnabot`, upstream=official bot | `origin/main` | 0/0 | clean |
| 2 | `/opt/remnabot1` | yes | `prod-cutover` (from `main`) | `89fa7dc584b9fb7f017c385d604614fb29692d66` | origin=`k4lantar4/remnabot1`, upstream=official bot, remnabot=`k4lantar4/remnabot` | `origin/main` | 0/0 vs origin; 0/0 vs upstream | `M docker-compose.yml`; governance docs staged on branch |
| 3 | `/opt/cabinet` | yes | `main` | `35e5aa9e78123fdf18506a7a8a46875d268689ed` | origin=`k4lantar4/cabinet`, upstream=`bedolaga-cabinet` | `origin/main` | 0/0 both | clean |
| 4 | `/opt/bot` | yes | `main` | `89fa7dc584b9fb7f017c385d604614fb29692d66` | origin=official upstream | `origin/main` | matches remnabot1 | `M docker-compose.yml` |
| 5 | `/opt/remnawave` | no | — | — | — | — | — | runtime only |
| 6 | `/opt/caddy` | no | — | — | — | — | — | infra only |

## Versions

| Component | Version | Source |
|---|---|---|
| remnabot (reference) | 3.60.0 | CHANGELOG |
| remnabot embedded cabinet | 1.57.0 | `/opt/remnabot/cabinet/package.json` |
| remnabot1 | 4.2.0 | pyproject.toml / CHANGELOG |
| cabinet | 1.67.0 | package.json |

## Architecture A spec location (historical only)

- Remote tip: `k4lantar4/remnabot` `origin/chore/mcp-dev-tools` @ `70476c0e0a23657ce8959ffb76d0dfbebbd7e697`
- Local `chore/mcp-dev-tools` @ `47a92619` — does not contain spec blob
- **Do not recover into remnabot1.** Binding facts are inlined in `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`.

## Rejected topology names

| Claim | Verdict |
|---|---|
| `k4lantar4/cabinet1` / `/opt/cabinet1` | FALSE — repo 404; use `k4lantar4/cabinet` |
| remnabot1 `origin` = `k4lantar4/remnabot` | FALSE — origin is `remnabot1`; `remnabot` is extra remote |

## Re-verify 2026-08-31

| Tree | Branch | HEAD | Notes |
|---|---|---|---|
| `/opt/remnabot1` | `prod-cutover` | `a168a817cbfdbab020ed3b328c596d866dfbc2a6` | Local only; not on `origin`. Dirty: rule, `docker-compose.yml`, deleted specs, `?? locales/`, handoff |
| `/opt/remnabot1` `main` | `main` | `89fa7dc584b9fb7f017c385d604614fb29692d66` | behind `origin/main` 1 (`31a3e930` python-app.yml) |
| `/opt/cabinet` | `main` | `35e5aa9e78123fdf18506a7a8a46875d268689ed` | 0/0 origin+upstream; clean |
| `/opt/remnabot` | `main` | `f36ec4ca078eea3f2647f01887ccf987823fbfd0` | READ-ONLY |
| `/opt/bot` | `main` | `89fa7dc584b9fb7f017c385d604614fb29692d66` | dirty `docker-compose.yml` |

Alembic graft **not** done. remnabot1 still has upstream `0104_remnawave_numeric_id.py` and `0110_referral_user_reward_choice.py`.
