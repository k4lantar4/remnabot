# M5-T2 single cabinet source of truth

Date: 2026-09-01  
Host: RC (`bot-v4` / `91.107.144.95`)  
Depends: M5-T1 user smoke **تایید**

## Rule

Canonical frontend: `/opt/cabinet`.  
Do not deploy `/opt/remnabot/cabinet` (legacy production embed).  
remnabot1 must not grow an embedded frontend `cabinet/` directory.

`app/cabinet/` in remnabot1 is the **bot Cabinet API** (Python). That is not a frontend embed.

## Agent verification

| Check | Result |
|---|---|
| `/opt/cabinet` | DIR (maintained repo, `prod-cutover` @ `95d49d8b`) |
| `/opt/cabinet1` | ABSENT |
| `/opt/remnabot1/cabinet` | ABSENT |
| `git ls-files cabinet/` in remnabot1 | empty |
| `/opt/remnabot/cabinet` | DIR (legacy 1.57.0; READ-ONLY; not mounted) |
| rehearsal compose `build.context` | `/opt/cabinet` |
| rehearsal rendered config | no `/opt/remnabot/cabinet`, no `cabinet1`, no `/opt/remnabot1/cabinet` |
| live `cabinet_frontend` working_dir | `/opt/cabinet` + `docker-compose.rc.yml` |
| `rehearsal_cabinet_frontend` | not created |
| `remnawave_bot` | unchanged id `3a8fbdb915d3…`; not rebuilt |
| `rehearsal_bot` app | not started |

## Compose pin

`docker-compose.rehearsal.yml` comments now state the M5-T2 constraint next to `context: /opt/cabinet`.

## User smoke

None (path/compose verification only).
