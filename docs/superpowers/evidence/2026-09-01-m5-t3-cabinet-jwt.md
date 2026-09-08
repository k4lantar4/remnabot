# M5-T3 RC cabinet JWT (class C)

Date: 2026-09-01  
Host: RC (`bot-v4` / `91.107.144.95`) + production `ssh bot` (read-only)  
Depends: M1-T3 env matrix; M5-T2 user OK  
Fingerprint: `sha256(utf-8)[:16]` (`app.custom.safety.token_guard.token_fingerprint`)

## Rule

`.env.rehearsal` `CABINET_JWT_SECRET` is class C (generated). Must differ from production (class D). Production-signed cabinet JWTs must not validate on the rehearsal secret. Secret values are not in git.

Live `/opt/remnabot1/.env` was **not** rewritten (session contract). Sandbox still signs cabinet JWTs with the test `BOT_TOKEN` fallback identity.

## Fingerprints (no secret values)

| Source | `CABINET_JWT_SECRET` | Fingerprint | Notes |
|---|---|---|---|
| Production `/opt/bot-remnawave/.env` | present, len 46 | `818cf61ccf8f100d` | same as production `BOT_TOKEN` |
| Rehearsal `/opt/remnabot1/.env.rehearsal` | present, len 64 | `6e66e417433351da` | generated; ≠ prod; ≠ test `BOT_TOKEN` `458863639bbe6d6b` |
| Live sandbox `/opt/remnabot1/.env` | present, len 46 | `458863639bbe6d6b` | equals test `BOT_TOKEN`; not production |
| `.env.cutover` | key present, empty | — | class D stub; not an `env_file` |

Match rehearsal vs production: **no**.

## Cross-validation (HS256)

| Token | Key | Result |
|---|---|---|
| Production-signed dummy (`sub=0`, `type=access`, 2 min exp, minted on `Bot`, not stored) | rehearsal secret | `jwt.InvalidSignatureError` |
| Rehearsal-signed dummy | rehearsal secret | decode OK (`type=access`) |

Production JWT **does not** validate on RC rehearsal secret.

## Git / isolation

| Check | Result |
|---|---|
| `git check-ignore .env.rehearsal .env .env.cutover` | ignored |
| `git ls-files` those env files | empty |
| `git grep 'CABINET_JWT_SECRET='` excluding `.env.example` | no tracked assignments |
| `.env.example` | `CABINET_JWT_SECRET=` empty placeholder |
| `rehearsal_bot` app | not started |
| `remnawave_bot` | unchanged id `3a8fbdb915d3…`; not rebuilt |

No new secret generated this batch — M1-T3 value still valid and distinct from production.
