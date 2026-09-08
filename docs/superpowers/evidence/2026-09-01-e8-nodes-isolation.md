# E8 — Rehearsal must not control production nodes

Date: 2026-09-01  
Host: RC (`bot-v4`)  
Trigger: operator reported restored `nodes` dual-controlling production agents (nodes went down). Operator emptied `nodes`.

## Verdict

Empty `nodes` is the correct default. A live node is **not** required for M4 (or for panel HTTP identity/purchase APIs). Optional isolated dummy deferred.

## Runtime (VERIFIED)

| Check | Result |
|---|---|
| `rehearsal_rw` | healthy `3.4.3@sha256:4ea85b2f…84515422` |
| `/health` `127.0.0.1:3101` | HTTP 200 |
| `nodes` | **0** |
| `hosts_to_nodes` | 0 |
| `config_profile_inbounds_to_nodes` | 0 |
| `users` | 3181 |
| `hosts` | 50 (YAML public hostnames; not the node-agent control plane) |
| `config_profiles` / inbounds / internal_squads | 7 / 44 / 11 |
| Panel bind | `127.0.0.1:3100` + `:3101` only |
| `PANEL_DOMAIN` in gitignored `.env.rehearsal-rw` | `rw.rookari.com` (**Host header only**; DNS still production) |

Boot log earlier today (before empty): `NodeHealthCheckTask` “Restarting all nodes on application start”, config push, plugin sync, then health-check timeouts to restored agent addresses. After `nodes=0`, those start-all/health-check lines stopped.

## Decision

| Need | Now |
|---|---|
| Production nodes attached to rehearsal | **No** — caused dual-control |
| Local dummy node + new DNS | **No** for M4–M6 API gates |
| Keep `nodes` empty | **Yes** |

If a later batch needs an isolated dummy: new record `rw-rehearsal.rookari.com` A → `91.107.144.95`, Caddy to `127.0.0.1:3100`, new node + key from **this** panel only. Do not publish rehearsal on `rw.rookari.com`.

## Plan/rule

Inlined as **E8** in the MVP plan; forbidden DAG edge 5; `.cursor/rules/10-remnabot-migration.mdc`; compose comment on `deploy/remnawave/docker-compose.rehearsal.yml`.
