# Cabinet Git reconciliation evidence

Date: 2026-08-31  
Host: RC (`bot-v4` / `91.107.144.95`)  
Task: M0-T3 · Authority: MVP plan `docs/superpowers/plans/2026-08-28-production-cutover-mvp.md`

## Goal

Confirm `/opt/cabinet` already is the maintained fork (`k4lantar4/cabinet`). Non-destructive read-only inspection; no `git init`, no remote retarget, no force-push.

## Step 1: Live re-inspect (2026-08-31)

Commands (verbatim from M0-T3 brief):

```bash
git -C /opt/cabinet remote -v
git -C /opt/cabinet log -1 --format='%H %s'
git -C /opt/cabinet status --short
git -C /opt/cabinet rev-list --left-right --count main...origin/main
git -C /opt/cabinet rev-list --left-right --count main...upstream/main
test -d /opt/cabinet1 && echo EXISTS || echo ABSENT
```

### Output

**Remotes:**

```
origin	https://github.com/k4lantar4/cabinet.git (fetch)
origin	https://github.com/k4lantar4/cabinet.git (push)
upstream	https://github.com/BEDOLAGA-DEV/bedolaga-cabinet.git (fetch)
upstream	https://github.com/BEDOLAGA-DEV/bedolaga-cabinet.git (push)
```

**HEAD (log -1):**

```
35e5aa9e78123fdf18506a7a8a46875d268689ed Merge pull request #561 from BEDOLAGA-DEV/release-please--branches--main--components--cabinet-frontend
```

**Status:**

```
 M docker-compose.yml
```

**Branch tracking (`git branch -vv`):**

```
* main 35e5aa9e [origin/main: behind 1] Merge pull request #561 from BEDOLAGA-DEV/release-please--branches--main--components--cabinet-frontend
```

**Divergence (`main...origin/main`):**

```
0	1
```

(local `main` is **1 commit behind** `origin/main`)

**Divergence (`main...upstream/main`):**

```
0	0
```

**`/opt/cabinet1`:**

```
ABSENT
```

**Version (package.json):** 1.67.0

## Comparison to 2026-08-31 seed

| Field | Expected seed | Live (2026-08-31) | Match |
|---|---|---|---|
| origin remote | `k4lantar4/cabinet` | `k4lantar4/cabinet` | yes |
| upstream remote | `bedolaga-cabinet` | `BEDOLAGA-DEV/bedolaga-cabinet` | yes |
| HEAD (short) | `35e5aa9e` | `35e5aa9e78123fdf18506a7a8a46875d268689ed` | yes |
| `main...origin/main` | 0/0 | 0/1 (behind 1) | partial — fetch lag on origin only |
| `main...upstream/main` | 0/0 | 0/0 | yes |
| `/opt/cabinet1` | ABSENT | ABSENT | yes |
| Working tree | clean (seed) | `M docker-compose.yml` | partial — local compose WIP only |

## Topology verdict

**PASS — no Git topology ambiguity.**

Six-identity table requirements satisfied:

- Path: `/opt/cabinet` (maintained cabinet tree)
- `origin` = `k4lantar4/cabinet` (not `cabinet1`)
- `upstream` = `BEDOLAGA-DEV/bedolaga-cabinet`
- `/opt/cabinet1` absent

Dirty `docker-compose.yml` is local WIP only; does not indicate topology ambiguity (per controller resolution #3).

## Actions taken (M0-T3)

| Action | Result |
|---|---|
| `git init` on `/opt/cabinet` | **Not performed** (already a Git repo) |
| Retarget to `cabinet1` | **Not performed** (forbidden) |
| Force-push | **Not performed** (forbidden) |
| Modify `/opt/cabinet` | **Not performed** (read-only inspection) |
| Create `prod-cutover` branch on cabinet | **Deferred** — `main` suitable until custom cabinet commits (per brief Step 3) |

## remnabot1 commit

Evidence recorded on `prod-cutover` @ `/opt/remnabot1` only. Cabinet repository unchanged.
