# Cutover Plan Slim — Design Spec

**Date:** 2026-09-01  
**Status:** Draft pending user review  
**Tree:** `/opt/remnabot1` · branch `prod-cutover`  
**Authority after approval:** this spec, then the implementation plan derived from it  
**Does not execute:** M6-T3 or any later cutover task

---

## Problem

`docs/superpowers/plans/2026-08-28-production-cutover-mvp.md` is the single execution authority (~1373 lines). `.cursor/rules/10-remnabot-migration.mdc` tells every new chat to read the whole file first.

That contract was chosen after sibling specs/errata caused missed safety facts. It now costs a full history pass (M0–M5 bodies, stale 2026-08-31 re-verify, duplicated handoff) before an agent can run the open task.

A second cost is the session closer: a long two-layer smoke template plus a rubber-stamp `تایید` after every batch. The word is not a technical brake. A new chat still sees `Next: M6-T3` and often continues. The operator pays friction; the agent is not actually stopped.

**Current open work (VERIFIED 2026-09-01):** M6-T1 and M6-T2 are DONE. Next executable cutover task is **M6-T3**. This spec must not start it.

---

## Goal

Keep **one live execution authority** and a **frozen full-text archive**. Agents load the slim live plan plus the open milestone, not the archive, unless they are reconstructing a past decision.

Replace rubber-stamp `تایید` with brakes that actually bind: **named-start** on a new chat, **STOP classes** inside a chat.

---

## Non-goals

- Do not split into rival files (`constraints.md`, `M6.md`, restored errata siblings).
- Do not delete cutover safety (DNS, Telegram, C2C, rollback, writer-freeze, G1–G13, env A–E) from the live plan. M7/M8 still need it.
- Do not rewrite `docs/superpowers/evidence/*` bodies.
- Do not execute M6-T3, start `rehearsal_bot`, rebuild sandbox `remnawave_bot`, or touch production.
- Do not retarget remnabot1 `origin`. Do not invent `staging-host-*` RC URLs.

---

## Decisions (from brainstorming)

| Topic | Decision |
|-------|----------|
| Shape | Live plan + frozen archive (option 1) |
| Live path | Same path: `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md` |
| Archive path | `docs/superpowers/plans/archive/2026-08-28-production-cutover-mvp.full.md` |
| Rival files | Forbidden |
| Smoke closer | Short (see Session contract). No Open smoke table in the live plan |
| Wait / brake | Option B: STOP classes in-chat; named-start on a new chat |
| Rubber-stamp `تایید` | Not required to continue Agent-only work |
| Evidence | Closed-batch `docs/superpowers/evidence/smoke-*.md` stays; keep short |

---

## Files

| Path | Role | Agent default |
|------|------|----------------|
| `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md` | **Only live execution authority.** Slim rewrite in place. | Read every cutover chat |
| `docs/superpowers/plans/archive/2026-08-28-production-cutover-mvp.full.md` | Immutable copy of the live file taken **immediately before** the slim rewrite. Header note: frozen; do not edit; live plan is the path above. | Do **not** read unless reconstructing a past decision or `PLAN REVISION` |
| `.cursor/rules/10-remnabot-migration.mdc` | Always-apply load contract + DAG. Must match this spec. | Always loaded by Cursor |
| `docs/superpowers/evidence/*` | Snapshots. Unchanged by this work. | Re-check dates when a live task cites them |

Archive creation order is a safety constraint: **copy first, then slim.** If slim happens without a copy, stop with `PLAN REVISION REQUIRED: archive missing before slim`.

The archive is not a second architecture spec. If live plan and archive disagree, **live plan wins** for execution. Archive wins only as a historical record of what was written on freeze day.

---

## Live plan contents

Target size: about 400–600 lines (not a hard cap). Prefer cutting completed task bodies over cutting binding safety.

### Keep

1. Agent header (executing-plans; TDD/evidence; never “container started” = PASS). Named-start + STOP classes. Do not require per-task wait.
2. **Next pointer** — one line, current as of rewrite: open = **M6-T3**; M6-T1/T2 DONE with evidence links; do not poll `rehearsal_bot`.
3. Goal + Architecture + Tech Stack (short; drop repeated DONE lists from the blockquote).
4. Global Constraints (the existing bullet list, kept exact on safety values).
5. Six identities table (compact).
6. Forbidden DAG + standing Alembic (`0111` on G1 restore, remnabot lineage, upstream `0088–0110` archive-only, sandbox `remnabot1_postgres_data` still `0110`, never stamp/upgrade that volume with the graft).
7. Cutover safety: DNS, env A–E, Telegram isolation, C2C isolation, rollback, writer-freeze order, G1–G13.
8. **Session contract (new)** — briefing template + STOP classes + named-start. Replaces the 2026-08-31 long template and Open smoke table.
9. Open tasks with full steps: **M6-T3, M6-T4, M6-T5, M7-*, M8-T1, M9-***.
10. Closed milestones M0–M5 and M6-T1/T2 as a **one-line table**: ID · DONE date · evidence path. No graft/restore how-to bodies.
11. P1 / P2 still UNKNOWN where they block M6-T4 / M7–M8.
12. Fresh-conversation resume: live plan, `prod-cutover` HEAD, evidence, rule, runtime re-check. Do not point at deleted specs. Do not point at the archive as required reading.

### Move to archive only (not live)

- Full M0–M5 (and any other closed) task step lists.
- Re-verify 2026-08-31 snapshot (git HEAD table, then-absent compose, “no task executed” era).
- Claim verification table, duplicated self-review, duplicated execution handoff.
- Old Open smoke table and the long `خلاصه / اسموک من / بعد از تایید تو` template.

E1–E8 prose may be compressed into the standing constraints / DAG / E8 nodes rule. Do not drop a binding fact. If unsure whether a sentence is binding, keep it in the live plan.

---

## Session contract

### New-chat named-start (brake)

A new chat may run MVP/cutover tasks only if the **user message** names a task ID (`M6-T3`, `M7-T1`, …) or says **ادامه** or **شروع M6** (or the current open milestone). `شروع M6` / `ادامه` still cannot cross a STOP class (M6-T4 stays blocked without P1).

These are **not** named-start:

- Greeting, status question, unrelated bug, this slim-plan work, or “what is next?”
- The next-pointer sitting in the plan with no user verb

Default if unnamed: report next pointer and STOP classes ahead; do not start the task.

This slim-plan implementation is authorized by **this spec + the derived implementation plan**, not by named-start for M6-T3.

### In-chat continue vs STOP (brake)

After finishing a task in the **same chat**:

**Continue without asking** when all of:

- Next task is Agent-only (no operator Telegram / cabinet / C2C action)
- Same milestone **or** remaining named-batch weight ≤ 8
- Next task is not a STOP class
- Current task verification passed

**STOP** (do not start the next task) when any of:

| Class | Examples |
|-------|----------|
| User-visible | Operator must tap Telegram, open `https://panel.rookari.com`, or run a query they own |
| Missing prerequisite | P1 blocks M6-T4; P2 blocks M7-T5/M8 |
| High risk | Weight 13 or 21; DNS; production token; writer freeze; M8 |
| Failure | Test/gate fail; `PLAN REVISION REQUIRED` |
| Checkpoint end | End of M6.1 after T3 (then T4 is also STOP for P1); MVP-VERIFIED; M7/M8 boundaries |

M6.1 = {M6-T1, M6-T2, M6-T3}. T1/T2 are done. A chat that is **named-started** for M6-T3 may run T3 and must **STOP before M6-T4** (P1 + isolated C2C + user-visible).

Do not ask for rubber-stamp `تایید` on Agent-only PASS. Do not auto-start M8 from a next-pointer.

### Closeout briefing (replace the long template)

Agent-only continue (approved during brainstorming; facts from the M6-T2 closeout):

```
M6-T2 انجام شد.
HEAD: 0c6f38d4 prod-cutover — pushed
تومان: گیت ۸ تست + فیکس کسری (990550 → 550). rehearsal_bot روشن نشد.

اسموک کاربر: ندارد
Agent: pytest toman 8 PASS · price_display 25 PASS · import main · get_admin_texts=0

بعدی: M6-T3
ایست: ندارد
```

STOP example (do not start the next task):

```
M6-T3 انجام شد.
HEAD: <sha> prod-cutover — pushed
عمده: گیت PASS. rehearsal_bot روشن نشد.

اسموک کاربر: ندارد
Agent: pytest wholesale … PASS · import main

بعدی: M6-T4
ایست: Missing prerequisite — P1 isolated C2C chat
```

Rules:

- Silent wait (no HEAD, no next pointer, no STOP line) is a contract failure.
- `تایید؟` is not required on Agent-only continue.
- If STOP: say `ایست:` with class and reason. Do not say `تایید یعنی برو به …`.
- User-visible STOP: at most **3** items, each `مسیر` + `انتظار`. Operator replies `تایید` (all OK) or `2 FAIL: …`.
- Do not keep a living Open smoke table in the plan.
- On batch closeout, a short `docs/superpowers/evidence/smoke-YYYY-MM-DD-<task>.md` is enough. Do not paste the old 20-line template into evidence.

---

## Rule file changes

`.cursor/rules/10-remnabot-migration.mdc`:

**Remove / replace**

- `Read first: <entire 1373-line plan>`
- `Do not execute M6-T3 until the user explicitly says so` as a per-task rubber stamp

**Require**

- Read the **live** plan (slim) + the **open milestone section**, not the archive.
- Named-start and STOP classes as in this spec.
- Standing DAG, identities, Alembic, RC hostname `panel.rookari.com`, no `rehearsal_bot` polling until a named task that requires it, G8 = M6-T4 with isolated chat.
- Done-set current as of rewrite: through **M6-T2**; open **M6-T3**.
- Archive path recorded as frozen history, not required reading.

The rule stays the machine-readable DAG. The live plan stays Alembic + cutover execution authority. Do not copy the whole live plan back into the rule.

---

## Implementation constraints

1. Copy the current live plan to the archive path **before** any deletion/slim.
2. Archive file gets a 5-line banner at the top stating frozen date, source SHA (git blob or commit after add), and “do not edit; execute from the live path.” The rest of the file is the pre-slim text. Banner may prepend; do not rewrite the frozen body.
3. Slim rewrite must preserve exact safety values (IPs, hostnames, volume name prefixes, alembic heads, env class D/E rules, E8 nodes).
4. After rewrite, grep the live plan for leftover M0–M5 step checklists; they belong only in the archive.
5. `git add` only: archive file, slim plan, rule. No unrelated dirty docs, `docker-compose.yml`, `locales/`, `uv.lock`.
6. Verification: line count live plan ≪ archive; archive contains a known unique string from today’s full plan (e.g. `Task M4-T0`); live plan still contains `M6-T3`, `M8-T1`, env A–E, `rehearsal_*`; rule no longer says to read the whole historic file first; rule does not instruct a default rubber-stamp wait on M6-T3.

---

## Success criteria

- A new cutover chat can execute M6-T3 from the live plan without loading M0–M5 how-to bodies.
- Binding cutover/Alembic/Telegram/C2C/volume facts remain in the live plan and the rule.
- Full pre-slim text exists at the archive path and is not required reading.
- Closeout matches the short template; Open smoke table is gone from the live plan.
- Named-start + STOP classes are in both live plan header and the rule.
- M6-T3 is not started by this work.

---

## Risks

| Risk | Mitigation |
|------|------------|
| Slim drops a binding fact (the original reason for inlining) | Keep cutover safety + DAG + Alembic standing in full; when unsure, keep; archive exists for recovery |
| Agents still read the archive because the rule lists the path | Rule: archive default **off**; live plan says the same |
| `ادامه` in an unrelated chat starts M6-T3 | Named-start applies to MVP/cutover tasks; this spec’s implementation plan is a different named unit of work and must not include M6-T3 steps |
| Archive drifts after freeze | Do not edit archive. Later plan edits go only to the live file |

---

## Out of scope for the follow-up implementation plan

- Running wholesale tests (M6-T3)
- C2C P1 / G8
- Caddy/DNS/cutover
- Deduplicating `10-remnabot.mdc` vs `10-remnabot-migration.mdc` beyond the load-contract lines in this spec
