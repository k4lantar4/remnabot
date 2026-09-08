# Closed smoke — E8 nodes isolation (2026-09-01)

User smoke: none.

| # | Layer | Path | Expect | Status |
|---|---|---|---|---|
| 1 | Agent | `SELECT count(*) FROM nodes` | 0 | PASS |
| 2 | Agent | users / hosts / `/health` | 3181 / 50 / 200 | PASS |
| 3 | Agent | bind | `127.0.0.1:3100` | PASS |
